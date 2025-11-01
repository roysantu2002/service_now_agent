# Incident Models

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
    
# class IncidentAnalysisModel(BaseModel):
#     id: str = Field(..., description="Auto-generated ID for the analysis")
#     issue: str = Field(..., description="Short title or summary of the issue")
#     description: str = Field(..., description="Detailed description of the incident")
#     steps_to_resolve: List[str] = Field(..., description="Minimum 10 detailed steps to resolve the issue")
#     technical_details: str = Field(..., description="Technical information and context")
#     complete_description: str = Field(..., description="Comprehensive write-up combining all insights and recommendations")

class IncidentAnalysisModel(BaseModel):
    id: str = Field(..., description="Auto-generated ID for the analysis")
    issue: str = Field(..., description="Short title or summary of the issue")
    issue_category: str = Field(..., description="Category of the issue, e.g., Network, Hardware, Software")
    description: str = Field(..., description="Detailed description of the incident")
    steps_to_resolve: List[str] = Field(..., description="Minimum 10 detailed steps to resolve the issue")
    technical_details: str = Field(..., description="Technical information and context")
    complete_description: str = Field(..., description="Comprehensive write-up combining all insights and recommendations")
    
"""
Incident Models

This module defines data models for incident management including ServiceNow-specific
incident representations with proper validation and serialization capabilities.
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict, field_validator, ConfigDict


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
    """Incident states."""
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
    """AI predicted tiers."""
    TIER_1 = "Tier 1"
    TIER_2 = "Tier 2"
    TIER_3 = "Tier 3"
    EXECUTIVE = "Executive"


class ServiceNowIncident(BaseModel):
    """
    ServiceNow Incident model with comprehensive field support including:
    - Core ServiceNow fields
    - Assignment and workflow fields  
    - Custom AI fields with u_ prefix
    - Audit and tracking fields
    """
    
    # Core ServiceNow Fields
    sys_id: Optional[str] = Field(None, description="ServiceNow unique identifier", alias="sys_id")
    number: Optional[str] = Field(None, description="Incident number (e.g., INC0012345)", alias="number")
    short_description: Optional[str] = Field(None, description="Brief incident description", alias="short_description", max_length=160)
    description: Optional[str] = Field(None, description="Detailed incident description", alias="description")
    category: Optional[IncidentCategory] = Field(None, description="Incident category", alias="category")
    priority: Optional[IncidentPriority] = Field(None, description="Incident priority", alias="priority")
    impact: Optional[IncidentImpact] = Field(None, description="Incident impact", alias="impact")
    urgency: Optional[IncidentUrgency] = Field(None, description="Incident urgency", alias="urgency")
    
    # Assignment Fields
    assignment_group: Optional[str] = Field(None, description="Assigned team/group", alias="assignment_group")
    assigned_to: Optional[str] = Field(None, description="Assigned individual", alias="assigned_to")
    state: Optional[IncidentState] = Field(None, description="Current incident state", alias="state")
    
    # Custom AI Fields (u_ prefix for ServiceNow conventions)
    u_ai_predicted_tier: Optional[AITier] = Field(None, description="AI predicted tier", alias="u_ai_predicted_tier")
    u_ai_confidence: Optional[float] = Field(None, description="AI confidence score (0.0-1.0)", alias="u_ai_confidence", ge=0.0, le=1.0)
    u_ai_routing_reason: Optional[str] = Field(None, description="AI routing reasoning", alias="u_ai_routing_reason")
    u_previous_assignment_group: Optional[str] = Field(None, description="Previous assignment group", alias="u_previous_assignment_group")
    u_feedback_flag: Optional[bool] = Field(False, description="Feedback provided flag", alias="u_feedback_flag")
    
    # Audit Fields
    reassignment_count: int = Field(0, description="Number of reassignments", alias="reassignment_count", ge=0)
    created_on: Optional[datetime] = Field(None, description="Creation timestamp", alias="created_on")
    updated_on: Optional[datetime] = Field(None, description="Last update timestamp", alias="updated_on")
    
    # Configuration for Pydantic
    model_config = ConfigDict(
        populate_by_name=True,  # Allow both field names and aliases
        use_enum_values=True,   # Serialize enums by their values
        extra="allow",          # Allow additional fields from ServiceNow
        json_encoders={
            datetime: lambda v: v.isoformat() if v else None
        }
    )
    
    @field_validator("u_ai_confidence")
    @classmethod
    def validate_ai_confidence(cls, v: Optional[float]) -> Optional[float]:
        """Validate AI confidence score is between 0.0 and 1.0."""
        if v is not None and not (0.0 <= v <= 1.0):
            raise ValueError("AI confidence must be between 0.0 and 1.0")
        return v
    
    @field_validator("reassignment_count")
    @classmethod
    def validate_reassignment_count(cls, v: int) -> int:
        """Validate reassignment count is non-negative."""
        if v < 0:
            raise ValueError("Reassignment count must be non-negative")
        return v
    
    @field_validator("short_description")
    @classmethod
    def validate_short_description(cls, v: Optional[str]) -> Optional[str]:
        """Validate short description length."""
        if v and len(v) > 160:
            raise ValueError("Short description must not exceed 160 characters")
        return v
    
    def to_servicenow_update(self) -> Dict[str, Any]:
        """
        Convert incident data to ServiceNow update payload.
        
        Returns:
            Dict[str, Any]: ServiceNow-compatible update dictionary
        """
        update_data = {}
        
        # Map field names to ServiceNow format (using aliases)
        field_mappings = {
            "number": "number",
            "short_description": "short_description", 
            "description": "description",
            "category": "category",
            "priority": "priority",
            "impact": "impact",
            "urgency": "urgency",
            "assignment_group": "assignment_group",
            "assigned_to": "assigned_to", 
            "state": "state",
            "u_ai_predicted_tier": "u_ai_predicted_tier",
            "u_ai_confidence": "u_ai_confidence",
            "u_ai_routing_reason": "u_ai_routing_reason",
            "u_previous_assignment_group": "u_previous_assignment_group",
            "u_feedback_flag": "u_feedback_flag"
        }
        
        # Only include fields that have values
        for field_name, sn_field_name in field_mappings.items():
            value = getattr(self, field_name, None)
            if value is not None:
                update_data[sn_field_name] = value
        
        # Add audit fields if they exist
        if self.reassignment_count > 0:
            update_data["u_reassignment_count"] = self.reassignment_count
            
        if self.created_on:
            update_data["u_created_on"] = self.created_on.isoformat()
            
        if self.updated_on:
            update_data["u_updated_on"] = self.updated_on.isoformat()
        
        return update_data
    
    def get_ai_fields(self) -> Dict[str, Any]:
        """
        Extract AI-related fields for analysis.
        
        Returns:
            Dict[str, Any]: AI-specific field values
        """
        return {
            "ai_predicted_tier": self.u_ai_predicted_tier.value if self.u_ai_predicted_tier else None,
            "ai_confidence": self.u_ai_confidence,
            "ai_routing_reason": self.u_ai_routing_reason,
            "previous_assignment_group": self.u_previous_assignment_group,
            "feedback_provided": self.u_feedback_flag
        }
    
    def get_assignment_info(self) -> Dict[str, Any]:
        """
        Extract assignment-related information.
        
        Returns:
            Dict[str, Any]: Assignment-specific information
        """
        return {
            "current_assignment_group": self.assignment_group,
            "current_assignee": self.assigned_to,
            "previous_assignment_group": self.u_previous_assignment_group,
            "current_state": self.state.value if self.state else None
        }
    
    def get_priority_info(self) -> Dict[str, Any]:
        """
        Extract priority-related information.
        
        Returns:
            Dict[str, Any]: Priority and impact information
        """
        return {
            "priority": self.priority.value if self.priority else None,
            "impact": self.impact.value if self.impact else None,
            "urgency": self.urgency.value if self.urgency else None
        }
    
    def needs_ai_review(self) -> bool:
        """
        Determine if incident needs AI-based review.
        
        Returns:
            bool: True if AI review is needed
        """
        # Conditions for AI review
        conditions = [
            self.u_ai_confidence is None or self.u_ai_confidence < 0.7,
            self.u_ai_predicted_tier is None,
            self.u_feedback_flag is False,
            self.reassignment_count >= 2
        ]
        
        return any(conditions)
    
    def is_escalation_candidate(self) -> bool:
        """
        Determine if incident is a candidate for escalation.
        
        Returns:
            bool: True if escalation is recommended
        """
        # Escalation criteria
        escalation_reasons = []
        
        if self.priority == IncidentPriority.CRITICAL:
            escalation_reasons.append("critical_priority")
            
        if self.impact == IncidentImpact.HIGH and self.urgency == IncidentUrgency.HIGH:
            escalation_reasons.append("high_impact_urgency")
            
        if self.u_ai_confidence and self.u_ai_confidence > 0.9:
            escalation_reasons.append("high_ai_confidence")
            
        if self.reassignment_count >= 3:
            escalation_reasons.append("multiple_reassignments")
        
        return len(escalation_reasons) > 0
    
    def get_summary(self) -> str:
        """
        Get a human-readable summary of the incident.
        
        Returns:
            str: Incident summary
        """
        parts = []
        
        if self.number:
            parts.append(f"Incident {self.number}")
            
        if self.short_description:
            parts.append(self.short_description)
            
        if self.priority:
            parts.append(f"Priority: {self.priority.value}")
            
        if self.assignment_group:
            parts.append(f"Assigned to: {self.assignment_group}")
            
        if self.u_ai_predicted_tier:
            parts.append(f"AI Tier: {self.u_ai_predicted_tier.value}")
            
        return " | ".join(parts) if parts else "Unassigned incident"
    
    @classmethod
    def from_servicenow_data(cls, data: Dict[str, Any]) -> "ServiceNowIncident":
        """
        Create ServiceNowIncident from ServiceNow API response data.
        
        Args:
            data (Dict[str, Any]): Raw ServiceNow data
            
        Returns:
            ServiceNowIncident: Parsed incident instance
        """
        # Handle datetime fields
        for date_field in ["created_on", "updated_on"]:
            if date_field in data and data[date_field]:
                try:
                    data[date_field] = datetime.fromisoformat(data[date_field].replace('Z', '+00:00'))
                except (ValueError, AttributeError):
                    data[date_field] = None
        
        return cls(**data)
    
    def update_timestamp(self):
        """Update the updated_on timestamp to current time."""
        self.updated_on = datetime.utcnow()


# Utility functions for backward compatibility
def create_basic_incident(
    number: Optional[str] = None,
    short_description: Optional[str] = None,
    description: Optional[str] = None,
    priority: Optional[IncidentPriority] = None,
    category: Optional[IncidentCategory] = None
) -> ServiceNowIncident:
    """
    Create a basic incident with minimal required fields.
    
    Args:
        number: Incident number
        short_description: Brief description
        description: Detailed description
        priority: Priority level
        category: Category
        
    Returns:
        ServiceNowIncident: New incident instance
    """
    return ServiceNowIncident(
        number=number,
        short_description=short_description,
        description=description,
        priority=priority,
        category=category,
        state=IncidentState.NEW,
        created_on=datetime.utcnow(),
        updated_on=datetime.utcnow()
    )


def create_ai_enhanced_incident(
    number: Optional[str] = None,
    short_description: Optional[str] = None,
    description: Optional[str] = None,
    ai_predicted_tier: Optional[AITier] = None,
    ai_confidence: Optional[float] = None,
    ai_routing_reason: Optional[str] = None
) -> ServiceNowIncident:
    """
    Create an incident enhanced with AI predictions.
    
    Args:
        number: Incident number
        short_description: Brief description
        description: Detailed description
        ai_predicted_tier: AI predicted tier
        ai_confidence: AI confidence score
        ai_routing_reason: AI routing reasoning
        
    Returns:
        ServiceNowIncident: AI-enhanced incident instance
    """
    return ServiceNowIncident(
        number=number,
        short_description=short_description,
        description=description,
        u_ai_predicted_tier=ai_predicted_tier,
        u_ai_confidence=ai_confidence,
        u_ai_routing_reason=ai_routing_reason,
        state=IncidentState.NEW,
        created_on=datetime.utcnow(),
        updated_on=datetime.utcnow()
    )


# Example usage and testing
if __name__ == "__main__":
    # Test basic incident creation
    incident = create_basic_incident(
        number="INC0012345",
        short_description="Database connection timeout",
        description="Users experiencing slow response times",
        priority=IncidentPriority.HIGH,
        category=IncidentCategory.SOFTWARE
    )
    
    print(f"Created incident: {incident.get_summary()}")
    print(f"Priority: {incident.priority.value}")
    
    # Test AI enhancement
    ai_incident = create_ai_enhanced_incident(
        number="INC0012346", 
        short_description="API endpoint returning 500 errors",
        ai_predicted_tier=AITier.TIER_2,
        ai_confidence=0.85,
        ai_routing_reason="High error rate indicates backend issue"
    )
    
    print(f"AI Enhanced: {ai_incident.get_summary()}")
    print(f"AI Tier: {ai_incident.u_ai_predicted_tier.value}")
    print(f"AI Confidence: {ai_incident.u_ai_confidence}")
    
    # Test ServiceNow update payload
    update_payload = incident.to_servicenow_update()
    print(f"Update payload: {update_payload}")
    
    # Test validation
    try:
        invalid_incident = ServiceNowIncident(
            number="INC0012347",
            u_ai_confidence=1.5  # Invalid: exceeds 1.0
        )
    except ValueError as e:
        print(f"Validation error (expected): {e}")


class IncidentAnalysisModel(BaseModel):
    """
    Model for AI incident analysis results.
    
    Used by IncidentProcessor to store analyzed incident data with
    AI-generated insights, resolution steps, and technical details.
    """
    
    id: str = Field(..., description="Unique analysis ID")
    issue: str = Field(..., description="Short title describing the problem")
    issue_category: str = Field(..., description="Category of the issue")
    description: str = Field(..., description="Detailed explanation of the incident")
    steps_to_resolve: List[str] = Field(
        default_factory=list,
        description="List of actionable resolution steps",
        min_length=1
    )
    technical_details: str = Field(..., description="Technical breakdown of the incident")
    complete_description: str = Field(
        ...,
        description="Comprehensive summary combining all analysis aspects"
    )
    
    # Optional metadata
    analyzed_at: Optional[datetime] = Field(
        default_factory=datetime.utcnow,
        description="Analysis timestamp"
    )
    ai_model: Optional[str] = Field(None, description="AI model used for analysis")
    confidence_score: Optional[float] = Field(None, ge=0.0, le=1.0, description="Analysis confidence")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                "issue": "Database Connection Pool Exhausted",
                "issue_category": "Database Issue",
                "description": "The production database connection pool has reached maximum capacity, causing application timeouts and service degradation.",
                "steps_to_resolve": [
                    "Step 1: Check current database connection pool size and usage",
                    "Step 2: Identify long-running queries consuming connections",
                    "Step 3: Increase connection pool size temporarily",
                    "Step 4: Optimize slow queries identified in step 2",
                    "Step 5: Implement connection timeout policies",
                    "Step 6: Add monitoring alerts for pool utilization",
                    "Step 7: Review application connection handling patterns",
                    "Step 8: Deploy connection pooling best practices",
                    "Step 9: Test under load to verify resolution",
                    "Step 10: Document findings and preventive measures"
                ],
                "technical_details": "Connection pool maxed at 100 connections. Analysis shows 45 connections held by long-running report queries. Application stack traces indicate connection leak in batch processing module.",
                "complete_description": "Production database experiencing connection pool exhaustion due to combination of inefficient queries and connection leaks in batch processing. Resolution requires immediate pool expansion and query optimization."
            }
        }
    )
