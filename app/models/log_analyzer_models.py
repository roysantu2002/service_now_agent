from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
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