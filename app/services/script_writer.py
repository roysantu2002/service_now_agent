# script_util.py

import os
import logging
from typing import Optional, Dict, Any

from dotenv import load_dotenv
from .generic_ai_connector import AIConnectorFactory

load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")


class ScriptUtil:
    """
    Generic script utility that wraps AIConnectorFactory and handles prompt-based text generation.
    Works with Azure OpenAI or OpenAI backends based on provider_name.
    """

    def __init__(self, provider_name: Optional[str] = "azure"):
        self.provider_name = provider_name
        self.ai_service = AIConnectorFactory.get_connector(provider_name)
        self._initialized = False

    async def _ensure_initialized(self):
        """Initialize the AI connector once per session."""
        if not self._initialized:
            logger.info("[Init] Initializing AI service...")
            if hasattr(self.ai_service, "initialize"):
                await self.ai_service.initialize()
            self._initialized = True
            logger.info("[Init] AI service initialized successfully.")

    async def generate_script(self, query: str, context: Optional[Dict[str, Any]] = None) -> str:
        """
        Generate a response or script text for the given query prompt.
        """
        try:
            await self._ensure_initialized()

            logger.info("Inside call_prompt with query: %s", query)

            ai_request = {
                "prompt": query,
                "context": context or {"task": "script_generation"},
                "max_tokens": 800,
                "temperature": 0.3,
            }

            ai_response = await self.ai_service.generate_text(ai_request)

            if not ai_response:
                logger.warning("No response received from AI service.")
                return ""

            content = str(ai_response).strip()
            logger.info("AI response received successfully.")
            return content

        except Exception as e:
            logger.error(f"Error during AI script generation: {e}", exc_info=True)
            return f"ERROR: {e}"
