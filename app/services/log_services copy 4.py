# app/services/log_services.py

import re
import os
import uuid
import json
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import structlog
from rich.console import Console
from rich.panel import Panel

# pandas still used in logs_to_dataframe pipeline
import pandas as pd

from app.models.log_analyzer_models import MultiLogAnalysis, LogAnalysis  # Pydantic models
from .log_parser import MultiFileLogParser
from .generic_ai_connector import AIConnectorFactory
from .report_generator import LogReportGenerator

logger = structlog.get_logger(__name__)
console = Console()


class LogAnalyzerService:
    """Service to parse logs, analyze with AI, and generate structured reports."""

    def __init__(self, provider_name: str = "openai", base_uploads: str = "data/uploads"):
        self.parser = MultiFileLogParser()
        self.ai_service = AIConnectorFactory.get_connector(provider_name)
        self.analysis_cache: Dict[str, Any] = {}
        self._initialized = False

        # Folders
        self.base_uploads = Path(base_uploads)
        self.base_dir = Path("outputs")
        self.base_dir.mkdir(parents=True, exist_ok=True)

        batch_name = datetime.utcnow().strftime("%Y-%m-%d_%H-%M-%S")
        self.batch_folder = self.base_dir / batch_name
        self.batch_folder.mkdir(parents=True, exist_ok=True)

        self.reporter = LogReportGenerator(output_dir=str(self.batch_folder))
        console.log(f"[Init] Batch folder created: {self.batch_folder}")

    # -------------------------------------------------------------------
    async def _ensure_initialized(self):
        """Initialize parser and AI connector once per batch."""
        if not self._initialized:
            console.log("[Init] Initializing parser and AI service...")
            if hasattr(self.parser, "health_check"):
                await self.parser.health_check()
            if hasattr(self.ai_service, "initialize"):
                await self.ai_service.initialize()
            self._initialized = True
            console.log("[Init] LogAnalyzerService initialized successfully")

    # -------------------------------------------------------------------
    async def _extract_ai_text(self, ai_response) -> str:
        """Extract text content from Gemini or OpenAI-style response."""
        raw_text = ""
        # Gemini format
        if hasattr(ai_response, "candidates") and ai_response.candidates:
            candidate = ai_response.candidates[0]
            parts = getattr(getattr(candidate, "content", {}), "parts", [])
            raw_text = "".join([getattr(p, "text", "") for p in parts if getattr(p, "text", None)]).strip()

        # Fallback: OpenAI-like format
        if not raw_text:
            # Some connectors set 'content' or 'text'
            raw_text = getattr(ai_response, "content", "") or getattr(ai_response, "text", "") or ""

        return (raw_text or "").strip()

    # -------------------------------------------------------------------
    def _strip_code_fences(self, text: str) -> str:
        """
        Remove Markdown code fences (```json ... ``` or ``` ... ```) and return inner content.
        If multiple fences exist, join contents with newlines.
        """
        if not text:
            return ""

        # Remove leading/trailing whitespace
        t = text.strip()

        # Collect fenced blocks
        fenced_blocks = re.findall(r"```(?:json)?\s*(.*?)```", t, flags=re.DOTALL | re.IGNORECASE)
        if fenced_blocks:
            # If fences found, return the concatenated inner parts
            return "\n".join(b.strip() for b in fenced_blocks if b and b.strip())

        # If no fenced code blocks, return original
        return t

    # -------------------------------------------------------------------
    def _extract_json_substring(self, text: str) -> Optional[str]:
        """
        Try to extract a JSON object or array substring from arbitrary text.
        Returns the JSON substring if found, otherwise None.
        """
        if not text:
            return None

        # Search for the first outermost { ... } or [ ... ] that looks like JSON
        # We'll attempt to find the longest balanced braces substring.
        def find_balanced(text, open_ch, close_ch):
            start_idxs = [m.start() for m in re.finditer(re.escape(open_ch), text)]
            for start in start_idxs:
                depth = 0
                for i in range(start, len(text)):
                    if text[i] == open_ch:
                        depth += 1
                    elif text[i] == close_ch:
                        depth -= 1
                        if depth == 0:
                            return text[start : i + 1]
            return None

        # Prefer object first, fallback to array
        obj = find_balanced(text, "{", "}")
        if obj:
            return obj
        arr = find_balanced(text, "[", "]")
        if arr:
            return arr
        return None

    # -------------------------------------------------------------------
    def _parse_ai_text_to_struct(self, raw_text: str) -> Dict[str, Any]:
        """
        Clean raw AI text and attempt to parse JSON; returns a plain dict.
        If JSON cannot be parsed, returns a dict with 'summary' containing cleaned text.
        """
        if not raw_text:
            return {"summary": "", "observations": [], "planning": [], "events": [], "traffic_patterns": [], "highest_severity": None, "requires_immediate_attention": False}

        # 1) strip fenced code blocks if present
        cleaned = self._strip_code_fences(raw_text)

        # 2) try direct json.loads
        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, dict):
                return parsed
            # if parsed is list or other, wrap into dict
            return {"parsed": parsed}
        except Exception:
            # 3) try to extract a JSON substring and load it
            json_sub = self._extract_json_substring(cleaned)
            if json_sub:
                try:
                    parsed = json.loads(json_sub)
                    if isinstance(parsed, dict):
                        return parsed
                    return {"parsed": parsed}
                except Exception:
                    # fallthrough to return cleaned text
                    pass

        # 4) fallback: return cleaned text as summary
        return {"summary": cleaned}

    # -------------------------------------------------------------------
    def _normalize_to_log_analysis(self, structured: Dict[str, Any], file_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Convert the parsed AI dict (which may originate from many schemas) into
        a dict that matches your LogAnalysis Pydantic model fields.
        Ensures required fields such as 'file_name' exist.
        """

        # Helper to try many possible key names
        def pick(*keys, default=None):
            for k in keys:
                if k in structured and structured[k] not in (None, ""):
                    return structured[k]
            return default

        # Build normalized dict
        normalized: Dict[str, Any] = {}

        # file_name (required)
        normalized["file_name"] = pick("file_name", "filename", "file") or (Path(file_path).name if file_path else f"log_{uuid.uuid4().hex}.log")

        # summary: prefer 'summary' or overall_summary or AI-output textual fallbacks
        normalized["summary"] = pick("summary", "overall_summary", "analysis_summary", default="No summary provided.")
        if isinstance(normalized["summary"], dict) or isinstance(normalized["summary"], list):
            # convert non-string summary into a compact string
            try:
                normalized["summary"] = json.dumps(normalized["summary"], ensure_ascii=False, indent=2)
            except Exception:
                normalized["summary"] = str(normalized["summary"])

        # observations: list
        obs = pick("observations", "aggregated_findings", "findings", default=[])
        if isinstance(obs, str):
            # split heuristically by lines or bullets
            obs_list = [line.strip(" -•\t") for line in re.split(r"\r?\n|;|\u2022|-", obs) if line.strip()]
            normalized["observations"] = obs_list
        elif isinstance(obs, list):
            normalized["observations"] = obs
        else:
            normalized["observations"] = []

        # planning: list
        plan = pick("planning", "steps_to_resolve", "recommendations", default=[])
        if isinstance(plan, str):
            plan_list = [line.strip(" -•\t") for line in re.split(r"\r?\n|;|\u2022|-", plan) if line.strip()]
            normalized["planning"] = plan_list
        elif isinstance(plan, list):
            normalized["planning"] = plan
        else:
            normalized["planning"] = []

        # events: try to use structured events if present
        events = pick("events", "combined_events", "security_events", "individual_analyses", default=[])
        # If events are list-like but items are strings, wrap minimal structure
        normalized_events = []
        if isinstance(events, list):
            for ev in events:
                if isinstance(ev, dict):
                    normalized_events.append(ev)
                else:
                    normalized_events.append({"reasoning": str(ev), "relevant_log_entries": []})
        normalized["events"] = normalized_events

        # traffic_patterns
        tp = pick("traffic_patterns", "patterns", default=[])
        if isinstance(tp, list):
            normalized["traffic_patterns"] = tp
        elif isinstance(tp, dict):
            # convert dict to list if needed
            normalized["traffic_patterns"] = [tp]
        else:
            normalized["traffic_patterns"] = []

        # highest_severity
        highest = pick("highest_severity", "highest_severity_overall", default=None)
        normalized["highest_severity"] = highest

        # requires immediate attention: try to detect from flags or severity
        req = pick("requires_immediate_attention", "requires_immediate_action", default=None)
        if req is None:
            normalized["requires_immediate_attention"] = (str(highest).lower() in ("critical", "high", "error"))
        else:
            normalized["requires_immediate_attention"] = bool(req)

        return normalized

    # -------------------------------------------------------------------
    async def analyze_log_file(self, request_id: str, file_path: str, date_filter: Optional[Any] = None) -> LogAnalysis:
        """
        Analyze a single log file and return structured LogAnalysis (Pydantic model).
        This function always returns a LogAnalysis instance (safe to .dict()).
        """
        await self._ensure_initialized()
        console.log(f"[Step 0] Analyzing single file: {file_path}")

        try:
            # Parse file(s) using existing parser
            parse_results = await self.parser.parse_multiple_logs([file_path])
            df = self.parser.logs_to_dataframe(parse_results)
            console.log(f"[Step 1] Parsed {len(df)} rows from file {file_path}")

            if df.empty:
                console.log("[Step 2] File contains no logs")
                return LogAnalysis(
                    file_name=Path(file_path).name,
                    summary=f"No log entries found in file: {file_path}",
                    observations=[],
                    planning=[],
                    events=[],
                    traffic_patterns=[],
                    highest_severity=None,
                    requires_immediate_attention=False,
                )

            # Prepare combined text for AI (first 100 rows)
            combined_text = "\n".join(df["message"].tolist()[:100])
            console.log(f"[Step 3] Prepared text for AI (file: {file_path})")

            prompt = f"""Analyze the following log entries and return structured JSON matching the LogAnalysis schema.
If possible return JSON only. If you cannot produce full schema, at least include summary, observations, planning, events, traffic_patterns, highest_severity.
Log entries:
{combined_text}
"""

            ai_request = {
                "prompt": prompt,
                "context": {"analysis_type": "log_analysis", "request_id": request_id, "file": Path(file_path).name},
                "max_tokens": 2000,
                "temperature": 0.0,
            }

            try:
                ai_response = await self.ai_service.generate_text(ai_request)
                raw_text = await self._extract_ai_text(ai_response)
                parsed = self._parse_ai_text_to_struct(raw_text)
                normalized = self._normalize_to_log_analysis(parsed, file_path=file_path)

                # Build LogAnalysis Pydantic model (this validates)
                result = LogAnalysis(**normalized)
            except Exception as e:
                # If validation fails or AI failed, create fallback LogAnalysis
                logger.error("AI analysis or validation failed", error=str(e), traceback=traceback.format_exc())
                result = LogAnalysis(
                    file_name=Path(file_path).name,
                    summary=(raw_text.strip() if 'raw_text' in locals() and raw_text else f"AI analysis failed: {e}"),
                    observations=[],
                    planning=[],
                    events=[],
                    traffic_patterns=[],
                    highest_severity=None,
                    requires_immediate_attention=False,
                )

            # Save results to a per-analysis folder
            analysis_id = str(uuid.uuid4())
            folder = self.batch_folder / analysis_id
            folder.mkdir(parents=True, exist_ok=True)
            json_path = folder / f"analysis_{analysis_id}.json"
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(result.dict(), f, indent=2, default=str)
            console.log(f"[Step 4] Single-file LogAnalysis JSON saved: {json_path}")

            # Generate report (best-effort)
            try:
                self.reporter.output_dir = str(folder)
                self.reporter.generate_reports(analysis_id, result.dict())
                console.log(f"[Step 5] Reports generated in folder: {folder}")
            except Exception:
                logger.warning("Report generation failed", exc_info=True)

            return result

        except Exception as e:
            logger.error(f"Error analyzing file {file_path}: {e}", traceback=traceback.format_exc())
            return LogAnalysis(
                file_name=Path(file_path).name if file_path else f"log_{uuid.uuid4().hex}.log",
                summary=f"Error analyzing file: {file_path}\n{e}",
                observations=[],
                planning=[],
                events=[],
                traffic_patterns=[],
                highest_severity=None,
                requires_immediate_attention=False,
            )

    # -------------------------------------------------------------------
    async def analyze_multiple_files(self, file_paths: List[str], analysis_folder: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
        """
        Analyze multiple files together.
        Returns dict: { filename: LogAnalysis.dict() }
        """
        await self._ensure_initialized()

        if not file_paths:
            raise ValueError("No file paths provided for analysis")

        console.log(f"[Multi] Analyzing {len(file_paths)} files: {file_paths}")
        results: Dict[str, Any] = {}

        # Parse all at once to allow combined analysis if desired
        parse_results = await self.parser.parse_multiple_logs(file_paths)
        df_all = self.parser.logs_to_dataframe(parse_results)
        console.log(f"[Multi] Parsed {len(df_all)} rows from {len(parse_results)} files")

        # Option A: If you want a combined analysis for all files, call AI once:
        if not df_all.empty:
            combined_text = "\n".join(df_all["message"].tolist()[:100])
            prompt = f"Analyze combined logs and return LogAnalysis-like JSON describing overall findings.\n{combined_text}"
            ai_request = {"prompt": prompt, "context": {"analysis_type": "combined_log_analysis"}, "max_tokens": 2000, "temperature": 0.0}
            try:
                ai_response = await self.ai_service.generate_text(ai_request)
                raw_text = await self._extract_ai_text(ai_response)
                parsed = self._parse_ai_text_to_struct(raw_text)
                normalized = self._normalize_to_log_analysis(parsed, file_path=None)
                # use analysis id for combined file_name
                normalized.setdefault("file_name", "combined_logs")
                combined_result = LogAnalysis(**normalized)
                # Put combined result under a special key
                results["combined"] = combined_result.dict()
            except Exception:
                # ignore combined failure, we'll do per-file
                logger.debug("Combined analysis failed; falling back to per-file", exc_info=True)

        # Per-file analysis to ensure we have structured outputs for each file (safe path)
        for fp in file_paths:
            try:
                single_result = await self.analyze_log_file(str(uuid.uuid4()), fp)
                results[Path(fp).name] = single_result.dict()
            except Exception as e:
                logger.exception("Per-file analysis failed for %s", fp)
                results[Path(fp).name] = {"error": str(e)}

        # Save overall results if an analysis_folder requested
        folder = Path(analysis_folder) if analysis_folder else (self.batch_folder / str(uuid.uuid4()))
        folder.mkdir(parents=True, exist_ok=True)
        out_path = folder / f"multi_analysis_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(results, fh, indent=2, default=str)
        console.log(f"[Multi] Saved multi-file results: {out_path}")

        # Generate reports
        try:
            self.reporter.output_dir = str(folder)
            self.reporter.generate_reports(str(uuid.uuid4()), results)
        except Exception:
            logger.warning("Multi-file report generation failed", exc_info=True)

        return results


# -------------------------------------------------------------------
# STRESSED Printer
# -------------------------------------------------------------------
class StressedPrinter:
    """Print STRESSED-style humorous console report."""

    def print_summary(self, analysis: LogAnalysis):
        panel_text = f"""
😰 STRESSED (STRuctured Generation Security System Evaluating Data) 😰

Summary: {analysis.summary}

Current Status:
Anxiety         ▓▓▓▓▓▓▓▓▓░ 90%
Coffee          ▓░░░░░░░░░ 10%
Understanding   NOT APPLICABLE

Coping Mechanisms:
- Deep breaths between log entries
- Nervous documentation
- Excessive commenting
- Strategic panic
"""
        console.print(Panel(panel_text, border_style="red", title="STRESSED Report"))
