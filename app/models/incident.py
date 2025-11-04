"""
Incident Models

Unified data models for incident management and AI analysis.
Includes:
- ServiceNow-compatible incident schema
- AI analysis results
- Request/response models for incident processing
- Validation and serialization helpers
"""

from __future__ import annotations
from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict, field_validator


# ---------------------------------------------------------------------
# ENUMS
# ---------------------------------------------------------------------

class IncidentPriority(str, Enum):
    """Incident priority levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    PLANNED = "planned"


class IncidentImpact(str, Enum):
    """Incident impact levels."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class IncidentUrgency(str, Enum):
    """Incident urgency levels."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class IncidentState(str, Enum):
    """Incident workflow states."""
    NEW = "New"
    IN_PROGRESS = "In Progress"
    ON_HOLD = "On Hold"
    RESOLVED = "Resolved"
    CLOSED = "Closed"
    CANCELED = "Canceled"


class IncidentCategory(str, Enum):
    """Incident categories."""
    INQUIRY = "inquiry"
    PROBLEM = "problem"
    QUESTION = "question"
    SOFTWARE = "software"
    HARDWARE = "hardware"
    NETWORK = "network"
    REQUEST = "request"


class AITier(str, Enum):
    """AI predicted support tiers."""
    TIER_1 = "Tier 1"
    TIER_2 = "Tier 2"
    TIER_3 = "Tier 3"
    EXECUTIVE = "Executive"


class AnalysisLevel(str, Enum):
    """AI-suggested operational response level."""
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"
    EXECUTIVE = "Executive"
    UNKNOWN = "Unknown"


# ---------------------------------------------------------------------
# INCIDENT PROCESSING MODELS
# ---------------------------------------------------------------------

class IncidentProcessRequest(BaseModel):
    """Request payload for AI-driven incident processing."""
    sys_id: str = Field(..., description="ServiceNow incident sys_id")
    include_history: bool = Field(default=False, description="Include incident history")
    analysis_type: str = Field(default="general", description="Type of AI analysis to perform")
    compliance_level: str = Field(default="internal", description="Compliance filtering level")


class IncidentProcessResponse(BaseModel):
    """Response payload for AI incident processing."""
    success: bool
    incident: Optional[Dict[str, Any]] = None
    ai_analysis: Optional[Dict[str, Any]] = None
    compliance_info: Optional[Dict[str, Any]] = None
    processing_time: float
    message: str
    errors: Optional[List[str]] = None


# ---------------------------------------------------------------------
# INCIDENT SUMMARY MODEL
# ---------------------------------------------------------------------

class IncidentSummary(BaseModel):
    """Condensed incident summary for dashboards and listings."""
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


# ---------------------------------------------------------------------
# SERVICENOW INCIDENT MODEL
# ---------------------------------------------------------------------

class ServiceNowIncident(BaseModel):
    """
    ServiceNow Incident representation with:
    - Core SNOW fields
    - AI-predicted fields (u_ prefix)
    - Assignment & audit metadata
    """

    sys_id: Optional[str] = Field(None, description="ServiceNow unique identifier")
    number: Optional[str] = Field(None, description="Incident number (e.g., INC0012345)")
    short_description: Optional[str] = Field(None, max_length=160)
    description: Optional[str] = None
    category: Optional[IncidentCategory] = None
    priority: Optional[IncidentPriority] = None
    impact: Optional[IncidentImpact] = None
    urgency: Optional[IncidentUrgency] = None

    assignment_group: Optional[str] = None
    assigned_to: Optional[str] = None
    state: Optional[IncidentState] = None

    # AI-enhanced fields
    u_ai_predicted_tier: Optional[AITier] = None
    u_ai_confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    u_ai_routing_reason: Optional[str] = None
    u_previous_assignment_group: Optional[str] = None
    u_feedback_flag: Optional[bool] = False

    reassignment_count: int = Field(0, ge=0)
    created_on: Optional[datetime] = None
    updated_on: Optional[datetime] = None

    model_config = ConfigDict(
        populate_by_name=True,
        use_enum_values=True,
        extra="allow",
        json_encoders={datetime: lambda v: v.isoformat() if v else None}
    )

    # --- Validators ---
    @field_validator("u_ai_confidence")
    @classmethod
    def _validate_confidence(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and not (0.0 <= v <= 1.0):
            raise ValueError("AI confidence must be between 0.0 and 1.0")
        return v

    @field_validator("short_description")
    @classmethod
    def _validate_short_desc(cls, v: Optional[str]) -> Optional[str]:
        if v and len(v) > 160:
            raise ValueError("Short description must not exceed 160 characters")
        return v

    # --- Converters ---
    def to_servicenow_update(self) -> Dict[str, Any]:
        """Convert to a ServiceNow API update payload."""
        update_fields = {
            "short_description": self.short_description,
            "description": self.description,
            "category": self.category,
            "priority": self.priority,
            "impact": self.impact,
            "urgency": self.urgency,
            "assignment_group": self.assignment_group,
            "assigned_to": self.assigned_to,
            "state": self.state,
            "u_ai_predicted_tier": self.u_ai_predicted_tier,
            "u_ai_confidence": self.u_ai_confidence,
            "u_ai_routing_reason": self.u_ai_routing_reason,
            "u_previous_assignment_group": self.u_previous_assignment_group,
            "u_feedback_flag": self.u_feedback_flag,
        }
        return {k: v for k, v in update_fields.items() if v is not None}

    def get_summary(self) -> str:
        """Return a human-readable summary."""
        parts = [f"Incident {self.number or '(Unnumbered)'}"]
        if self.short_description:
            parts.append(self.short_description)
        if self.priority:
            parts.append(f"Priority: {self.priority}")
        if self.assignment_group:
            parts.append(f"Group: {self.assignment_group}")
        if self.u_ai_predicted_tier:
            parts.append(f"AI Tier: {self.u_ai_predicted_tier}")
        return " | ".join(parts)


# ---------------------------------------------------------------------
# INCIDENT ANALYSIS MODEL (AI OUTPUT)
# ---------------------------------------------------------------------

class IncidentAnalysisModel(BaseModel):
    """
    AI-generated incident analysis model.
    Contains deep insights, categorized findings, and resolution plan.
    """

    id: str = Field(..., description="Unique analysis ID")
    issue: str = Field(..., description="Short title describing the problem")
    issue_category: str = Field(..., description="High-level category of the issue")

    # Extended fields
    category: Optional[str] = Field(
        None, description="AI-classified category (e.g., performance, security, reliability)"
    )
    level: Optional[AnalysisLevel] = Field(
        default=AnalysisLevel.UNKNOWN, description="AI-suggested operational level"
    )

    description: str = Field(..., description="Detailed explanation of the incident")
    steps_to_resolve: List[str] = Field(
        default_factory=list,
        description="List of actionable resolution steps (minimum 5 required)",
        min_length=1
    )
    technical_details: str = Field(..., description="Technical breakdown of root cause and evidence")
    complete_description: str = Field(..., description="Comprehensive summary including all AI insights")

    analyzed_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
    ai_model: Optional[str] = Field(None, description="AI model used for analysis")
    confidence_score: Optional[float] = Field(None, ge=0.0, le=1.0)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                "issue": "Database Connection Pool Exhausted",
                "issue_category": "Database Issue",
                "category": "performance",
                "level": "L2",
                "description": "Production DB connection pool reached maximum capacity causing application latency.",
                "steps_to_resolve": [
                    "Check pool utilization metrics",
                    "Identify long-held connections",
                    "Restart idle sessions",
                    "Optimize long-running queries",
                    "Increase pool size temporarily",
                    "Add monitoring for pool usage"
                ],
                "technical_details": "Connection pool at 100% with 45 long-running queries detected.",
                "complete_description": "Incident caused by query inefficiency and connection leak. Resolved by tuning pool and refactoring API layer.",
                "ai_model": "gemini-pro",
                "confidence_score": 0.94
            }
        }
    )

    @field_validator("steps_to_resolve")
    @classmethod
    def _validate_steps(cls, v: List[str]) -> List[str]:
        if len(v) < 5:
            raise ValueError("At least 5 resolution steps are required.")
        return v


# ---------------------------------------------------------------------
# FACTORY UTILITIES
# ---------------------------------------------------------------------

def create_basic_incident(
    number: Optional[str] = None,
    short_description: Optional[str] = None,
    description: Optional[str] = None,
    priority: Optional[IncidentPriority] = None,
    category: Optional[IncidentCategory] = None,
) -> ServiceNowIncident:
    """Quickly create a basic incident record."""
    now = datetime.utcnow()
    return ServiceNowIncident(
        number=number,
        short_description=short_description,
        description=description,
        priority=priority,
        category=category,
        state=IncidentState.NEW,
        created_on=now,
        updated_on=now,
    )


def create_ai_enhanced_incident(
    number: Optional[str] = None,
    short_description: Optional[str] = None,
    description: Optional[str] = None,
    ai_predicted_tier: Optional[AITier] = None,
    ai_confidence: Optional[float] = None,
    ai_routing_reason: Optional[str] = None,
) -> ServiceNowIncident:
    """Create an AI-enriched incident with predictions."""
    now = datetime.utcnow()
    return ServiceNowIncident(
        number=number,
        short_description=short_description,
        description=description,
        u_ai_predicted_tier=ai_predicted_tier,
        u_ai_confidence=ai_confidence,
        u_ai_routing_reason=ai_routing_reason,
        state=IncidentState.NEW,
        created_on=now,
        updated_on=now,
    )

# -------------------------------------------------------
# Pydantic model for allowed updatable fields
# -------------------------------------------------------
class ServiceNowIncidentUpdateRequest(BaseModel):
    short_description: Optional[str] = Field(None, description="Short summary of the incident")
    category: Optional[str] = Field(None, description="Incident category (e.g., 'network', 'software', etc.)")
    assignment_group: Optional[str] = Field(None, description="Group assigned to the incident")
    assigned_to: Optional[str] = Field(None, description="User assigned to the incident")
    work_notes: Optional[str] = Field(None, description="Internal notes for technicians")
    urgency: Optional[str] = Field(None, description="Incident urgency (1=High, 2=Medium, 3=Low)")
    impact: Optional[str] = Field(None, description="Incident impact (1=High, 2=Medium, 3=Low)")

    class Config:
        extra = "forbid"

# ---------------------------------------------------------------------
# TEST USAGE (LOCAL)
# ---------------------------------------------------------------------

if __name__ == "__main__":
    incident = create_basic_incident(
        number="INC0010001",
        short_description="API latency spike",
        description="Users reported 500ms response delays during peak load",
        priority=IncidentPriority.HIGH,
        category=IncidentCategory.SOFTWARE,
    )

    print("Incident summary:", incident.get_summary())

    analysis = IncidentAnalysisModel(
        id="12345",
        issue="API Latency Spike",
        issue_category="Performance",
        category="network",
        level="L2",
        description="API services experiencing degraded performance under load.",
        steps_to_resolve=[
            "Analyze current API latency logs",
            "Review load balancer health",
            "Increase worker threads",
            "Optimize DB query caching",
            "Implement rate limiting"
        ],
        technical_details="Detected high CPU and DB wait times in service pod #4.",
        complete_description="Load imbalance caused high CPU utilization. Scaling and query optimization resolved issue.",
        ai_model="gemini-pro",
        confidence_score=0.93,
    )

    print("AI Analysis:", analysis.model_dump_json(indent=2))


