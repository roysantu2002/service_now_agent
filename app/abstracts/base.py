"""Base abstract classes for the application."""
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, List
from pydantic import BaseModel


class BaseResponse(BaseModel):
    """Base response model."""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    errors: Optional[List[str]] = None


class BaseService(ABC):
    """Abstract base service class."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
    
    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the service."""
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the service is healthy."""
        pass


class BaseConnector(BaseService):
    """Abstract base connector for external services."""
    
    @abstractmethod
    async def connect(self) -> bool:
        """Establish connection to external service."""
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection to external service."""
        pass
    
    # @abstractmethod
    # async def test_connection(self) -> bool:
    #     """Test the connection to external service."""
    #     pass
