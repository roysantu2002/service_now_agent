"""OpenAI integration service implementation."""
import openai
import structlog
from typing import Dict, Any, List, Optional
from datetime import datetime

from app.abstracts.ai_connector import (
    BaseAIConnector,
    AIRequest,
    AIResponse
)
from app.core.config import get_settings

logger = structlog.get_logger(__name__)


class OpenAIConnector(BaseAIConnector):
    """OpenAI API connector implementation."""
    
    def __init__(self):
        super().__init__()
        self.settings = get_settings()
        self.client: Optional[openai.AsyncOpenAI] = None
        self.model = self.settings.OPENAI_MODEL
        self.max_tokens = self.settings.OPENAI_MAX_TOKENS
    
    async def initialize(self) -> None:
        """Initialize the OpenAI connector."""
        self.client = openai.AsyncOpenAI(
            api_key=self.settings.OPENAI_API_KEY
        )
        logger.info("OpenAI connector initialized", model=self.model)
    
    async def health_check(self) -> bool:
        """Check if OpenAI API is accessible."""
        try:
            if not self.client:
                await self.initialize()
            
            # Simple test request
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "Hello"}],
                max_tokens=10
            )
            return bool(response.choices)
        except Exception as e:
            logger.error("OpenAI health check failed", error=str(e))
            return False
    
    async def connect(self) -> bool:
        """Establish connection to OpenAI."""
        try:
            await self.initialize()
            return await self.test_connection()
        except Exception as e:
            logger.error("Failed to connect to OpenAI", error=str(e))
            return False
    
    async def disconnect(self) -> None:
        """Close connection to OpenAI."""
        if self.client:
            await self.client.close()
            self.client = None
            logger.info("OpenAI connection closed")
    
    async def test_connection(self) -> bool:
        """Test the connection to OpenAI."""
        try:
            if not self.client:
                await self.initialize()
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "Test connection"}],
                max_tokens=5
            )
            
            success = bool(response.choices)
            if success:
                logger.info("OpenAI connection test successful")
            else:
                logger.error("OpenAI connection test failed - no response")
            return success
            
        except Exception as e:
            logger.error("OpenAI connection test error", error=str(e))
            return False
    
    def validate_request(self, request: AIRequest) -> bool:
        """Validate AI request parameters."""
        if not request.prompt or not request.prompt.strip():
            return False
        
        if request.max_tokens and request.max_tokens > 4000:
            return False
        
        if request.temperature and (request.temperature < 0 or request.temperature > 2):
            return False
        
        return True
    
    async def generate_text(self, request: AIRequest) -> AIResponse:
        """Generate text using OpenAI."""
        if not self.client:
            await self.initialize()
        
        if not self.validate_request(request):
            raise ValueError("Invalid AI request parameters")
        
        try:
            messages = [{"role": "user", "content": request.prompt}]
            
            # Add context if provided
            if request.context:
                context_message = f"Context: {request.context}"
                messages.insert(0, {"role": "system", "content": context_message})
            
            logger.info("Generating text with OpenAI", 
                       model=request.model or self.model,
                       max_tokens=request.max_tokens or self.max_tokens)
            
            response = await self.client.chat.completions.create(
                model=request.model or self.model,
                messages=messages,
                max_tokens=request.max_tokens or self.max_tokens,
                temperature=request.temperature or 0.7
            )
            
            choice = response.choices[0]
            usage_info = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            } if response.usage else None
            
            ai_response = AIResponse(
                content=choice.message.content,
                usage=usage_info,
                model=response.model,
                finish_reason=choice.finish_reason
            )
            
            logger.info("Text generation completed", 
                       tokens_used=usage_info.get('total_tokens') if usage_info else None)
            
            return ai_response
            
        except Exception as e:
            logger.error("Error generating text", error=str(e))
            raise
    
    async def analyze_incident(
        self, 
        incident_data: Dict[str, Any],
        analysis_type: str = "general"
    ) -> AIResponse:
        """Analyze incident data and provide insights."""
        prompt = self._build_incident_analysis_prompt(incident_data, analysis_type)
        
        request = AIRequest(
            prompt=prompt,
            context={"analysis_type": analysis_type},
            max_tokens=self.max_tokens,
            temperature=0.3  # Lower temperature for more consistent analysis
        )
        
        logger.info("Analyzing incident", 
                   sys_id=incident_data.get('sys_id'),
                   analysis_type=analysis_type)
        
        return await self.generate_text(request)
    
    async def explain_technical_details(
        self, 
        description: str,
        short_description: str,
        notes: List[str]
    ) -> AIResponse:
        """Explain technical details in user-friendly language."""
        prompt = self._build_explanation_prompt(description, short_description, notes)
        
        request = AIRequest(
            prompt=prompt,
            max_tokens=self.max_tokens,
            temperature=0.5
        )
        
        logger.info("Explaining technical details")
        
        return await self.generate_text(request)
    
    def _build_incident_analysis_prompt(
        self, 
        incident_data: Dict[str, Any], 
        analysis_type: str
    ) -> str:
        """Build prompt for incident analysis."""
        base_prompt = """
You are an expert IT incident analyst. Analyze the following ServiceNow incident and provide insights.

Incident Details:
- Number: {number}
- Priority: {priority}
- State: {state}
- Short Description: {short_description}
- Description: {description}
- Category: {category}
- Assignment Group: {assignment_group}
- Opened: {opened_at}
- Updated: {updated_at}

Analysis Type: {analysis_type}
        """.strip()
        
        if analysis_type == "root_cause":
            analysis_prompt = """
Please provide:
1. Potential root causes based on the incident details
2. Recommended investigation steps
3. Similar incident patterns to look for
4. Preventive measures to avoid recurrence
            """.strip()
        elif analysis_type == "priority_assessment":
            analysis_prompt = """
Please provide:
1. Assessment of the current priority level
2. Business impact analysis
3. Urgency justification
4. Recommendation for priority adjustment if needed
            """.strip()
        elif analysis_type == "resolution_guidance":
            analysis_prompt = """
Please provide:
1. Step-by-step resolution guidance
2. Required resources and skills
3. Estimated resolution time
4. Escalation criteria
            """.strip()
        else:  # general
            analysis_prompt = """
Please provide:
1. Summary of the incident
2. Key concerns and risks
3. Recommended next steps
4. Overall assessment and recommendations
            """.strip()
        
        return f"{base_prompt}\n\n{analysis_prompt}".format(
            number=incident_data.get('number', 'N/A'),
            priority=incident_data.get('priority', 'N/A'),
            state=incident_data.get('state', 'N/A'),
            short_description=incident_data.get('short_description', 'N/A'),
            description=incident_data.get('description', 'N/A'),
            category=incident_data.get('category', 'N/A'),
            assignment_group=incident_data.get('assignment_group', 'N/A'),
            opened_at=incident_data.get('opened_at', 'N/A'),
            updated_at=incident_data.get('updated_at', 'N/A'),
            analysis_type=analysis_type
        )
    
    def _build_explanation_prompt(
        self, 
        description: str, 
        short_description: str, 
        notes: List[str]
    ) -> str:
        """Build prompt for technical explanation."""
        notes_text = "\n".join([f"- {note}" for note in notes]) if notes else "No additional notes"
        
        return f"""
You are an expert technical communicator. Please explain the following technical incident details in clear, user-friendly language that can be understood by non-technical stakeholders.

Short Description: {short_description}

Detailed Description: {description}

Additional Notes:
{notes_text}

Please provide:
1. A clear, non-technical summary of what happened
2. The business impact in simple terms
3. What actions are being taken to resolve it
4. Any steps users can take while waiting for resolution
5. An estimated timeline if possible

Use simple language and avoid technical jargon. Focus on what matters to the business users.
        """.strip()
