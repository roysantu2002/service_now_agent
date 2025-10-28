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

import pandas as pd

from app.models.log_analyzer_models import MultiLogAnalysis, LogAnalysis
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

        self.base_uploads = Path(base_uploads)
        self.base_dir = Path("outputs")
        self.base_dir.mkdir(parents=True, exist_ok=True)

        batch_name = datetime.utcnow().strftime("%Y-%m-%d_%H-%M-%S")
        self.batch_folder = self.base_dir / batch_name
        self.batch_folder.mkdir(parents=True, exist_ok=True)

        self.reporter = LogReportGenerator(output_dir=str(self.batch_folder))
        console.log(f"[Init] Batch folder created: {self.batch_folder}")

    # ------------------------------------------------------------
    async def _ensure_initialized(self):
        if not self._initialized:
            console.log("[Init] Initializing parser and AI service...")
            if hasattr(self.parser, "health_check"):
                await self.parser.health_check()
            if hasattr(self.ai_service, "initialize"):
                await self.ai_service.initialize()
            self._initialized = True
            console.log("[Init] LogAnalyzerService initialized successfully")

    # ------------------------------------------------------------
    async def _extract_ai_text(self, ai_response) -> str:
        """Extract and format text content from Gemini or OpenAI-like responses."""
        raw_text = ""
        if hasattr(ai_response, "candidates") and ai_response.candidates:
            candidate = ai_response.candidates[0]
            parts = getattr(getattr(candidate, "content", {}), "parts", [])
            raw_text = "".join(
                [getattr(p, "text", "") for p in parts if getattr(p, "text", None)]
            ).strip()

        if not raw_text:
            raw_text = getattr(ai_response, "content", "") or getattr(ai_response, "text", "") or ""

        # Remove unnecessary wrapping or escape chars
        raw_text = raw_text.replace("\\n", "\n").replace("\\t", "\t").strip()
        # Remove extra quotes if it’s a quoted string
        if raw_text.startswith('"') and raw_text.endswith('"'):
            raw_text = raw_text[1:-1]
        return raw_text.strip()

    # ------------------------------------------------------------
    def _strip_code_fences(self, text: str) -> str:
        if not text:
            return ""
        fenced_blocks = re.findall(r"```(?:json)?\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
        if fenced_blocks:
            return "\n".join(b.strip() for b in fenced_blocks if b.strip())
        return text.strip()

    # ------------------------------------------------------------
    def _extract_json_substring(self, text: str) -> Optional[str]:
        if not text:
            return None

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

        obj = find_balanced(text, "{", "}")
        if obj:
            return obj
        arr = find_balanced(text, "[", "]")
        if arr:
            return arr
        return None

    # ------------------------------------------------------------
    def _parse_ai_text_to_struct(self, raw_text: str) -> Dict[str, Any]:
        """Clean, format, and parse AI text to structured JSON."""
        if not raw_text:
            return {"summary": "Empty AI response."}

        # Log what the AI returned (for debugging)
        console.log("[DEBUG] Raw AI text start >>>")
        console.log(raw_text[:500])
        console.log("[DEBUG] Raw AI text end <<<")

        cleaned = self._strip_code_fences(raw_text)

        # Sanitize common issues
        cleaned = cleaned.strip()
        cleaned = re.sub(r"^json\s*[:=-]?\s*", "", cleaned, flags=re.IGNORECASE)

        # Try to load directly
        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, dict):
                return parsed
            return {"parsed": parsed}
        except Exception:
            pass

        # Attempt to find JSON-like section
        json_sub = self._extract_json_substring(cleaned)
        if json_sub:
            try:
                parsed = json.loads(json_sub)
                if isinstance(parsed, dict):
                    return parsed
                return {"parsed": parsed}
            except Exception:
                pass

        # If nothing worked, fallback with cleaned text
        return {"summary": cleaned}

    # ------------------------------------------------------------
    def _normalize_to_log_analysis(self, structured: Dict[str, Any], file_path: Optional[str] = None) -> Dict[str, Any]:
        """Normalize AI response to match LogAnalysis schema."""
        def pick(*keys, default=None):
            for k in keys:
                if k in structured and structured[k] not in (None, ""):
                    return structured[k]
            return default

        normalized: Dict[str, Any] = {}

        normalized["file_name"] = pick("file_name", "filename", "file") or (
            Path(file_path).name if file_path else f"log_{uuid.uuid4().hex}.log"
        )

        normalized["summary"] = pick("summary", "overall_summary", "analysis_summary", default="No summary provided.")
        if isinstance(normalized["summary"], (dict, list)):
            try:
                normalized["summary"] = json.dumps(normalized["summary"], ensure_ascii=False, indent=2)
            except Exception:
                normalized["summary"] = str(normalized["summary"])

        obs = pick("observations", "findings", "issues", default=[])
        if isinstance(obs, str):
            obs = [line.strip(" -•\t") for line in re.split(r"[\n;•-]", obs) if line.strip()]
        normalized["observations"] = obs if isinstance(obs, list) else []

        plan = pick("planning", "recommendations", "next_steps", default=[])
        if isinstance(plan, str):
            plan = [line.strip(" -•\t") for line in re.split(r"[\n;•-]", plan) if line.strip()]
        normalized["planning"] = plan if isinstance(plan, list) else []

        events = pick("events", "incidents", "security_events", default=[])
        if isinstance(events, str):
            events = [{"reasoning": events, "relevant_log_entries": []}]
        elif isinstance(events, list):
            events = [
                ev if isinstance(ev, dict) else {"reasoning": str(ev), "relevant_log_entries": []}
                for ev in events
            ]
        normalized["events"] = events

        tp = pick("traffic_patterns", "patterns", default=[])
        if isinstance(tp, dict):
            tp = [tp]
        normalized["traffic_patterns"] = tp if isinstance(tp, list) else []

        normalized["highest_severity"] = pick("highest_severity", "severity", default=None)
        req = pick("requires_immediate_attention", "requires_immediate_action", default=None)
        if req is None:
            normalized["requires_immediate_attention"] = (
                str(normalized["highest_severity"]).lower() in ("critical", "high", "error")
            )
        else:
            normalized["requires_immediate_attention"] = bool(req)

        return normalized

    # ------------------------------------------------------------
    async def analyze_log_file(self, request_id: str, file_path: str, date_filter: Optional[Any] = None) -> LogAnalysis:
        await self._ensure_initialized()
        console.log(f"[Step 0] Analyzing file: {file_path}")

        try:
            parse_results = await self.parser.parse_multiple_logs([file_path])
            df = self.parser.logs_to_dataframe(parse_results)
            console.log(f"[Step 1] Parsed {len(df)} rows")

            if df.empty:
                return LogAnalysis(
                    file_name=Path(file_path).name,
                    summary=f"No log entries found in {file_path}",
                    observations=[], planning=[], events=[],
                    traffic_patterns=[], highest_severity=None,
                    requires_immediate_attention=False,
                )

            combined_text = "\n".join(df["message"].tolist()[:100])
            prompt = f"""Analyze the following logs and return a structured JSON matching the LogAnalysis schema:
- summary
- observations
- planning
- events
- traffic_patterns
- highest_severity
- requires_immediate_attention

Logs:
{combined_text}"""

            ai_request = {"prompt": prompt, "context": {"file": Path(file_path).name}, "max_tokens": 2000, "temperature": 0.0}
            ai_response = await self.ai_service.generate_text(ai_request)
            raw_text = await self._extract_ai_text(ai_response)
            parsed = self._parse_ai_text_to_struct(raw_text)
            normalized = self._normalize_to_log_analysis(parsed, file_path)
            result = LogAnalysis(**normalized)

        except Exception as e:
            logger.error("AI analysis failed", error=str(e), traceback=traceback.format_exc())
            result = LogAnalysis(
                file_name=Path(file_path).name,
                summary=f"Error analyzing log: {e}",
                observations=[], planning=[], events=[],
                traffic_patterns=[], highest_severity=None,
                requires_immediate_attention=False,
            )

        folder = self.batch_folder / str(uuid.uuid4())
        folder.mkdir(parents=True, exist_ok=True)
        with open(folder / "analysis.json", "w", encoding="utf-8") as f:
            json.dump(result.dict(), f, indent=2, default=str)
        console.log(f"[Saved] Analysis saved to {folder}/analysis.json")

        try:
            self.reporter.output_dir = str(folder)
            self.reporter.generate_reports(str(uuid.uuid4()), result.dict())
        except Exception:
            logger.warning("Report generation failed", exc_info=True)

        return result

    # ------------------------------------------------------------
    async def analyze_multiple_files(self, file_paths: List[str], analysis_folder: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
        await self._ensure_initialized()
        if not file_paths:
            raise ValueError("No file paths provided")

        results: Dict[str, Any] = {}
        for fp in file_paths:
            res = await self.analyze_log_file(str(uuid.uuid4()), fp)
            results[Path(fp).name] = res.dict()

        folder = Path(analysis_folder or (self.batch_folder / str(uuid.uuid4())))
        folder.mkdir(parents=True, exist_ok=True)
        with open(folder / "multi_analysis.json", "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, default=str)
        console.log(f"[Multi] Saved all analyses to {folder}")

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
