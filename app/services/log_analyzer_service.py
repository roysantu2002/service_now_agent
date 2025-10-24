import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import sys
import os
import json
import pandas as pd
from pathlib import Path
import structlog

# Add parent directory to path to import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from .log_parser import LogParser, LogEntry
from .compliance import ComplianceFilter
from .rag_search import LangChainRAG
from .ai_integration import SecureAIIntegration
from .generic_ai_connector import AIConnectorFactory

logger = structlog.get_logger(__name__)


class LogAnalyzerService:
    """
    Unified log analysis service that integrates:
      - Parsing
      - Compliance
      - RAG search
      - AI insights (via generic AI connector)
      - Structured CSV/JSON persistence
    """

    def __init__(self):
        self.parser = LogParser()
        self.compliance_filter = ComplianceFilter()
        self.rag_engine = LangChainRAG()
        self.ai_integration = SecureAIIntegration()
        self.ai_integration.rag_engine = self.rag_engine

        self.analysis_cache = {}
        self.persist_dir = Path(os.environ.get("LOG_ANALYSIS_PERSIST_DIR", "data/analysis_store"))
        self.persist_dir.mkdir(parents=True, exist_ok=True)

        # --- Initialize generic AI connector (OpenAI / Gemini / others)
        try:
            self.ai_connector = AIConnectorFactory.get_connector()
            logger.info("✅ Generic AI connector initialized", connector=type(self.ai_connector).__name__)
        except Exception as e:
            logger.warning("⚠️ Failed to initialize AI connector", error=str(e))
            self.ai_connector = None

    # ---------------------------------------------------------------------
    # Core Analysis
    # ---------------------------------------------------------------------
    async def analyze_log_file(
        self,
        analysis_id: str,
        file_path: str,
        date_filter: Optional[Dict],
        task: Dict
    ):
        print(f"[DEBUG] ▶️ analyze_log_file() called for {analysis_id}")
        try:
            task.update({"message": "Parsing log entries...", "progress": 10, "status": "processing"})
            logger.info("Parsing log file", file=file_path)

            analysis_result = await asyncio.to_thread(self.parser.process_log_file, file_path)
            entries = analysis_result["entries"]
            print(f"[DEBUG] Parsed {len(entries)} entries")

            # --- Date filtering ---
            if date_filter:
                print(f"[DEBUG] Applying date filter: {date_filter}")
                entries = self._filter_by_date_range(entries, date_filter)
                analysis_result = self._recalculate_stats(entries)
                print(f"[DEBUG] After filtering, entries={len(entries)}")

            task.update({"message": "Building search index...", "progress": 40})
            print(f"[DEBUG] Building RAG index for {len(entries)} entries")
            await asyncio.to_thread(self.rag_engine.index_log_entries, entries)

            task.update({"message": "Performing compliance scan...", "progress": 60})
            print("[DEBUG] Running compliance scan...")
            sample_text = "\n".join([e.raw_line for e in entries[:100]])
            compliance_findings = await asyncio.to_thread(self.compliance_filter.scan_for_sensitive_data, sample_text)
            print(f"[DEBUG] Compliance results: {json.dumps(compliance_findings, indent=2)}")

            task.update({"message": "Analyzing error patterns...", "progress": 80})
            print("[DEBUG] Analyzing error patterns...")
            pattern_analysis = await asyncio.to_thread(self.rag_engine.analyze_error_patterns, entries)
            print(f"[DEBUG] Pattern analysis done with {len(pattern_analysis) if pattern_analysis else 0} patterns")

            # --- AI Summary via Generic Connector ---
            ai_summary = None
            if self.ai_connector:
                print("[DEBUG] Generating AI summary using generic connector...")
                task["message"] = "Generating AI summary..."
                df = pd.DataFrame([vars(e) for e in entries[:200]])

                prompt = (
                    "You are an expert log analyst. Analyze the following logs and summarize "
                    "the most frequent issues, potential root causes, and any anomalies detected.\n\n"
                    "Provide a concise, actionable summary."
                )
                ai_summary = await asyncio.to_thread(self._query_ai_connector, prompt, df)
                print(f"[DEBUG] AI summary result: {ai_summary[:200]}...")
            else:
                print("[DEBUG] AI connector unavailable, skipping AI summary.")

            # --- Final results ---
            task.update({"message": "Preparing report...", "progress": 90})
            print("[DEBUG] Preparing final report and summary...")
            results = {
                "analysis_id": analysis_id,
                "timestamp": datetime.now().isoformat(),
                "summary": self._generate_summary(analysis_result, compliance_findings),
                "statistics": analysis_result,
                "compliance": compliance_findings,
                "patterns": pattern_analysis,
                "ai_summary": ai_summary or "AI summary unavailable",
                "top_errors": analysis_result.get("top_errors", []),
            }

            self._save_results(analysis_id, results, entries)
            print(f"[DEBUG] Results persisted successfully for {analysis_id}")

            task.update({
                "status": "completed",
                "progress": 100,
                "message": "Analysis complete",
                "results": results
            })
            print(f"[DEBUG] ✅ Analysis completed successfully for {analysis_id}")

        except Exception as e:
            print(f"[ERROR] ❌ analyze_log_file() failed for {analysis_id}: {e}")
            logger.exception("Analysis failed", analysis_id=analysis_id, error=str(e))
            task.update({
                "status": "error",
                "message": f"Error: {str(e)}",
                "progress": 0
            })

    # ---------------------------------------------------------------------
    # AI Connector Wrapper
    # ---------------------------------------------------------------------
    def _query_ai_connector(self, prompt: str, df: pd.DataFrame) -> str:
        """Send structured data to AI model through generic connector"""
        try:
            text_preview = df.head(30).to_string(index=False)
            user_prompt = f"{prompt}\n\nLogs:\n{text_preview}"

            ai_request = {
                "prompt": user_prompt,
                "temperature": 0.2,
                "max_tokens": 800,
            }

            response = self.ai_connector.generate(ai_request)
            if isinstance(response, dict) and "text" in response:
                return response["text"].strip()
            elif hasattr(response, "content"):
                return response.content.strip()
            else:
                return str(response)[:1000]

        except Exception as e:
            logger.warning("AI summary generation failed", error=str(e))
            return f"[AI summary error: {e}]"

    # ---------------------------------------------------------------------
    # Utility & Helper Methods
    # ---------------------------------------------------------------------
    def _save_results(self, analysis_id: str, results: Dict[str, Any], entries: List[LogEntry]):
        """Persist structured data and results"""
        try:
            json_path = self.persist_dir / f"{analysis_id}.json"
            csv_path = self.persist_dir / f"{analysis_id}_structured.csv"

            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(results, f, default=str, indent=2)

            df = pd.DataFrame([vars(e) for e in entries])
            df.to_csv(csv_path, index=False)

            self.analysis_cache[analysis_id] = {"results": results, "entries": entries}
        except Exception as e:
            logger.warning("Failed to persist results", error=str(e))

    def _filter_by_date_range(self, entries: List[LogEntry], date_filter: Dict) -> List[LogEntry]:
        """Filter logs within a time window or explicit date range"""
        if not date_filter:
            return entries

        if "time_period" in date_filter and date_filter["time_period"]:
            end = date_filter.get("end_date", datetime.now())
            if isinstance(end, str):
                end = datetime.fromisoformat(end)
            start = end - timedelta(hours=date_filter["time_period"])
        else:
            start = date_filter.get("start_date")
            end = date_filter.get("end_date")
            if isinstance(start, str):
                start = datetime.fromisoformat(start)
            if isinstance(end, str):
                end = datetime.fromisoformat(end)

        filtered = []
        for e in entries:
            try:
                ts = datetime.fromisoformat(e.timestamp[:19])
                if start <= ts <= end:
                    filtered.append(e)
            except Exception:
                continue
        return filtered

    def _recalculate_stats(self, entries: List[LogEntry]) -> Dict:
        """Compute statistics again after filtering"""
        from collections import Counter, defaultdict

        levels = Counter(e.level for e in entries)
        cats = Counter(e.category for e in entries)
        hourly = defaultdict(int)
        errors = sum(1 for e in entries if e.level in ["ERROR", "CRITICAL", "FATAL"])

        for e in entries:
            try:
                ts = datetime.fromisoformat(e.timestamp[:19])
                hourly[ts.hour] += 1
            except:
                continue

        severities = [e.severity_score for e in entries]
        avg_sev = sum(severities) / len(severities) if severities else 0
        high_sev = sum(1 for s in severities if s >= 4)

        return {
            "total_entries": len(entries),
            "error_count": errors,
            "level_distribution": dict(levels),
            "category_distribution": dict(cats),
            "hourly_distribution": dict(hourly),
            "severity_analysis": {
                "average_severity": avg_sev,
                "high_severity_count": high_sev,
                "distribution": dict(Counter(severities))
            }
        }

    def _generate_summary(self, analysis: Dict, compliance: Dict) -> Dict:
        total = analysis["total_entries"]
        error_rate = (analysis["error_count"] / total * 100) if total > 0 else 0
        risk_score = compliance.get("risk_score", 0)
        return {
            "total_entries": total,
            "error_count": analysis["error_count"],
            "error_rate": round(error_rate, 2),
            "critical_errors": analysis["severity_analysis"]["high_severity_count"],
            "avg_severity": round(analysis["severity_analysis"]["average_severity"], 2),
            "compliance_status": self._get_compliance_status(risk_score),
            "violations_found": len(compliance.get("compliance_violations", [])),
        }

    def _get_compliance_status(self, risk_score: int) -> str:
        if risk_score > 50:
            return "HIGH_RISK"
        elif risk_score > 20:
            return "MEDIUM_RISK"
        return "LOW_RISK"
