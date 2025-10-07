"""Gemini API connector implementation."""
import structlog
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
        self.model = self.settings.GEMINI_MODEL
        self.client_initialized = False

    async def initialize(self) -> None:
        """Initialize Gemini client."""
        if not self.client_initialized:
            genai.configure(api_key=self.settings.GEMINI_API_KEY)
            self.client_initialized = True
            logger.info("Gemini connector initialized", model=self.model)

    async def health_check(self) -> bool:
        """Check if Gemini API is accessible."""
        try:
            await self.initialize()
            model = genai.GenerativeModel(self.model)
            response = model.generate_content("Hello", generation_config={"max_output_tokens": 5})

            # Safely extract text
            text = ""
            if hasattr(response, "candidates") and response.candidates:
                text = getattr(response.candidates[0], "content", "")

            return bool(text)
        except Exception as e:
            logger.error("Gemini health check failed", error=str(e))
            return False

    async def connect(self) -> bool:
        await self.initialize()
        return await self.health_check()

    async def disconnect(self) -> None:
        """Gemini has no persistent connection to close."""
        self.client_initialized = False
        logger.info("Gemini connector reset")

    def validate_request(self, request: AIRequest) -> bool:
        if not request.prompt or not request.prompt.strip():
            return False
        return True

    async def generate_text(self, request: AIRequest) -> AIResponse:
        await self.initialize()

        if not self.validate_request(request):
            raise ValueError("Invalid AI request parameters")

        try:
            model = genai.GenerativeModel(request.model or self.model)
            response = model.generate_content(
                request.prompt,
                generation_config={
                    "temperature": request.temperature or 0.7,
                    "max_output_tokens": request.max_tokens or self.settings.GEMINI_MAX_TOKENS,
                },
            )

            content = getattr(response, "text", "") or ""
            ai_response = AIResponse(
                content=content,
                usage=None,  # Gemini doesn’t provide token usage metadata
                model=self.model,
                finish_reason="stop",
            )

            logger.info("Gemini text generation completed")
            return ai_response

        except Exception as e:
            logger.error("Gemini text generation failed", error=str(e))
            raise

    # === Abstract methods implemented ===
    async def analyze_incident(self, incident_data: Dict[str, Any], analysis_type: str = "general") -> AIResponse:
        """Analyze incident data and provide insights."""
        prompt = self._build_incident_analysis_prompt(incident_data, analysis_type)
        request = AIRequest(prompt=prompt, max_tokens=self.settings.GEMINI_MAX_TOKENS, temperature=0.3)
        logger.info("Analyzing incident with Gemini", analysis_type=analysis_type)
        return await self.generate_text(request)

    async def explain_technical_details(self, description: str, short_description: str, notes: List[str]) -> AIResponse:
        """Explain technical details in simple, non-technical terms."""
        prompt = self._build_explanation_prompt(description, short_description, notes)
        request = AIRequest(prompt=prompt, max_tokens=self.settings.GEMINI_MAX_TOKENS, temperature=0.5)
        logger.info("Explaining technical details with Gemini")
        return await self.generate_text(request)

    # === Reusable prompt builders (same as OpenAI connector) ===
    def _build_incident_analysis_prompt(self, incident_data: Dict[str, Any], analysis_type: str) -> str:
        return f"""
You are an expert IT incident analyst. Analyze the following incident and provide insights.

Incident Details:
- Number: {incident_data.get('number', 'N/A')}
- Priority: {incident_data.get('priority', 'N/A')}
- State: {incident_data.get('state', 'N/A')}
- Short Description: {incident_data.get('short_description', 'N/A')}
- Description: {incident_data.get('description', 'N/A')}
- Category: {incident_data.get('category', 'N/A')}
- Assignment Group: {incident_data.get('assignment_group', 'N/A')}
- Opened: {incident_data.get('opened_at', 'N/A')}
- Updated: {incident_data.get('updated_at', 'N/A')}

Analysis Type: {analysis_type}

Provide a concise analysis including:
1. Key concerns and risks
2. Root cause or likely reason
3. Recommended next steps
4. Preventive actions
        """.strip()

    def _build_explanation_prompt(self, description: str, short_description: str, notes: List[str]) -> str:
        notes_text = "\n".join([f"- {note}" for note in notes]) if notes else "No additional notes"
        return f"""
Explain this incident in simple, clear language for non-technical users.

Short Description: {short_description}
Detailed Description: {description}
Notes:
{notes_text}

Please include:
1. A plain-English summary of what happened
2. The impact on users or business
3. Actions being taken
4. Any user instructions
        """.strip()
