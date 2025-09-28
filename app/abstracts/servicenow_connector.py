"""Abstract ServiceNow connector interface."""
from abc import abstractmethod
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from datetime import datetime

from app.abstracts.base import BaseConnector


class IncidentData(BaseModel):
    """ServiceNow incident data model."""
    sys_id: str
    number: str
    short_description: str
    description: Optional[str] = None
    state: str
    priority: str
    urgency: str
    impact: str
    category: Optional[str] = None
    subcategory: Optional[str] = None
    assigned_to: Optional[str] = None
    assignment_group: Optional[str] = None
    caller_id: Optional[str] = None
    opened_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime] = None
    notes: Optional[str] = None
    work_notes: Optional[str] = None
    additional_fields: Optional[Dict[str, Any]] = None


class ServiceNowQuery(BaseModel):
    """ServiceNow query parameters."""
    table: str = "incident"
    sys_id: Optional[str] = None
    query: Optional[str] = None
    fields: Optional[List[str]] = None
    limit: Optional[int] = None
    offset: Optional[int] = None


class ServiceNowResponse(BaseModel):
    """ServiceNow API response."""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    status_code: int
    response_time: float


class BaseServiceNowConnector(BaseConnector):
    """Abstract base class for ServiceNow connectors."""

    @abstractmethod
    async def connect(self) -> bool:
        """Establish connection to ServiceNow."""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection to ServiceNow."""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if ServiceNow is accessible."""
        pass

    @abstractmethod
    async def get_incident(self, sys_id: str) -> IncidentData:
        """Get incident by sys_id."""
        pass
    
    @abstractmethod
    async def query_incidents(self, query: ServiceNowQuery) -> List[IncidentData]:
        """Query incidents with filters."""
        pass
    
    @abstractmethod
    async def update_incident(
        self, 
        sys_id: str,
        updates: Dict[str, Any]
    ) -> ServiceNowResponse:
        """Update incident data."""
        pass
    
    @abstractmethod
    async def add_work_note(
        self, 
        sys_id: str,
        note: str
    ) -> ServiceNowResponse:
        """Add work note to incident."""
        pass
    
    @abstractmethod
    async def get_incident_history(self, sys_id: str) -> List[Dict[str, Any]]:
        """Get incident history/audit trail."""
        pass
    
    @abstractmethod
    def validate_credentials(self) -> bool:
        """Validate ServiceNow credentials."""
        pass
