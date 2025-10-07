"""
Generic AI connector that can switch between OpenAI and Gemini dynamically.
"""

import structlog
from typing import Dict, Any, List, Optional
from datetime import datetime

from app.abstracts.ai_connector import BaseAIConnector, AIRequest, AIResponse
from app.core.config import get_settings

# Providers
from app.services.openai_connector import OpenAIConnector
from app.services.gemini_connector import GeminiConnector

logger = structlog.get_logger(__name__)


class AIConnectorFactory:
    """Factory class to select and initialize the right AI provider."""
    
    _connectors = {
        "openai": OpenAIConnector,
        "gemini": GeminiConnector
    }

    @staticmethod
    def get_connector(provider_name: Optional[str] = None) -> BaseAIConnector:
        """Return initialized connector instance."""
        settings = get_settings()
        provider = (provider_name or settings.AI_PROVIDER or "openai").lower()
        
        if provider not in AIConnectorFactory._connectors:
            raise ValueError(f"Unsupported AI provider: {provider}")

        connector_class = AIConnectorFactory._connectors[provider]
        logger.info("Initializing AI connector", provider=provider)
        return connector_class()
