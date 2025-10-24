import asyncio
import os
import traceback
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

import structlog

from app.models.log_analyzer_models import DateRangeFilter



from .log_parser import LogParser, LogEntry
from .compliance import ComplianceFilter
from .generic_ai_connector import AIConnectorFactory

logger = structlog.get_logger(__name__)


class LogAnalyzerService:
    """
    Central Log Analyzer Service:
    - Async log parsing via LogParser
    - Compliance scanning
    - Sending log context + user question to OpenAI via AIConnectorFactory
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
        date_filter: Optional[Dict[str, Any]] = None,
        progress_tracker: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        await self._ensure_initialized()
        progress_tracker = progress_tracker or {}
        progress_tracker[analysis_id] = {"status": "running", "progress": 0, "message": ""}

        try:
            progress_tracker[analysis_id].update(message="Reading log file...", progress=5)
            with open(file_path, "r", encoding="utf-8") as f:
                log_data = f.read()

            progress_tracker[analysis_id].update(message="Parsing logs...", progress=30)
            parse_result = await self.parser.parse_logs(log_data)
            entries: List[LogEntry] = parse_result.entries

            # Apply date filter if provided
            if date_filter:
                entries = self._filter_by_date(entries, date_filter)

            # Recalculate statistics
            stats = self._recalculate_stats(entries)

            progress_tracker[analysis_id].update(message="Compliance scan...", progress=60)
            sample_text = "\n".join([e.message for e in entries[:100]])
            compliance_result = await self.compliance_filter.filter_data({"logs_sample": sample_text})

            # Compose final results
            results = {
                "analysis_id": analysis_id,
                "timestamp": datetime.utcnow().isoformat(),
                "summary": self._generate_summary(stats, compliance_result),
                "statistics": stats,
                "compliance": compliance_result,
            }

            # Cache entries for queries
            self.analysis_cache[analysis_id] = {"entries": entries, "results": results}

            progress_tracker[analysis_id].update(
                status="completed",
                progress=100,
                message="Analysis complete",
                results=results
            )
            return results

        except Exception as e:
            tb = traceback.format_exc()
            logger.error("Log analysis failed", error=str(e), traceback=tb)
            progress_tracker[analysis_id].update(status="error", progress=0, message=str(e))
            return {"status": "error", "message": str(e), "traceback": tb}

    # -------------------------------------------------------------------------
    # Filtering & stats helpers
    # -------------------------------------------------------------------------

    def _filter_by_date(
        self, 
        entries: List[LogEntry], 
        date_filter: Optional[DateRangeFilter] = None
    ) -> List[LogEntry]:
        """
        Filter log entries by start and end date.
        - If `date_filter` is None, uses first and last entry timestamps.
        """

        def parse_timestamp(ts: str | datetime) -> datetime:
            """Convert string or datetime to timezone-aware UTC datetime."""
            if isinstance(ts, datetime):
                return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
            if ts.endswith("Z"):
                ts = ts.replace("Z", "+00:00")
            dt = datetime.fromisoformat(ts)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

        # Access attributes directly since date_filter is a Pydantic model
        start_raw = getattr(date_filter, "start_date", None) if date_filter else None
        end_raw = getattr(date_filter, "end_date", None) if date_filter else None

        # Use first and last entry timestamps if not provided
        if not start_raw and entries:
            start_raw = entries[0].timestamp
        if not end_raw and entries:
            end_raw = entries[-1].timestamp

        start = parse_timestamp(start_raw) if start_raw else None
        end = parse_timestamp(end_raw) if end_raw else None

        if not start or not end:
            return entries

        # Filter entries
        filtered_entries = [
            e for e in entries
            if e.timestamp and start <= parse_timestamp(e.timestamp) <= end
        ]

        return filtered_entries

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

    def _generate_summary(self, stats: Dict[str, Any], compliance_result: Any) -> Dict[str, Any]:
        error_rate = (stats["error_count"] / stats["total_entries"] * 100) if stats["total_entries"] else 0
        return {
            "total_entries": stats["total_entries"],
            "error_count": stats["error_count"],
            "error_rate": round(error_rate, 2),
            "critical_errors": stats["severity_analysis"]["high_severity_count"],
            "average_severity": round(stats["severity_analysis"]["average_severity"], 2),
            "compliance_score": getattr(compliance_result, "compliance_score", 0),
            "compliance_status": "PASS" if getattr(compliance_result, "compliance_score", 0) >= 0.7 else "REVIEW",
        }

    # -------------------------------------------------------------------------
    # Send logs + question to OpenAI via AIConnectorFactory
    # -------------------------------------------------------------------------
    async def ai_natural_query(self, analysis_id: str, question: str, context_size: int = 100) -> Dict[str, Any]:
        """
        Perform AI-based query over a previously analyzed log.

        Args:
            analysis_id: ID of completed log analysis
            question: User question about logs
            context_size: Number of relevant log entries to include

        Returns:
            Dict with AI answer, context logs, and optional confidence
        """
        # --- 1️⃣ Load analysis results ---
        from app.api.v1.endpoints.log_analyzer import analysis_results, PERSIST_DIR
        import json
        from pathlib import Path

        results = analysis_results.get(analysis_id)
        if not results:
            path = PERSIST_DIR / f"{analysis_id}.json"
            if path.exists():
                with open(path, "r", encoding="utf-8") as fh:
                    results = json.load(fh)
            else:
                raise ValueError(f"No results found for analysis_id {analysis_id}")

        # --- 2️⃣ Prepare context logs ---
        context_logs = results.get("top_errors", []) + results.get("top_warnings", [])
        context_logs = context_logs[:context_size]

        logs_text = "\n".join(
            [f"{entry['timestamp']} [{entry['level']}] {entry['message']}" for entry in context_logs]
        )

        prompt = f"User question: {question}\n\nRelevant logs:\n{logs_text}\n\nAnswer concisely:"

        # --- 3️⃣ Call AI connector ---
        ai_response = await asyncio.to_thread(
            self.ai_service.chat_completion,  # must exist in your OpenAIConnector
            prompt,
            max_tokens=500
        )

        # --- 4️⃣ Return structured response ---
        return {
            "answer": ai_response.get("text", "No insights found."),
            "context": context_logs,
            "confidence": ai_response.get("confidence", None)
        }
