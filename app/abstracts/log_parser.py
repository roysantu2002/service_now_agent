"""Abstract log parser interface."""
from abc import abstractmethod
from typing import Dict, Any, List, Optional, Iterator
from pydantic import BaseModel
from datetime import datetime
from enum import Enum

from app.abstracts.base import BaseService


class LogLevel(str, Enum):
    """Log levels."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class LogEntry(BaseModel):
    """Log entry model."""
    timestamp: datetime
    level: LogLevel
    message: str
    source: str
    context: Optional[Dict[str, Any]] = None
    exception: Optional[str] = None
    trace_id: Optional[str] = None


class LogPattern(BaseModel):
    """Log pattern model."""
    name: str
    pattern: str
    fields: List[str]
    level: LogLevel
    description: str


class ParseResult(BaseModel):
    """Log parsing result."""
    entries: List[LogEntry]
    total_count: int
    error_count: int
    warning_count: int
    patterns_matched: Dict[str, int]
    parsing_errors: List[str]


class BaseLogParser(BaseService):
    """Abstract base class for log parsers."""
    
    @abstractmethod
    async def parse_logs(
        self, 
        log_data: str,
        patterns: Optional[List[LogPattern]] = None
    ) -> ParseResult:
        """Parse log data and extract structured information."""
        pass
    
    @abstractmethod
    async def extract_errors(self, log_data: str) -> List[LogEntry]:
        """Extract error entries from log data."""
        pass
    
    @abstractmethod
    async def analyze_patterns(
        self, 
        log_entries: List[LogEntry]
    ) -> Dict[str, Any]:
        """Analyze log entries for patterns and anomalies."""
        pass
    
    @abstractmethod
    async def filter_by_level(
        self, 
        log_entries: List[LogEntry],
        min_level: LogLevel
    ) -> List[LogEntry]:
        """Filter log entries by minimum level."""
        pass
    
    @abstractmethod
    async def search_logs(
        self, 
        log_entries: List[LogEntry],
        query: str,
        fields: Optional[List[str]] = None
    ) -> List[LogEntry]:
        """Search log entries by query."""
        pass
    
    @abstractmethod
    def get_supported_patterns(self) -> List[LogPattern]:
        """Get list of supported log patterns."""
        pass
