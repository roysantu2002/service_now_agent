"""Log parser service implementation."""
import re
import structlog
from typing import Dict, Any, List, Optional, Iterator
from datetime import datetime
from collections import defaultdict

from app.abstracts.log_parser import (
    BaseLogParser,
    LogEntry,
    LogLevel,
    LogPattern,
    ParseResult
)

logger = structlog.get_logger(__name__)


class LogParser(BaseLogParser):
    """Log parser service implementation."""
    
    def __init__(self):
        super().__init__()
        self.patterns = self._initialize_patterns()
    
    async def initialize(self) -> None:
        """Initialize the log parser."""
        logger.info("Log parser initialized", pattern_count=len(self.patterns))
    
    async def health_check(self) -> bool:
        """Check if the log parser is healthy."""
        return True
    
    async def parse_logs(
        self, 
        log_data: str,
        patterns: Optional[List[LogPattern]] = None
    ) -> ParseResult:
        """Parse log data and extract structured information."""
        start_time = datetime.now()
        
        # Use provided patterns or default ones
        parse_patterns = patterns or self.patterns
        
        entries = []
        parsing_errors = []
        patterns_matched = defaultdict(int)
        error_count = 0
        warning_count = 0
        
        logger.info("Starting log parsing", 
                   data_size=len(log_data),
                   pattern_count=len(parse_patterns))
        
        # Split log data into lines
        lines = log_data.strip().split('\n')
        
        for line_num, line in enumerate(lines, 1):
            if not line.strip():
                continue
            
            try:
                entry = await self._parse_line(line, parse_patterns)
                if entry:
                    entries.append(entry)
                    
                    # Count by level
                    if entry.level == LogLevel.ERROR:
                        error_count += 1
                    elif entry.level == LogLevel.WARNING:
                        warning_count += 1
                    
                    # Track pattern matches
                    pattern_name = entry.context.get('pattern_name') if entry.context else 'default'
                    patterns_matched[pattern_name] += 1
                
            except Exception as e:
                parsing_errors.append(f"Line {line_num}: {str(e)}")
                logger.warning("Error parsing log line", 
                              line_num=line_num, 
                              error=str(e))
        
        processing_time = (datetime.now() - start_time).total_seconds()
        
        result = ParseResult(
            entries=entries,
            total_count=len(entries),
            error_count=error_count,
            warning_count=warning_count,
            patterns_matched=dict(patterns_matched),
            parsing_errors=parsing_errors
        )
        
        logger.info("Log parsing completed",
                   total_entries=len(entries),
                   error_count=error_count,
                   warning_count=warning_count,
                   processing_time=processing_time)
        
        return result
    
    async def extract_errors(self, log_data: str) -> List[LogEntry]:
        """Extract error entries from log data."""
        parse_result = await self.parse_logs(log_data)
        return [entry for entry in parse_result.entries if entry.level == LogLevel.ERROR]
    
    async def analyze_patterns(self, log_entries: List[LogEntry]) -> Dict[str, Any]:
        """Analyze log entries for patterns and anomalies."""
        if not log_entries:
            return {"message": "No log entries to analyze"}
        
        analysis = {
            "total_entries": len(log_entries),
            "level_distribution": defaultdict(int),
            "source_distribution": defaultdict(int),
            "time_range": {
                "start": min(entry.timestamp for entry in log_entries),
                "end": max(entry.timestamp for entry in log_entries)
            },
            "common_messages": defaultdict(int),
            "error_patterns": [],
            "anomalies": []
        }
        
        # Analyze level and source distribution
        for entry in log_entries:
            analysis["level_distribution"][entry.level] += 1
            analysis["source_distribution"][entry.source] += 1
            analysis["common_messages"][entry.message] += 1
        
        # Find error patterns
        error_entries = [e for e in log_entries if e.level == LogLevel.ERROR]
        if error_entries:
            error_messages = [e.message for e in error_entries]
            analysis["error_patterns"] = self._find_common_patterns(error_messages)
        
        # Detect anomalies (simple implementation)
        analysis["anomalies"] = await self._detect_anomalies(log_entries)
        
        # Convert defaultdicts to regular dicts for JSON serialization
        analysis["level_distribution"] = dict(analysis["level_distribution"])
        analysis["source_distribution"] = dict(analysis["source_distribution"])
        analysis["common_messages"] = dict(sorted(
            analysis["common_messages"].items(), 
            key=lambda x: x[1], 
            reverse=True
        )[:10])  # Top 10 most common messages
        
        return analysis
    
    async def filter_by_level(
        self, 
        log_entries: List[LogEntry],
        min_level: LogLevel
    ) -> List[LogEntry]:
        """Filter log entries by minimum level."""
        level_hierarchy = {
            LogLevel.DEBUG: 0,
            LogLevel.INFO: 1,
            LogLevel.WARNING: 2,
            LogLevel.ERROR: 3,
            LogLevel.CRITICAL: 4
        }
        
        min_level_value = level_hierarchy[min_level]
        
        return [
            entry for entry in log_entries
            if level_hierarchy[entry.level] >= min_level_value
        ]
    
    async def search_logs(
        self, 
        log_entries: List[LogEntry],
        query: str,
        fields: Optional[List[str]] = None
    ) -> List[LogEntry]:
        """Search log entries by query."""
        if not query:
            return log_entries
        
        search_fields = fields or ["message", "source"]
        query_lower = query.lower()
        
        matching_entries = []
        
        for entry in log_entries:
            match_found = False
            
            for field in search_fields:
                field_value = getattr(entry, field, "")
                if field_value and query_lower in str(field_value).lower():
                    match_found = True
                    break
            
            # Also search in context if available
            if not match_found and entry.context:
                for key, value in entry.context.items():
                    if query_lower in str(value).lower():
                        match_found = True
                        break
            
            if match_found:
                matching_entries.append(entry)
        
        return matching_entries
    
    def get_supported_patterns(self) -> List[LogPattern]:
        """Get list of supported log patterns."""
        return self.patterns.copy()
    
    def _initialize_patterns(self) -> List[LogPattern]:
        """Initialize log parsing patterns."""
        return [
            # Standard application log pattern
            LogPattern(
                name="standard_app_log",
                pattern=r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),(\d{3}) - (\w+) - (.+?) - (.+)",
                fields=["timestamp", "milliseconds", "level", "source", "message"],
                level=LogLevel.INFO,
                description="Standard application log format"
            ),
            
            # JSON log pattern
            LogPattern(
                name="json_log",
                pattern=r"^{.+}$",
                fields=["json_data"],
                level=LogLevel.INFO,
                description="JSON structured log format"
            ),
            
            # ServiceNow API log pattern
            LogPattern(
                name="servicenow_api",
                pattern=r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) - ServiceNow API - (\w+) - (.+)",
                fields=["timestamp", "level", "message"],
                level=LogLevel.INFO,
                description="ServiceNow API log format"
            ),
            
            # Error log pattern
            LogPattern(
                name="error_log",
                pattern=r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) - ERROR - (.+?) - (.+)",
                fields=["timestamp", "source", "message"],
                level=LogLevel.ERROR,
                description="Error log format"
            ),
            
            # HTTP access log pattern
            LogPattern(
                name="http_access",
                pattern=r'(\S+) - - \[([^\]]+)\] "(\S+) (\S+) (\S+)" (\d+) (\d+)',
                fields=["ip", "timestamp", "method", "path", "protocol", "status", "size"],
                level=LogLevel.INFO,
                description="HTTP access log format"
            )
        ]
    
    async def _parse_line(self, line: str, patterns: List[LogPattern]) -> Optional[LogEntry]:
        """Parse a single log line using available patterns."""
        for pattern in patterns:
            match = re.match(pattern.pattern, line)
            if match:
                return await self._create_log_entry(line, pattern, match)
        
        # If no pattern matches, create a basic entry
        return LogEntry(
            timestamp=datetime.now(),
            level=LogLevel.INFO,
            message=line,
            source="unknown",
            context={"pattern_name": "unparsed"}
        )
    
    async def _create_log_entry(
        self, 
        line: str, 
        pattern: LogPattern, 
        match: re.Match
    ) -> LogEntry:
        """Create log entry from pattern match."""
        groups = match.groups()
        
        # Extract timestamp
        timestamp = datetime.now()
        if "timestamp" in pattern.fields:
            timestamp_idx = pattern.fields.index("timestamp")
            if timestamp_idx < len(groups):
                timestamp = self._parse_timestamp(groups[timestamp_idx])
        
        # Extract level
        level = pattern.level
        if "level" in pattern.fields:
            level_idx = pattern.fields.index("level")
            if level_idx < len(groups):
                level = self._parse_level(groups[level_idx])
        
        # Extract message
        message = line
        if "message" in pattern.fields:
            message_idx = pattern.fields.index("message")
            if message_idx < len(groups):
                message = groups[message_idx]
        
        # Extract source
        source = "unknown"
        if "source" in pattern.fields:
            source_idx = pattern.fields.index("source")
            if source_idx < len(groups):
                source = groups[source_idx]
        
        # Build context from other fields
        context = {"pattern_name": pattern.name}
        for i, field in enumerate(pattern.fields):
            if i < len(groups) and field not in ["timestamp", "level", "message", "source"]:
                context[field] = groups[i]
        
        # Handle JSON logs specially
        if pattern.name == "json_log":
            try:
                import json
                json_data = json.loads(line)
                timestamp = self._parse_timestamp(json_data.get("timestamp", ""))
                level = self._parse_level(json_data.get("level", "info"))
                message = json_data.get("message", line)
                source = json_data.get("source", "json")
                context.update(json_data)
            except json.JSONDecodeError:
                pass
        
        return LogEntry(
            timestamp=timestamp,
            level=level,
            message=message,
            source=source,
            context=context
        )
    
    def _parse_timestamp(self, timestamp_str: str) -> datetime:
        """Parse timestamp string to datetime."""
        if not timestamp_str:
            return datetime.now()
        
        # Try common timestamp formats
        formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%SZ",
            "%d/%b/%Y:%H:%M:%S %z"
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(timestamp_str, fmt)
            except ValueError:
                continue
        
        # If all formats fail, return current time
        logger.warning("Could not parse timestamp", timestamp=timestamp_str)
        return datetime.now()
    
    def _parse_level(self, level_str: str) -> LogLevel:
        """Parse log level string."""
        level_mapping = {
            "debug": LogLevel.DEBUG,
            "info": LogLevel.INFO,
            "warning": LogLevel.WARNING,
            "warn": LogLevel.WARNING,
            "error": LogLevel.ERROR,
            "critical": LogLevel.CRITICAL,
            "fatal": LogLevel.CRITICAL
        }
        
        return level_mapping.get(level_str.lower(), LogLevel.INFO)
    
    def _find_common_patterns(self, messages: List[str]) -> List[Dict[str, Any]]:
        """Find common patterns in error messages."""
        # Simple pattern detection - group similar messages
        pattern_groups = defaultdict(list)
        
        for message in messages:
            # Normalize message by removing numbers and specific values
            normalized = re.sub(r'\d+', 'N', message)
            normalized = re.sub(r'[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}', 'UUID', normalized)
            normalized = re.sub(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b', 'IP', normalized)
            
            pattern_groups[normalized].append(message)
        
        # Return patterns with more than one occurrence
        patterns = []
        for pattern, examples in pattern_groups.items():
            if len(examples) > 1:
                patterns.append({
                    "pattern": pattern,
                    "count": len(examples),
                    "examples": examples[:3]  # First 3 examples
                })
        
        return sorted(patterns, key=lambda x: x["count"], reverse=True)
    
    async def _detect_anomalies(self, log_entries: List[LogEntry]) -> List[Dict[str, Any]]:
        """Detect anomalies in log entries."""
        anomalies = []
        
        if not log_entries:
            return anomalies
        
        # Check for error spikes
        error_entries = [e for e in log_entries if e.level == LogLevel.ERROR]
        if len(error_entries) > len(log_entries) * 0.1:  # More than 10% errors
            anomalies.append({
                "type": "high_error_rate",
                "description": f"High error rate detected: {len(error_entries)} errors out of {len(log_entries)} entries",
                "severity": "high"
            })
        
        # Check for repeated identical messages
        message_counts = defaultdict(int)
        for entry in log_entries:
            message_counts[entry.message] += 1
        
        for message, count in message_counts.items():
            if count > 10:  # Same message repeated more than 10 times
                anomalies.append({
                    "type": "repeated_message",
                    "description": f"Message repeated {count} times: {message[:100]}...",
                    "severity": "medium"
                })
        
        return anomalies
