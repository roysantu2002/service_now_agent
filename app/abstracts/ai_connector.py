"""Abstract AI connector interface."""
from abc import abstractmethod
from typing import Dict, Any, List, Optional
from pydantic import BaseModel

from app.abstracts.base import BaseConnector


class AIRequest(BaseModel):
    """AI request model."""
    prompt: str
    context: Optional[Dict[str, Any]] = None
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    model: Optional[str] = None


class AIResponse(BaseModel):
    """AI response model."""
    content: str
    usage: Optional[Dict[str, Any]] = None
    model: str
    finish_reason: Optional[str] = None


class BaseAIConnector(BaseConnector):
    """Abstract base class for AI service connectors."""
    
    @abstractmethod
    async def generate_text(self, request: AIRequest) -> AIResponse:
        """Generate text using AI service."""
        pass
    
    @abstractmethod
    async def analyze_incident(
        self, 
        incident_data: Dict[str, Any],
        analysis_type: str = "general"
    ) -> AIResponse:
        """Analyze incident data and provide insights."""
        pass
    
    @abstractmethod
    async def explain_technical_details(
        self, 
        description: str,
        short_description: str,
        notes: List[str]
    ) -> AIResponse:
        """Explain technical details in user-friendly language."""
        pass
    
    @abstractmethod
    def validate_request(self, request: AIRequest) -> bool:
        """Validate AI request parameters."""
        pass
