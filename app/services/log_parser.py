"""Log parser service with structured, async, progressive analysis."""
import re
from typing import List, Optional, Dict, Any
from datetime import datetime
from collections import defaultdict, Counter

import structlog
from app.abstracts.log_parser import BaseLogParser, LogEntry, LogPattern, LogLevel, ParseResult

logger = structlog.get_logger(__name__)


class LogParser(BaseLogParser):
    """Concrete log parser implementation."""

    def __init__(self):
        super().__init__()
        self.patterns = self._initialize_patterns()
        logger.info("LogParser initialized", pattern_count=len(self.patterns))

    # ------------------- Abstract methods implementations -------------------

    async def parse_logs(
        self,
        log_data: str,
        patterns: Optional[List[LogPattern]] = None
    ) -> ParseResult:
        patterns = patterns or self.patterns
        entries: List[LogEntry] = []
        parsing_errors: List[str] = []
        patterns_matched: Dict[str, int] = defaultdict(int)
        error_count = 0
        warning_count = 0

        for i, line in enumerate(log_data.splitlines(), 1):
            line = line.strip()
            if not line:
                continue
            try:
                entry = await self._parse_line(line, patterns)
                entries.append(entry)
                if entry.level == LogLevel.ERROR:
                    error_count += 1
                elif entry.level == LogLevel.WARNING:
                    warning_count += 1
                patterns_matched[entry.context.get("pattern_name", "default")] += 1
            except Exception as e:
                parsing_errors.append(f"Line {i}: {e}")
                logger.warning("Line parse error", line=line, error=str(e))

        return ParseResult(
            entries=entries,
            total_count=len(entries),
            error_count=error_count,
            warning_count=warning_count,
            patterns_matched=dict(patterns_matched),
            parsing_errors=parsing_errors
        )

    async def extract_errors(self, log_data: str) -> List[LogEntry]:
        result = await self.parse_logs(log_data)
        return [e for e in result.entries if e.level in [LogLevel.ERROR, LogLevel.CRITICAL]]

    async def analyze_patterns(self, log_entries: List[LogEntry]) -> Dict[str, Any]:
        levels = Counter(e.level for e in log_entries)
        sources = Counter(e.source for e in log_entries)
        messages = Counter(e.message for e in log_entries)
        timestamps = [e.timestamp for e in log_entries if e.timestamp]

        anomalies = await self._detect_anomalies(log_entries)

        return {
            "total_entries": len(log_entries),
            "level_distribution": dict(levels),
            "source_distribution": dict(sources),
            "common_messages": dict(messages.most_common(10)),
            "time_range": {"start": min(timestamps).isoformat() if timestamps else None,
                           "end": max(timestamps).isoformat() if timestamps else None},
            "anomalies": anomalies
        }

    async def filter_by_level(self, log_entries: List[LogEntry], min_level: LogLevel) -> List[LogEntry]:
        level_order = ["debug", "info", "warning", "error", "critical"]
        min_idx = level_order.index(min_level.value)
        return [e for e in log_entries if level_order.index(e.level.value) >= min_idx]

    async def search_logs(
        self,
        log_entries: List[LogEntry],
        query: str,
        fields: Optional[List[str]] = None
    ) -> List[LogEntry]:
        result = []
        for e in log_entries:
            searchable = []
            if not fields or "message" in fields:
                searchable.append(e.message)
            if not fields or "source" in fields:
                searchable.append(e.source)
            if any(query.lower() in s.lower() for s in searchable):
                result.append(e)
        return result

    def get_supported_patterns(self) -> List[LogPattern]:
        return self.patterns

    async def health_check(self) -> bool:
        """Dummy health check, always True."""
        return True

    async def initialize(self) -> None:
        """Optional async initialization."""
        logger.info("LogParser initialized and ready.")

    # ------------------- Internal helpers -------------------

    def _initialize_patterns(self) -> List[LogPattern]:
        return [
            LogPattern(
                name="standard_app_log",
                pattern=r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),(\d{3}) - (\w+) - (.+?) - (.+)",
                fields=["timestamp", "milliseconds", "level", "source", "message"],
                level=LogLevel.INFO,
                description="Standard application log format"
            ),
            LogPattern(
                name="error_log",
                pattern=r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) - ERROR - (.+?) - (.+)",
                fields=["timestamp", "source", "message"],
                level=LogLevel.ERROR,
                description="Error log format"
            ),
        ]

    async def _parse_line(self, line: str, patterns: List[LogPattern]) -> LogEntry:
        for pattern in patterns:
            match = re.match(pattern.pattern, line)
            if match:
                return await self._create_log_entry(pattern, match)
        # Fallback
        return LogEntry(timestamp=datetime.utcnow(), level=LogLevel.INFO,
                        message=line, source="unknown", context={"pattern_name": "unparsed"})

    async def _create_log_entry(self, pattern: LogPattern, match: re.Match) -> LogEntry:
        groups = match.groups()
        context = {"pattern_name": pattern.name}
        timestamp = datetime.utcnow()
        if "timestamp" in pattern.fields:
            idx = pattern.fields.index("timestamp")
            if idx < len(groups):
                timestamp = self._parse_timestamp(groups[idx])
        level = pattern.level
        if "level" in pattern.fields:
            idx = pattern.fields.index("level")
            if idx < len(groups):
                level = self._parse_level(groups[idx])
        source = groups[pattern.fields.index("source")] if "source" in pattern.fields else "unknown"
        message = groups[pattern.fields.index("message")] if "message" in pattern.fields else ""
        return LogEntry(timestamp=timestamp, level=level, source=source, message=message, context=context)

    def _parse_timestamp(self, text: str) -> datetime:
        formats = ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f"]
        for fmt in formats:
            try:
                return datetime.strptime(text, fmt)
            except ValueError:
                continue
        return datetime.utcnow()

    def _parse_level(self, text: str) -> LogLevel:
        mapping = {"debug": LogLevel.DEBUG, "info": LogLevel.INFO,
                   "warning": LogLevel.WARNING, "error": LogLevel.ERROR,
                   "critical": LogLevel.CRITICAL}
        return mapping.get(text.lower(), LogLevel.INFO)

    async def _detect_anomalies(self, log_entries: List[LogEntry]) -> List[Dict[str, Any]]:
        anomalies = []
        total = len(log_entries)
        errors = len([e for e in log_entries if e.level == LogLevel.ERROR])
        if total and errors / total > 0.1:
            anomalies.append({
                "type": "high_error_rate",
                "description": f"{errors} of {total} entries are errors",
                "severity": "high"
            })
        return anomalies
    
    async def process_log_file(self, file_path: str) -> Dict[str, Any]:
        """Read a file, parse logs, and return summary dict."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                log_data = f.read()

            parse_result = await self.parse_logs(log_data)

            return {
                "entries": parse_result.entries,
                "total_entries": parse_result.total_count,
                "error_count": parse_result.error_count,
                "warning_count": parse_result.warning_count,
                "patterns_matched": parse_result.patterns_matched,
                "parsing_errors": parse_result.parsing_errors,
            }
        except Exception as e:
            logger.error("Failed to process log file", error=str(e), exc_info=True)
            return {
                "entries": [],
                "total_entries": 0,
                "error_count": 0,
                "warning_count": 0,
                "patterns_matched": {},
                "parsing_errors": [str(e)],
            }
    
