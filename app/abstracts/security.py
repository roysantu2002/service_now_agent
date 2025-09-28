"""Abstract security interface."""
from abc import abstractmethod
from typing import Dict, Any, Optional, List
from pydantic import BaseModel
from datetime import datetime

from app.abstracts.base import BaseService


class SecurityContext(BaseModel):
    """Security context model."""
    user_id: Optional[str] = None
    roles: List[str] = []
    permissions: List[str] = []
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    timestamp: datetime


class AuthResult(BaseModel):
    """Authentication result."""
    authenticated: bool
    user_id: Optional[str] = None
    roles: List[str] = []
    token: Optional[str] = None
    expires_at: Optional[datetime] = None
    message: str


class SecurityEvent(BaseModel):
    """Security event model."""
    event_type: str
    user_id: Optional[str] = None
    ip_address: Optional[str] = None
    resource: str
    action: str
    result: str
    timestamp: datetime
    details: Optional[Dict[str, Any]] = None


class BaseSecurityService(BaseService):
    """Abstract base class for security services."""
    
    @abstractmethod
    async def authenticate(
        self, 
        credentials: Dict[str, Any]
    ) -> AuthResult:
        """Authenticate user credentials."""
        pass
    
    @abstractmethod
    async def authorize(
        self, 
        context: SecurityContext,
        resource: str,
        action: str
    ) -> bool:
        """Authorize user action on resource."""
        pass
    
    @abstractmethod
    async def validate_token(self, token: str) -> SecurityContext:
        """Validate and decode authentication token."""
        pass
    
    @abstractmethod
    async def log_security_event(self, event: SecurityEvent) -> None:
        """Log security event."""
        pass
    
    @abstractmethod
    async def check_rate_limit(
        self, 
        identifier: str,
        action: str
    ) -> bool:
        """Check if action is within rate limits."""
        pass
