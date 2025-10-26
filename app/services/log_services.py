# app/services/log_services.py

import os
import uuid
import json
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog
from rich.console import Console
from rich.panel import Panel
import pandas as pd

from app.models.log_analyzer_models import MultiLogAnalysis
from .log_parser import MultiFileLogParser
from .generic_ai_connector import AIConnectorFactory
from .report_generator import LogReportGenerator

logger = structlog.get_logger(__name__)
console = Console()


class LogAnalyzerService:
    """Service to parse logs, create DataFrame, and send first 100 rows to AI."""

    def __init__(self, provider_name: str = "openai", base_uploads: str = "data/uploads"):
        self.parser = MultiFileLogParser()
        self.ai_service = AIConnectorFactory.get_connector(provider_name)
        self.analysis_cache: Dict[str, Any] = {}
        self._initialized = False

        self.base_uploads = Path(base_uploads)
        self.base_dir = Path("outputs")
        self.base_dir.mkdir(parents=True, exist_ok=True)

        # Batch folder for current analysis
        batch_name = datetime.utcnow().strftime("%Y-%m-%d_%H-%M-%S")
        self.batch_folder = self.base_dir / batch_name
        self.batch_folder.mkdir(parents=True, exist_ok=True)

        self.reporter = LogReportGenerator(output_dir=str(self.batch_folder))
        console.log(f"[Init] Batch folder created: {self.batch_folder}")

    async def _ensure_initialized(self):
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
        """Extract raw text from AI response (OpenAI or Gemini style)."""
        raw_text = ""

        # Gemini format
        if hasattr(ai_response, "candidates") and ai_response.candidates:
            candidate = ai_response.candidates[0]
            parts = getattr(getattr(candidate, "content", {}), "parts", [])
            raw_text = "".join([getattr(p, "text", "") for p in parts if getattr(p, "text", None)]).strip()

        # Fallback: OpenAI-like format
        if not raw_text:
            raw_text = getattr(ai_response, "content", "") or ""

        return raw_text.strip()

    # -------------------------------------------------------------------
    async def analyze_latest_folder(self) -> MultiLogAnalysis:
        """Automatically detect the latest upload folder and analyze all files."""
        await self._ensure_initialized()

        # Detect latest timestamped folder
        folders = [f for f in self.base_uploads.iterdir() if f.is_dir()]
        if not folders:
            raise FileNotFoundError(f"No upload folders found in {self.base_uploads}")
        latest_folder = max(folders, key=lambda f: f.stat().st_mtime)
        console.log(f"[Step 0] Latest folder detected: {latest_folder}")

        # List all files inside latest folder
        file_paths = [str(f) for f in latest_folder.iterdir() if f.is_file()]
        if not file_paths:
            console.log("[Step 0] No files found in folder")
            return MultiLogAnalysis(
                analysis_id=str(uuid.uuid4()),
                overall_summary="No files found in latest folder.",
                aggregated_findings=[],
                highest_severity_overall=None,
                combined_events=[],
                individual_analyses=[]
            )

        console.log(f"[Step 0] Found {len(file_paths)} files: {file_paths}")

        # Delegate to analyze_multiple_files
        return await self.analyze_multiple_files(file_paths)

    # -------------------------------------------------------------------
    async def analyze_multiple_files(
        self,
        file_paths: List[str],
        analysis_folder: Optional[str | Path] = None
    ) -> MultiLogAnalysis:
        """Analyze a given list of files, generate DataFrame, send first 100 rows to AI."""
        await self._ensure_initialized()

        if not file_paths:
            raise ValueError("No file paths provided for analysis")

        console.log(f"[Step 0] Analyzing {len(file_paths)} files: {file_paths}")

        # Parse all files
        parse_results = await self.parser.parse_multiple_logs(file_paths)
        df = self.parser.logs_to_dataframe(parse_results)
        console.log(f"[Step 1] Parsed {len(df)} rows from {len(parse_results)} files")

        if df.empty:
            console.log("[Step 2] No logs found, returning empty analysis")
            return MultiLogAnalysis(
                analysis_id=str(uuid.uuid4()),
                overall_summary="No log entries found.",
                aggregated_findings=[],
                highest_severity_overall=None,
                combined_events=[],
                individual_analyses=[]
            )

        # Prepare first 100 rows for AI
        combined_text = "\n".join(df["message"].tolist()[:100])
        console.log("[Step 3] Combined text prepared for AI (first 100 rows)")

        prompt = f"Analyze the following log entries (first 100 rows) and return structured JSON:\n{combined_text}"

        ai_request = {
            "prompt": prompt,
            "context": {"analysis_type": "log_analysis"},
            "max_tokens": 2000,
            "temperature": 0.3
        }

        # Send to AI
        try:
            ai_response = await self.ai_service.generate_text(ai_request)
            raw_text = await self._extract_ai_text(ai_response)
            try:
                structured_data = json.loads(raw_text)
                result = MultiLogAnalysis(**structured_data)
            except Exception:
                result = MultiLogAnalysis(
                    analysis_id=str(uuid.uuid4()),
                    overall_summary=raw_text.strip() or "AI returned no structured data",
                    aggregated_findings=[],
                    highest_severity_overall=None,
                    combined_events=[],
                    individual_analyses=[]
                )
        except Exception as e:
            logger.error("AI analysis failed", error=str(e), traceback=traceback.format_exc())
            result = MultiLogAnalysis(
                analysis_id=str(uuid.uuid4()),
                overall_summary="AI analysis failed.",
                aggregated_findings=[],
                highest_severity_overall=None,
                combined_events=[],
                individual_analyses=[]
            )

        # Save JSON + generate reports
        folder = Path(analysis_folder) if analysis_folder else self.batch_folder / result.analysis_id
        folder.mkdir(parents=True, exist_ok=True)
        json_path = folder / f"analysis_{result.analysis_id}.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(result.dict(), f, indent=2)
        console.log(f"[Step 4] Analysis JSON saved: {json_path}")

        self.reporter.output_dir = str(folder)
        self.reporter.generate_reports(result.analysis_id, result.dict())
        console.log(f"[Step 5] Reports generated in folder: {folder}")

        return result


# -----------------------------
# STRESSED Printer
# -----------------------------
class StressedPrinter:
    """Print STRESSED-style console report"""

    def print_summary(self, analysis: MultiLogAnalysis):
        panel_text = f"""
😰 STRESSED (STRuctured Generation Security System Evaluating Data) 😰

Summary: {analysis.overall_summary}

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
