from typing import Dict, Any
from pydantic import BaseModel


# -------------------------
# Exceptions
# -------------------------
class ServiceNowError(Exception):
    """Base exception for ServiceNow API errors."""
    pass


class ServiceNowNotFoundError(ServiceNowError):
    """Exception when an incident is not found in ServiceNow."""
    pass


# -------------------------
# Base Connector
# -------------------------
class BaseServiceNowConnector:
    """Minimal ServiceNow connector with no external dependencies."""
    
    async def get_incident(self, sys_id: str) -> BaseModel:
        """Fetch an incident (stub). Override in actual connector."""
        return {"sys_id": sys_id, "short_description": "Example incident"}

    async def get_incident_history(self, sys_id: str) -> list[Dict[str, Any]]:
        """Return incident history (stub)."""
        return []

    async def health_check(self) -> bool:
        """Stub health check."""
        return True

    async def initialize(self):
        pass

    async def disconnect(self):
        pass
