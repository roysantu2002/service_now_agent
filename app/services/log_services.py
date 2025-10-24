import asyncio
import os
import uuid
import json
import tempfile
import traceback
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import pandas as pd
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
    Central Log Analyzer Service
    - Parses logs asynchronously
    - Runs compliance scanning
    - Sends log context + user question to AI
    - Generates PDF, Markdown, and JSON reports (named after analysis_id)
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
            logger.info("LogAnalyzerService initialized successfully")

    # -------------------------------------------------------------------------
    # Main Log Analysis
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
            # 1️⃣ Read file
            progress_tracker[analysis_id].update(message="Reading log file...", progress=5)
            with open(file_path, "r", encoding="utf-8") as f:
                log_data = f.read()

            # 2️⃣ Parse logs
            progress_tracker[analysis_id].update(message="Parsing logs...", progress=25)
            parse_result = await self.parser.parse_logs(log_data)
            entries: List[LogEntry] = parse_result.entries

            # 3️⃣ Apply date filter or infer automatically
            if date_filter:
                entries = self._filter_by_date(entries, date_filter)
            elif entries:
                start_date, end_date = entries[0].timestamp, entries[-1].timestamp
                date_filter = DateRangeFilter(start_date=start_date, end_date=end_date)
                entries = self._filter_by_date(entries, date_filter)

            # 4️⃣ Stats
            stats = self._recalculate_stats(entries)

            # 5️⃣ Compliance scan
            progress_tracker[analysis_id].update(message="Running compliance checks...", progress=50)
            sample_text = "\n".join([e.message for e in entries[:100]])
            compliance_result = await self.compliance_filter.filter_data({"logs_sample": sample_text})

            # 6️⃣ Prepare AI prompt
            context_text = "\n".join([f"{e.timestamp} [{e.level}] {e.message}" for e in entries[:100]])
            prompt = f"Analyze the following log entries and summarize the main problem:\n\n{context_text}"

            logger.info("AI PROMPT PREVIEW", analysis_id=analysis_id, prompt=prompt)

            ai_analysis = await self.ai_service.generate_text({
                "prompt": prompt,
                "context": {"analysis_id": analysis_id},
                "max_tokens": 2000,
                "temperature": 0.3
            })

            raw_text = getattr(ai_analysis, "content", "") or ""
            logger.info("AI RAW RESPONSE RECEIVED", analysis_id=analysis_id, length=len(raw_text))
            logger.debug("AI RESPONSE TEXT", response=raw_text[:2000])

            # 7️⃣ Parse AI JSON
            parsed_json = self._extract_json_from_ai(raw_text)

            # 8️⃣ Assemble final analysis
            analysis = {
                "id": analysis_id,
                "summary": parsed_json.get("summary", "No summary"),
                "issue": parsed_json.get("issue", "Unknown issue"),
                "description": parsed_json.get("description", "No description"),
                "steps_to_resolve": self._ensure_ten_steps(parsed_json.get("steps_to_resolve")),
                "technical_details": parsed_json.get("technical_details", "N/A"),
                "complete_description": parsed_json.get("complete_description", "N/A"),
                "statistics": stats,
                "compliance": compliance_result,
                "date_range": {
                    "start_date": str(date_filter.start_date),
                    "end_date": str(date_filter.end_date)
                }
            }

            # 9️⃣ Generate outputs
            pdf_path = await self._generate_pdf(analysis)
            md_path = await self._generate_md(analysis)
            json_path = await self._save_json_output(analysis)

            # 🔟 Cache result
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
    # Helper: Filter by date (auto infer if missing)
    # -------------------------------------------------------------------------
    def _filter_by_date(self, entries: List[LogEntry], date_filter: Optional[DateRangeFilter]) -> List[LogEntry]:
        def parse_ts(ts):
            if isinstance(ts, datetime):
                return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
            if isinstance(ts, str):
                if ts.endswith("Z"):
                    ts = ts.replace("Z", "+00:00")
                dt = datetime.fromisoformat(ts)
                return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
            return datetime.now(timezone.utc)

        start_raw = getattr(date_filter, "start_date", None)
        end_raw = getattr(date_filter, "end_date", None)

        if not start_raw and entries:
            start_raw = entries[0].timestamp
        if not end_raw and entries:
            end_raw = entries[-1].timestamp

        start, end = parse_ts(start_raw), parse_ts(end_raw)
        return [e for e in entries if e.timestamp and start <= parse_ts(e.timestamp) <= end]

    # -------------------------------------------------------------------------
    # Helper: Stats recalculation
    # -------------------------------------------------------------------------
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
        }

    # -------------------------------------------------------------------------
    # Helper: Parse AI JSON safely
    # -------------------------------------------------------------------------
    def _extract_json_from_ai(self, raw_text: str) -> Dict[str, Any]:
        import re, json
        text = raw_text.replace("```json", "").replace("```", "").strip()
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end == -1 or end < start:
            return {}
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            parsed = {}
            for key in ["summary", "issue", "description", "technical_details", "complete_description"]:
                m = re.search(rf'"{key}"\s*:\s*"([^"]+)"', text)
                parsed[key] = m.group(1) if m else None
            return parsed

    # -------------------------------------------------------------------------
    # Helper: Ensure steps completeness
    # -------------------------------------------------------------------------
    def _ensure_ten_steps(self, steps: Optional[List[str]]) -> List[str]:
        default_steps = [
            "Verify log and context details.",
            "Check configurations and recent changes.",
            "Reproduce the issue if possible.",
            "Run diagnostics and validate logs.",
            "Investigate network/system dependencies.",
            "Apply temporary mitigation steps.",
            "Monitor the impact post mitigation.",
            "Escalate to relevant teams if unresolved.",
            "Document RCA and lessons learned.",
            "Implement preventive measures."
        ]
        if not steps or not isinstance(steps, list):
            steps = []
        cleaned = [s.strip("0123456789.- ") for s in steps]
        for step in default_steps:
            if len(cleaned) >= 10:
                break
            if step not in cleaned:
                cleaned.append(step)
        return [f"Step {i+1}: {s}" for i, s in enumerate(cleaned[:10])]

    # -------------------------------------------------------------------------
    # Output Generators (Named by analysis_id)
    # -------------------------------------------------------------------------
    async def _generate_pdf(self, analysis: Dict[str, Any]) -> str:
        pdf_dir = os.path.join(os.getcwd(), "output_pdf")
        os.makedirs(pdf_dir, exist_ok=True)
        pdf_path = os.path.join(pdf_dir, f"{analysis['id']}.pdf")

        try:
            doc = SimpleDocTemplate(pdf_path, pagesize=A4)
            styles = getSampleStyleSheet()
            elements = [
                Paragraph(f"<b>Issue:</b> {analysis.get('issue','')}", styles["Heading2"]),
                Paragraph(analysis.get('description',''), styles["Normal"]),
                Spacer(1, 12),
                Paragraph("<b>Steps to Resolve:</b>", styles["Heading3"]),
                ListFlowable([ListItem(Paragraph(s, styles["Normal"])) for s in analysis.get('steps_to_resolve', [])], bulletType="1"),
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
            logger.error("PDF generation failed", error=str(e))
            raise

    async def _generate_md(self, analysis: Dict[str, Any]) -> str:
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

    async def _save_json_output(self, analysis: Dict[str, Any]) -> str:
        json_dir = os.path.join(os.getcwd(), "json_output")
        os.makedirs(json_dir, exist_ok=True)
        json_path = os.path.join(json_dir, f"{analysis['id']}.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(jsonable_encoder(analysis), f, indent=2, ensure_ascii=False)
        return json_path

    # -------------------------------------------------------------------------
    # Natural Query with prompt + context + response logging
    # -------------------------------------------------------------------------
    async def _prepare_ai_prompt(self, log_entries: List[LogEntry], question: str, context_size: int = 50):
        df = pd.DataFrame([{
            "timestamp": e.timestamp.isoformat() if e.timestamp else None,
            "level": e.level,
            "source": getattr(e, "source", ""),
            "message": e.message
        } for e in log_entries])

        keywords = [w.lower() for w in question.split() if len(w) > 3]
        mask = df["message"].str.lower().apply(lambda m: any(k in m for k in keywords))
        filtered = df[mask].head(context_size)

        logs_text = "\n".join(
            [f"{r['timestamp']} [{r['level']}] {r['source']}: {r['message']}" for _, r in filtered.iterrows()]
        )
        prompt = f"User question: {question}\n\nRelevant logs:\n{logs_text}\n\nAnswer concisely:"

        logger.info("AI PROMPT BUILT FOR QUERY", question=question, prompt=prompt)
        return prompt, filtered

    async def ai_natural_query(self, log_data: str, question: str, context_size: int = 50) -> Dict[str, Any]:
        """
        Perform AI-powered log analysis given raw log text and a natural language question.
        It prints the parsed DataFrame, builds a contextual prompt, sends it to AI, and returns the structured result.
        """
        try:
            # Step 1: Parse logs
            parsed = await self.parser.parse_logs(log_data)
            entries = parsed.entries

            if not entries:
                logger.warning("No log entries found for analysis")
                return {"success": False, "error": "No log entries found"}

            df = pd.DataFrame([e.__dict__ for e in entries])
            start_dt = pd.to_datetime(df["timestamp"].min())
            end_dt = pd.to_datetime(df["timestamp"].max())
            logger.info("Determined log date range", extra={"start": str(start_dt), "end": str(end_dt)})

            # 🔍 Step 2: Print the DataFrame for debugging
            logger.info("Parsed Log DataFrame preview:")
            logger.info("\n" + df.to_string(max_rows=10, index=False))

            # Step 3: Select the last N context logs
            filtered_df = df.tail(context_size)

            # Print filtered DataFrame
            logger.info("Filtered log context (last %d lines):", context_size)
            logger.info("\n" + filtered_df.to_string(max_rows=20, index=False))

            # Step 4: Build AI input context text
            context_text = "\n".join(
                f"{row['timestamp']} [{row['level']}] {row.get('component', 'unknown')}: {row.get('message', '')}"
                for _, row in filtered_df.iterrows()
            )

            # Step 5: Build the AI prompt
            prompt = f"""
You are a senior site reliability engineer.
Analyze the following application logs and answer the user's question.

Question:
{question}

Relevant logs (between {start_dt} and {end_dt}):
{context_text}

Instructions:
- Identify patterns, errors, or warnings relevant to the question.
- Suggest probable root cause and impacted components.
- Respond only in JSON with keys:
  "summary", "root_cause", "probable_service", "recommendations".
"""
            logger.info("AI PROMPT BUILT FOR QUERY", extra={"question": question, "lines": len(filtered_df)})
            logger.debug(f"PROMPT SENT TO AI:\n{prompt}")

            # Step 6: Call AI
            ai_resp = await self.ai_service.generate_text({
                "prompt": prompt,
                "max_tokens": 1500,
                "temperature": 0.2
            })

            # Step 7: Extract raw text safely
            raw_text = getattr(ai_resp, "content", "") or getattr(ai_resp, "text", "") or str(ai_resp)
            logger.info("AI RAW RESPONSE RECEIVED", extra={"length": len(raw_text)})
            logger.debug(f"AI RAW RESPONSE:\n{raw_text}")

            # Step 8: Parse AI JSON
            parsed_output = self._extract_json_from_ai(raw_text)
            if not parsed_output:
                logger.warning("AI response not in expected JSON format, returning raw text")
                parsed_output = {
                    "summary": raw_text.strip(),
                    "root_cause": None,
                    "probable_service": None,
                    "recommendations": None
                }

            return {
                "success": True,
                "question": question,
                "prompt": prompt,
                "context_logs": filtered_df.to_dict(orient="records"),
                "ai_raw_text": raw_text,
                "ai_response": parsed_output,
                "parsing_summary": {
                    "total": parsed.total_count,
                    "errors": parsed.error_count,
                    "warnings": parsed.warning_count
                }
            }

        except Exception as e:
            tb = traceback.format_exc()
            logger.error("AI natural query failed", extra={"error": str(e), "traceback": tb})
            return {"success": False, "error": str(e), "traceback": tb}

    def _extract_json_from_ai(self, text: str) -> Dict[str, Any]:
            """Extract JSON block from AI response text."""
            import json, re
            try:
                match = re.search(r"\{[\s\S]*\}", text)
                if match:
                    return json.loads(match.group(0))
            except Exception as e:
                logger.warning("Failed to parse AI JSON", extra={"error": str(e)})
            return {}