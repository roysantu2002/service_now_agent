from pydantic import BaseModel, Field
from typing import List, Literal, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class SearchType(str, Enum):
    SEMANTIC = "semantic"
    KEYWORD = "keyword"
    PATTERN = "pattern"
    HYBRID = "hybrid"


class UploadStatus(BaseModel):
    upload_id: str
    status: str
    progress: int
    total_size: int
    uploaded_size: int
    filename: str
    file_path: Optional[str] = None


class AnalysisRequest(BaseModel):
    upload_id: str
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    time_period: Optional[int] = Field(None, description="Time period in hours (6, 12, 24)")


class SearchRequest(BaseModel):
    query: str
    search_type: SearchType = SearchType.HYBRID
    max_results: int = Field(10, ge=1, le=100)


class AIAnalysisRequest(BaseModel):
    error_message: str


class LogEntryResponse(BaseModel):
    line_number: int
    timestamp: str
    level: str
    category: str
    message: str
    severity_score: int


class SearchResultResponse(BaseModel):
    entry: LogEntryResponse
    similarity_score: float
    match_type: str
    context: str


class SearchResponse(BaseModel):
    query: str
    search_type: str
    total_results: int
    results: List[SearchResultResponse]

class DateRangeFilter(BaseModel):
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    time_period: Optional[int] = Field(None, description="Time period in hours (6, 12, 24)")


class AnalysisResponse(BaseModel):
    analysis_id: str
    timestamp: str
    summary: Dict[str, Any]
    statistics: Dict[str, Any]
    compliance: Dict[str, Any]
    patterns: Dict[str, Any]
    top_errors: List[Dict[str, Any]]
    top_warnings: List[Dict[str, Any]]
    
class LogEntry(BaseModel):
    timestamp: Optional[datetime]
    level: Optional[str] = "INFO"
    message: str
    severity_score: Optional[int] = 0

class DateRangeFilter(BaseModel):
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    
class SeverityLevel(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class AttackType(str, Enum):
    BRUTE_FORCE = "BRUTE_FORCE"
    SQL_INJECTION = "SQL_INJECTION"
    XSS = "XSS"
    FILE_INCLUSION = "FILE_INCLUSION"
    COMMAND_INJECTION = "COMMAND_INJECTION"
    PRIVILEGE_ESCALATION = "PRIVILEGE_ESCALATION"
    UNKNOWN = "UNKNOWN"


class IPAddress(BaseModel):
    ip_address: str = Field(pattern=r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$")


class ResponseCode(BaseModel):
    response_code: str = Field(pattern=r"^\d{3}$")


class WebTrafficPattern(BaseModel):
    url_path: str
    http_method: str
    hits_count: int
    response_codes: Dict[str, int]
    unique_ips: int


class WebSecurityEvent(BaseModel):
    relevant_log_entries: List[str]
    reasoning: str
    event_type: str
    severity: SeverityLevel
    requires_human_review: bool
    confidence_score: float = Field(ge=0.0, le=1.0)
    url_pattern: str
    http_method: Literal["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD", "TRACE", "CONNECT"]
    source_ips: List[IPAddress]
    response_codes: List[ResponseCode]
    user_agents: List[str]
    possible_attack_patterns: List[AttackType]
    recommended_actions: List[str]


class LogAnalysis(BaseModel):
    file_name: str
    summary: str
    observations: List[str]
    planning: List[str]
    events: List[WebSecurityEvent]
    traffic_patterns: List[WebTrafficPattern]
    highest_severity: Optional[SeverityLevel]
    requires_immediate_attention: bool


class MultiLogAnalysis(BaseModel):
    analysis_id: str
    overall_summary: str
    aggregated_findings: List[str]
    highest_severity_overall: Optional[SeverityLevel]
    combined_events: List[WebSecurityEvent]
    individual_analyses: List[LogAnalysis]