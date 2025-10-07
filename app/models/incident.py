"""Incident-related data models."""
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime

from app.abstracts.servicenow_connector import IncidentData


class IncidentProcessRequest(BaseModel):
    """Request model for incident processing."""
    sys_id: str = Field(..., description="ServiceNow incident sys_id")
    include_history: bool = Field(default=False, description="Include incident history")
    analysis_type: str = Field(default="general", description="Type of AI analysis to perform")
    compliance_level: str = Field(default="internal", description="Compliance filtering level")


class IncidentProcessResponse(BaseModel):
    """Response model for incident processing."""
    success: bool
    incident: Optional[IncidentData] = None
    ai_analysis: Optional[Dict[str, Any]] = None
    compliance_info: Optional[Dict[str, Any]] = None
    processing_time: float
    message: str
    errors: Optional[List[str]] = None


from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime

class IncidentSummary(BaseModel):
    """Incident summary model."""
    sys_id: str
    number: str
    title: str
    status: str
    priority: str
    urgency: Optional[str] = None
    impact: Optional[str] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    assigned_to: Optional[str] = None
    assignment_group: Optional[str] = None
    caller_id: Optional[str] = None
    created: datetime
    updated: datetime
    resolved_at: Optional[datetime] = None
    short_description: Optional[str] = None
    description: Optional[str] = None
    work_notes: Optional[str] = None
    summary: Optional[str] = None
    additional_fields: Optional[Dict[str, Any]] = None
    
class IncidentAnalysisModel(BaseModel):
    id: str = Field(..., description="Auto-generated ID for the analysis")
    issue: str = Field(..., description="Short title or summary of the issue")
    description: str = Field(..., description="Detailed description of the incident")
    steps_to_resolve: List[str] = Field(..., description="Minimum 10 detailed steps to resolve the issue")
    technical_details: str = Field(..., description="Technical information and context")
    complete_description: str = Field(..., description="Comprehensive write-up combining all insights and recommendations")