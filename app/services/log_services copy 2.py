import asyncio
import os
import uuid
import json
import tempfile
import traceback
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import structlog
from fastapi.encoders import jsonable_encoder
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, ListFlowable, ListItem
from reportlab.lib.styles import getSampleStyleSheet

from app.models.log_analyzer_models import LogEntry, DateRangeFilter
from app.services.log_parser import LogParser
from app.services.compliance import ComplianceFilter
from app.services.generic_ai_connector import AIConnectorFactory

logger = structlog.get_logger(__name__)


class LogAnalyzerService:
    """
    Central Log Analyzer Service:
    - Async log parsing via LogParser
    - Compliance scanning
    - Sending log context + user question to AI via AIConnectorFactory
    """

    def __init__(self, provider_name: Optional[str] = None):
        self.parser = LogParser()
        self.compliance_filter = ComplianceFilter()
        self.ai_service = AIConnectorFactory.get_connector(provider_name)
        self.analysis_cache: Dict[str, Dict[str, Any]] = {}
        self._initialized = False

    # -------------------------------------------------------------------------
    # Initialization
    # -------------------------------------------------------------------------
    async def _ensure_initialized(self) -> None:
        if not self._initialized:
            await self.parser.initialize()
            await self.parser.health_check()
            await self.compliance_filter.initialize()
            await self.ai_service.initialize()
            self._initialized = True
            logger.info("LogAnalyzerService initialized")

    # -------------------------------------------------------------------------
    # Main log analysis
    # -------------------------------------------------------------------------
    async def analyze_log_file(
        self,
        analysis_id: str,
        file_path: str,
        date_filter: Optional[DateRangeFilter] = None,
        progress_tracker: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        await self._ensure_initialized()
        progress_tracker = progress_tracker or {}
        progress_tracker[analysis_id] = {"status": "running", "progress": 0, "message": ""}

        try:
            # 1️⃣ Read log file
            progress_tracker[analysis_id].update(message="Reading log file...", progress=5)
            with open(file_path, "r", encoding="utf-8") as f:
                log_data = f.read()

            # 2️⃣ Parse logs
            progress_tracker[analysis_id].update(message="Parsing logs...", progress=30)
            parse_result = await self.parser.parse_logs(log_data)
            entries: List[LogEntry] = parse_result.entries

            # 3️⃣ Apply date filter
            if date_filter:
                entries = self._filter_by_date(entries, date_filter)

            # 4️⃣ Recalculate statistics
            stats = self._recalculate_stats(entries)

            # 5️⃣ Compliance scan
            progress_tracker[analysis_id].update(message="Compliance scan...", progress=60)
            sample_text = "\n".join([e.message for e in entries[:100]])
            compliance_result = await self.compliance_filter.filter_data({"logs_sample": sample_text})

            # 6️⃣ Prepare AI analysis
            context_text = "\n".join([f"{e.timestamp} [{e.level}] {e.message}" for e in entries[:100]])
            prompt = f"Analyze the following log entries and summarize the problem:\n\n{context_text}"

            ai_analysis = await self.ai_service.generate_text({
                "prompt": prompt,
                "context": {"analysis_id": analysis_id},
                "max_tokens": 2000,
                "temperature": 0.3
            })

            raw_text = getattr(ai_analysis, "content", "") or ""
            logger.info("AI raw text retrieved", length=len(raw_text))

            # 7️⃣ Parse AI JSON output
            parsed_json = self._extract_json_from_ai(raw_text)

            # 8️⃣ Build final analysis dict
            analysis = {
                "id": analysis_id,
                "summary": parsed_json.get("summary", "No summary available"),
                "issue": parsed_json.get("issue", "Unknown issue"),
                "description": parsed_json.get("description", "No description"),
                "steps_to_resolve": self._ensure_ten_steps(parsed_json.get("steps_to_resolve")),
                "technical_details": parsed_json.get("technical_details", "N/A"),
                "complete_description": parsed_json.get("complete_description", "N/A"),
                "statistics": stats,
                "compliance": compliance_result
            }

            # 9️⃣ Save PDF, Markdown, JSON outputs
            pdf_path = await self._generate_pdf(analysis)
            md_path = await self._generate_md(analysis)
            json_path = await self._save_json_output(analysis)

            # 1️⃣0️⃣ Cache and finalize
            self.analysis_cache[analysis_id] = {"entries": entries, "analysis": analysis}
            progress_tracker[analysis_id].update(
                status="completed",
                progress=100,
                message="Analysis complete",
                results=analysis
            )

            return {
                "success": True,
                "analysis_id": analysis_id,
                "pdf_path": pdf_path,
                "md_path": md_path,
                "json_path": json_path,
                "analysis": analysis
            }

        except Exception as e:
            tb = traceback.format_exc()
            logger.error("Log analysis failed", error=str(e), traceback=tb)
            progress_tracker[analysis_id].update(status="error", progress=0, message=str(e))
            return {"status": "error", "message": str(e), "traceback": tb}

    # -------------------------------------------------------------------------
    # Filtering & stats helpers
    # -------------------------------------------------------------------------
    def _filter_by_date(self, entries: List[LogEntry], date_filter: Optional[DateRangeFilter] = None) -> List[LogEntry]:
        def parse_timestamp(ts: str | datetime) -> datetime:
            if isinstance(ts, datetime):
                return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
            if ts.endswith("Z"):
                ts = ts.replace("Z", "+00:00")
            dt = datetime.fromisoformat(ts)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

        start_raw = getattr(date_filter, "start_date", None) if date_filter else None
        end_raw = getattr(date_filter, "end_date", None) if date_filter else None

        if not start_raw and entries:
            start_raw = entries[0].timestamp
        if not end_raw and entries:
            end_raw = entries[-1].timestamp

        start = parse_timestamp(start_raw) if start_raw else None
        end = parse_timestamp(end_raw) if end_raw else None

        if not start or not end:
            return entries

        return [e for e in entries if e.timestamp and start <= parse_timestamp(e.timestamp) <= end]

    def _recalculate_stats(self, entries: List[LogEntry]) -> Dict[str, Any]:
        from collections import Counter, defaultdict
        level_dist = Counter(e.level for e in entries)
        hourly_dist = defaultdict(int)
        for e in entries:
            if e.timestamp:
                hourly_dist[e.timestamp.hour] += 1
        severity_scores = [getattr(e, "severity_score", 0) for e in entries]
        avg_severity = sum(severity_scores) / len(severity_scores) if severity_scores else 0
        high_severity_count = len([s for s in severity_scores if s >= 4])
        return {
            "total_entries": len(entries),
            "error_count": sum(1 for e in entries if e.level in ["ERROR", "CRITICAL"]),
            "level_distribution": dict(level_dist),
            "hourly_distribution": dict(hourly_dist),
            "severity_analysis": {"average_severity": avg_severity, "high_severity_count": high_severity_count},
            "entries": entries
        }

    def _extract_json_from_ai(self, raw_text: str) -> Dict[str, Any]:
        import re, json
        content = raw_text.replace("```json", "").replace("```", "").strip()
        start, end = content.find("{"), content.rfind("}")
        if start == -1 or end == -1 or end < start:
            return {}
        try:
            return json.loads(content[start:end + 1])
        except json.JSONDecodeError:
            parsed = {}
            steps_match = re.search(r'"steps_to_resolve"\s*:\s*\[(.*?)\]', content, re.DOTALL)
            if steps_match:
                parsed["steps_to_resolve"] = [s.strip().strip('"') for s in steps_match.group(1).split(",") if s.strip()]
            for field in ["summary", "issue", "description", "technical_details", "complete_description"]:
                m = re.search(rf'"{field}"\s*:\s*"([^"]*)"', content)
                parsed[field] = m.group(1) if m else None
            return parsed

    def _ensure_ten_steps(self, steps: Optional[List[str]]) -> List[str]:
        default_steps = [
            "Verify log and context details.",
            "Check system/network logs for errors.",
            "Identify recurring patterns or anomalies.",
            "Attempt to reproduce the issue if possible.",
            "Check configurations and recent changes.",
            "Run diagnostics or monitoring tools.",
            "Validate connectivity and performance.",
            "Apply temporary mitigation.",
            "Notify stakeholders and escalate as needed.",
            "Document root cause and corrective actions."
        ]
        if not steps or not isinstance(steps, list):
            steps = []
        cleaned_steps = [s.lstrip("0123456789. -") for s in steps]
        for step in default_steps:
            if len(cleaned_steps) >= 10:
                break
            if step not in cleaned_steps:
                cleaned_steps.append(step)
        return [f"Step {i+1}: {s}" for i, s in enumerate(cleaned_steps[:10])]

    # -------------------------------------------------------------------------
    # Output generation with filenames based on analysis_id
    # -------------------------------------------------------------------------
    async def _generate_pdf(self, analysis: Dict[str, Any]) -> str:
        try:
            pdf_dir = os.path.join(os.getcwd(), "output_pdf")
            os.makedirs(pdf_dir, exist_ok=True)
            pdf_path = os.path.join(pdf_dir, f"{analysis['id']}.pdf")

            doc = SimpleDocTemplate(pdf_path, pagesize=A4)
            styles = getSampleStyleSheet()
            elements = [
                Paragraph(f"<b>Issue:</b> {analysis.get('issue','')}", styles["Heading2"]),
                Paragraph(analysis.get('description',''), styles["Normal"]),
                Spacer(1, 12),
                Paragraph("<b>Steps to Resolve:</b>", styles["Heading3"]),
                ListFlowable([ListItem(Paragraph(str(s), styles["Normal"])) for s in analysis.get('steps_to_resolve', [])], bulletType="1"),
                Spacer(1, 12),
                Paragraph("<b>Technical Details:</b>", styles["Heading3"]),
                Paragraph(analysis.get('technical_details',''), styles["Normal"]),
                Spacer(1, 12),
                Paragraph("<b>Complete Description:</b>", styles["Heading3"]),
                Paragraph(analysis.get('complete_description',''), styles["Normal"])
            ]
            doc.build(elements)
            return pdf_path
        except Exception as e:
            logger.error("Failed to generate PDF", error=str(e))
            raise

    async def _generate_md(self, analysis: Dict[str, Any]) -> str:
        try:
            md_dir = os.path.join(os.getcwd(), "output_md")
            os.makedirs(md_dir, exist_ok=True)
            md_path = os.path.join(md_dir, f"{analysis['id']}.md")

            with open(md_path, "w", encoding="utf-8") as f:
                f.write(f"# Issue: {analysis.get('issue','')}\n\n")
                f.write(f"**Description:**\n{analysis.get('description','')}\n\n")
                f.write("**Steps to Resolve:**\n")
                for s in analysis.get('steps_to_resolve', []):
                    f.write(f"- {s}\n")
                f.write(f"\n**Technical Details:**\n{analysis.get('technical_details','')}\n\n")
                f.write(f"**Complete Description:**\n{analysis.get('complete_description','')}\n")

            return md_path
        except Exception as e:
            logger.error("Failed to generate Markdown file", error=str(e))
            raise

    async def _save_json_output(self, analysis: Dict[str, Any]) -> str:
        try:
            json_dir = os.path.join(os.getcwd(), "json_output")
            os.makedirs(json_dir, exist_ok=True)
            json_path = os.path.join(json_dir, f"{analysis['id']}.json")

            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(jsonable_encoder(analysis), f, indent=2, ensure_ascii=False)

            return json_path
        except Exception as e:
            logger.error("Failed to save JSON output", error=str(e))
            raise

    # -------------------------------------------------------------------------
    # AI Natural Query over past analysis
    # -------------------------------------------------------------------------
    # async def ai_natural_query(self, analysis_id: str, question: str, context_size: int = 100) -> Dict[str, Any]:
    #     """
    #     Perform AI-based natural language query on a previous analysis.
    #     """
    #     # 1️⃣ Load cached analysis
    #     results = self.analysis_cache.get(analysis_id)
    #     if not results:
    #         raise ValueError(f"No analysis found for ID {analysis_id}")

    #     # 2️⃣ Prepare context logs
    #     entries = results.get("entries", [])[:context_size]
    #     logs_text = "\n".join([f"{e.timestamp} [{e.level}] {e.message}" for e in entries])

    #     prompt = f"User question: {question}\n\nRelevant logs:\n{logs_text}\n\nAnswer concisely:"

    #     # 3️⃣ Call AI connector
    #     ai_response = await self.ai_service.generate_text({
    #         "prompt": prompt,
    #         "max_tokens": 500,
    #         "temperature": 0.3
    #     })

    #     # 4️⃣ Access AIResponse attributes directly
    #     raw_text = getattr(ai_response, "response_text", "")  # Use the actual field name in AIResponse
    #     confidence = getattr(ai_response, "confidence_score", None)

    #     return {
    #         "answer": raw_text.strip() if raw_text else "No insights found.",
    #         "context": [e.dict() for e in entries],  # convert LogEntry objects to dict
    #         "confidence": confidence
    #     }
    async def ai_natural_query(self, analysis_id: str, question: str, context_size: int = 100) -> Dict[str, Any]:
        """
        Perform AI-based natural language query on a previous log analysis,
        with debug output for prompt and response.
        """
        # 1️⃣ Load cached analysis
        results = self.analysis_cache.get(analysis_id)
        if not results:
            print(f"[DEBUG] No cached analysis found for ID: {analysis_id}")
            return {
                "analysis_id": analysis_id,
                "question": question,
                "answer": "No insights found.",
                "related_logs": [],
                "confidence": None,
                "timestamp": datetime.utcnow().isoformat()
            }

        # 2️⃣ Filter relevant logs
        entries = results.get("entries", [])
        keywords = [w.lower() for w in question.split() if len(w) > 3]
        related_logs = [
            e for e in entries
            if any(k in e.message.lower() for k in keywords)
        ][:context_size]

        logs_text = "\n".join([f"{e.timestamp} [{e.level}] {e.message}" for e in related_logs])

        # 3️⃣ Build AI prompt
        prompt = f"User question: {question}\n\nRelevant logs:\n{logs_text}\n\nAnswer concisely:"

        # 4️⃣ Print debug info
        print("\n[DEBUG] === AI Prompt Sent ===")
        print(prompt)
        print("[DEBUG] === End Prompt ===\n")

        # 5️⃣ Generate AI response
        ai_response = await self.ai_service.generate_text({
            "prompt": prompt,
            "max_tokens": 500,
            "temperature": 0.3
        })

        # 6️⃣ Extract response text
        raw_text = getattr(ai_response, "response_text", "")
        confidence = getattr(ai_response, "confidence_score", None)

        # 7️⃣ Print AI raw response
        print("\n[DEBUG] === AI Response Received ===")
        print(raw_text)
        print("[DEBUG] === End Response ===\n")

        return {
            "analysis_id": analysis_id,
            "question": question,
            "answer": raw_text.strip() if raw_text else "No insights found.",
            "related_logs": [e.dict() for e in related_logs],
            "confidence": confidence,
            "timestamp": datetime.utcnow().isoformat()
        }
