"""Gemini API connector implementation with structured request handling."""

import json
import structlog
import traceback
import google.generativeai as genai
from typing import Dict, Any, List, Optional

from app.abstracts.ai_connector import BaseAIConnector, AIRequest, AIResponse
from app.core.config import get_settings

logger = structlog.get_logger(__name__)


class GeminiConnector(BaseAIConnector):
    """Gemini API connector implementation."""

    def __init__(self):
        super().__init__()
        self.settings = get_settings()
        self.client: Optional[genai.GenerativeModel] = None
        self.model = self.settings.GEMINI_MODEL
        self.max_tokens = getattr(self.settings, "GEMINI_MAX_TOKENS", 2000 + 1024)

    async def initialize(self) -> None:
        """Initialize the Gemini connector."""
        try:
            api_key = getattr(self.settings, "GEMINI_API_KEY", None)
            if not api_key:
                raise ValueError("Missing GEMINI_API_KEY in settings")

            genai.configure(api_key=api_key)
            self.client = genai.GenerativeModel(self.model)
            logger.info("✅ Gemini connector initialized", model=self.model)

        except Exception as e:
            logger.error(
                "❌ Failed to initialize Gemini connector",
                error=str(e),
                traceback=traceback.format_exc(),
            )
            raise

    def validate_request(self, request: Dict[str, Any]) -> bool:
        """Validate AI request parameters."""
        if not isinstance(request, dict):
            return False
        prompt = request.get("prompt")
        if not prompt or not prompt.strip():
            return False
        max_tokens = request.get("max_tokens")
        if max_tokens and max_tokens > 4000:
            return False
        temperature = request.get("temperature")
        if temperature and not (0 <= temperature <= 2):
            return False
        return True

    async def health_check(self) -> bool:
        """Perform a simple health check to verify Gemini connectivity."""
        try:
            await self.initialize()
            model = genai.GenerativeModel(self.model)
            response = model.generate_content("ping", generation_config={"max_output_tokens": 5})
            return bool(getattr(response, "text", ""))
        except Exception as e:
            logger.error("⚠️ Gemini health check failed", error=str(e))
            return False

    async def connect(self) -> bool:
        """Establish connection (no persistent socket required)."""
        await self.initialize()
        return await self.health_check()

    async def disconnect(self) -> None:
        """Reset Gemini client (no persistent connection to close)."""
        self.client = None
        logger.info("🔌 Gemini connector disconnected")

    async def generate_text(self, request: dict) -> AIResponse:
        """
        Generate text using Gemini.
        Expects request dict with keys:
            - prompt (str)
            - context (dict, optional)
            - max_tokens (int, optional)
            - temperature (float, optional)
            - model (str, optional)
        """
        await self.initialize()

        if not self.validate_request(request):
            raise ValueError("Invalid AI request parameters")

        prompt = request.get("prompt")
        context = request.get("context", {})
        max_tokens = request.get("max_tokens", self.max_tokens)
        temperature = request.get("temperature", 0.7)
        model_name = request.get("model", self.model)

        try:
            # Build contextual prompt
            system_context = ""
            if context:
                system_context = f"\n\nContext:\n{json.dumps(context, indent=2)}"

            final_prompt = f"{prompt}{system_context}"

            logger.info(
                "Generating text with Gemini",
                model=model_name,
                max_tokens=max_tokens,
                temperature=temperature,
            )

            model = genai.GenerativeModel(model_name)
            response = model.generate_content(
                final_prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                ),
            )

            print(f"Gemini raw response: ")
            print(response)
            # Extract content safely
            # content = getattr(response, "text", "") or ""
             # Safely extract text content even if response.text is unavailable
            content = ""
            try:
                if hasattr(response, "text"):
                    content = response.text or ""
            except Exception:
                # Fallback: manually extract from candidates
                if hasattr(response, "candidates") and response.candidates:
                    parts = getattr(response.candidates[0].content, "parts", [])
                    if parts:
                        content = " ".join(
                            [getattr(p, "text", "") for p in parts if hasattr(p, "text")]
                        ).strip()

            # Extract finish reason (convert Enum → string if needed)
            finish_reason = None
            if hasattr(response, "candidates") and response.candidates:
                reason = getattr(response.candidates[0], "finish_reason", None)
                if reason is not None:
                    finish_reason = str(reason).split(".")[-1]  # e.g. MAX_TOKENS → "MAX_TOKENS"

            ai_response = AIResponse(
                content=content,
                usage=None,  # Gemini doesn’t return token usage
                model=model_name,
                finish_reason=finish_reason or "stop",
            )

            logger.info(
                "Gemini text generation completed",
                finish_reason=finish_reason,
            )
            return ai_response

        except Exception as e:
            logger.error(
                "Error generating text with Gemini",
                error=str(e),
                traceback=traceback.format_exc(),
            )
            raise
            
    # === High-Level Utilities ===
    async def analyze_incident(
        self, incident_data: Dict[str, Any], analysis_type: str = "general"
    ) -> AIResponse:
        """Analyze incident data and provide insights."""
        prompt = self._build_incident_analysis_prompt(incident_data, analysis_type)
        request = {
            "prompt": prompt,
            "context": {"analysis_type": analysis_type},
            "max_tokens": self.max_tokens,
            "temperature": 0.3,
        }
        logger.info("🧩 Analyzing incident with Gemini", analysis_type=analysis_type)
        return await self.generate_text(request)

    async def explain_technical_details(
        self, description: str, short_description: str, notes: List[str]
    ) -> AIResponse:
        """Explain technical details in simple, business-friendly language."""
        prompt = self._build_explanation_prompt(description, short_description, notes)
        request = {
            "prompt": prompt,
            "max_tokens": self.max_tokens,
            "temperature": 0.5,
        }
        logger.info("💡 Explaining technical details with Gemini")
        return await self.generate_text(request)

    # === Prompt Builders ===
    def _build_incident_analysis_prompt(
        self, incident_data: Dict[str, Any], analysis_type: str
    ) -> str:
        """Build prompt for incident analysis."""
        base_prompt = f"""
You are an expert IT incident analyst. Analyze the following ServiceNow incident.

Incident Details:
{json.dumps(incident_data, indent=2)}

Analysis Type: {analysis_type}
        """.strip()

        analysis_sections = {
            "root_cause": [
                "Potential root causes",
                "Recommended investigation steps",
                "Similar patterns",
                "Preventive measures",
            ],
            "priority_assessment": [
                "Assessment of current priority",
                "Business impact",
                "Urgency justification",
                "Priority recommendation",
            ],
            "resolution_guidance": [
                "Step-by-step resolution guidance",
                "Required skills/resources",
                "Estimated resolution time",
                "Escalation criteria",
            ],
            "general": [
                "Summary of the incident",
                "Key concerns and risks",
                "Recommended next steps",
                "Overall assessment",
            ],
        }

        items = analysis_sections.get(analysis_type, analysis_sections["general"])
        instructions = "\n".join([f"{i+1}. {item}" for i, item in enumerate(items)])
        return f"{base_prompt}\n\nPlease provide:\n{instructions}"

    def _build_explanation_prompt(
        self, description: str, short_description: str, notes: List[str]
    ) -> str:
        """Build prompt for technical explanation."""
        notes_text = "\n".join([f"- {n}" for n in notes]) if notes else "No additional notes"
        return f"""
You are an expert communicator. Simplify the following technical details.

Short Description: {short_description}
Description: {description}

Additional Notes:
{notes_text}

Please include:
1. Summary of what happened
2. Business/user impact
3. Actions being taken
4. Steps users should take
5. Estimated resolution time
        """.strip()
