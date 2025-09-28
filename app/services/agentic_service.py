"""Agentic AI service implementation."""
import uuid
import structlog
from typing import Dict, Any, List, Optional
from datetime import datetime
import asyncio

from app.abstracts.agentic_connector import (
    BaseAgenticConnector,
    AgentTask,
    AgentResult,
    AgentAction
)
from app.services.openai_service import OpenAIConnector
from app.abstracts.ai_connector import AIRequest

logger = structlog.get_logger(__name__)


class AgenticAIService(BaseAgenticConnector):
    """Agentic AI service implementation using OpenAI."""
    
    def __init__(self):
        super().__init__()
        self.openai_connector = OpenAIConnector()
        self.task_history: Dict[str, AgentResult] = {}
    
    async def initialize(self) -> None:
        """Initialize the agentic AI service."""
        await self.openai_connector.initialize()
        logger.info("Agentic AI service initialized")
    
    async def health_check(self) -> bool:
        """Check if the agentic AI service is healthy."""
        return await self.openai_connector.health_check()
    
    async def connect(self) -> bool:
        """Establish connection to agentic AI service."""
        return await self.openai_connector.connect()
    
    async def disconnect(self) -> None:
        """Close connection to agentic AI service."""
        await self.openai_connector.disconnect()
    
    # async def test_connection(self) -> bool:
    #     """Test the connection to agentic AI service."""
    #     return await self.openai_connector.test_connection()
    
    async def execute_task(self, task: AgentTask) -> AgentResult:
        """Execute an agent task."""
        task_id = str(uuid.uuid4())
        start_time = datetime.now()
        
        logger.info("Executing agent task", 
                   task_id=task_id, 
                   action=task.action,
                   priority=task.priority)
        
        try:
            # Route to specific handler based on action
            if task.action == AgentAction.ANALYZE:
                result_data = await self._handle_analyze_task(task)
            elif task.action == AgentAction.CLASSIFY:
                result_data = await self._handle_classify_task(task)
            elif task.action == AgentAction.PRIORITIZE:
                result_data = await self._handle_prioritize_task(task)
            elif task.action == AgentAction.RECOMMEND:
                result_data = await self._handle_recommend_task(task)
            elif task.action == AgentAction.ESCALATE:
                result_data = await self._handle_escalate_task(task)
            else:
                raise ValueError(f"Unknown agent action: {task.action}")
            
            execution_time = (datetime.now() - start_time).total_seconds()
            
            result = AgentResult(
                task_id=task_id,
                action=task.action,
                result=result_data,
                confidence=result_data.get('confidence', 0.8),
                execution_time=execution_time,
                status="completed"
            )
            
            # Store in history
            self.task_history[task_id] = result
            
            logger.info("Agent task completed", 
                       task_id=task_id,
                       execution_time=execution_time,
                       confidence=result.confidence)
            
            return result
            
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            
            result = AgentResult(
                task_id=task_id,
                action=task.action,
                result={"error": str(e)},
                confidence=0.0,
                execution_time=execution_time,
                status="failed"
            )
            
            logger.error("Agent task failed", 
                        task_id=task_id,
                        error=str(e))
            
            return result
    
    async def analyze_incident_priority(
        self, 
        incident_data: Dict[str, Any]
    ) -> AgentResult:
        """Analyze and determine incident priority."""
        task = AgentTask(
            action=AgentAction.PRIORITIZE,
            data=incident_data,
            context={"analysis_type": "priority_assessment"}
        )
        return await self.execute_task(task)
    
    async def classify_incident_type(
        self, 
        incident_data: Dict[str, Any]
    ) -> AgentResult:
        """Classify the type of incident."""
        task = AgentTask(
            action=AgentAction.CLASSIFY,
            data=incident_data,
            context={"classification_type": "incident_type"}
        )
        return await self.execute_task(task)
    
    async def recommend_actions(
        self, 
        incident_data: Dict[str, Any]
    ) -> AgentResult:
        """Recommend actions for incident resolution."""
        task = AgentTask(
            action=AgentAction.RECOMMEND,
            data=incident_data,
            context={"recommendation_type": "resolution_actions"}
        )
        return await self.execute_task(task)
    
    async def check_escalation_criteria(
        self, 
        incident_data: Dict[str, Any]
    ) -> AgentResult:
        """Check if incident meets escalation criteria."""
        task = AgentTask(
            action=AgentAction.ESCALATE,
            data=incident_data,
            context={"check_type": "escalation_criteria"}
        )
        return await self.execute_task(task)
    
    async def _handle_analyze_task(self, task: AgentTask) -> Dict[str, Any]:
        """Handle analysis tasks."""
        incident_data = task.data
        analysis_type = task.context.get('analysis_type', 'general')
        
        # Use OpenAI for analysis
        ai_response = await self.openai_connector.analyze_incident(
            incident_data, analysis_type
        )
        
        return {
            "analysis": ai_response.content,
            "analysis_type": analysis_type,
            "confidence": 0.85,
            "tokens_used": ai_response.usage.get('total_tokens') if ai_response.usage else None
        }
    
    async def _handle_classify_task(self, task: AgentTask) -> Dict[str, Any]:
        """Handle classification tasks."""
        incident_data = task.data
        classification_type = task.context.get('classification_type', 'general')
        
        prompt = self._build_classification_prompt(incident_data, classification_type)
        
        ai_request = AIRequest(
            prompt=prompt,
            context=task.context,
            temperature=0.3  # Lower temperature for consistent classification
        )
        
        ai_response = await self.openai_connector.generate_text(ai_request)
        
        # Parse classification result
        classification = self._parse_classification_response(ai_response.content)
        
        return {
            "classification": classification,
            "classification_type": classification_type,
            "confidence": classification.get('confidence', 0.8),
            "reasoning": classification.get('reasoning', ''),
            "tokens_used": ai_response.usage.get('total_tokens') if ai_response.usage else None
        }
    
    async def _handle_prioritize_task(self, task: AgentTask) -> Dict[str, Any]:
        """Handle prioritization tasks."""
        incident_data = task.data
        
        prompt = self._build_prioritization_prompt(incident_data)
        
        ai_request = AIRequest(
            prompt=prompt,
            context=task.context,
            temperature=0.2  # Very low temperature for consistent prioritization
        )
        
        ai_response = await self.openai_connector.generate_text(ai_request)
        
        # Parse priority assessment
        priority_assessment = self._parse_priority_response(ai_response.content)
        
        return {
            "priority_assessment": priority_assessment,
            "recommended_priority": priority_assessment.get('recommended_priority'),
            "current_priority": incident_data.get('priority'),
            "confidence": priority_assessment.get('confidence', 0.8),
            "justification": priority_assessment.get('justification', ''),
            "tokens_used": ai_response.usage.get('total_tokens') if ai_response.usage else None
        }
    
    async def _handle_recommend_task(self, task: AgentTask) -> Dict[str, Any]:
        """Handle recommendation tasks."""
        incident_data = task.data
        recommendation_type = task.context.get('recommendation_type', 'general')
        
        prompt = self._build_recommendation_prompt(incident_data, recommendation_type)
        
        ai_request = AIRequest(
            prompt=prompt,
            context=task.context,
            temperature=0.4
        )
        
        ai_response = await self.openai_connector.generate_text(ai_request)
        
        # Parse recommendations
        recommendations = self._parse_recommendations_response(ai_response.content)
        
        return {
            "recommendations": recommendations,
            "recommendation_type": recommendation_type,
            "confidence": 0.8,
            "tokens_used": ai_response.usage.get('total_tokens') if ai_response.usage else None
        }
    
    async def _handle_escalate_task(self, task: AgentTask) -> Dict[str, Any]:
        """Handle escalation tasks."""
        incident_data = task.data
        
        prompt = self._build_escalation_prompt(incident_data)
        
        ai_request = AIRequest(
            prompt=prompt,
            context=task.context,
            temperature=0.2
        )
        
        ai_response = await self.openai_connector.generate_text(ai_request)
        
        # Parse escalation assessment
        escalation_assessment = self._parse_escalation_response(ai_response.content)
        
        return {
            "escalation_assessment": escalation_assessment,
            "should_escalate": escalation_assessment.get('should_escalate', False),
            "escalation_reason": escalation_assessment.get('reason', ''),
            "confidence": escalation_assessment.get('confidence', 0.8),
            "tokens_used": ai_response.usage.get('total_tokens') if ai_response.usage else None
        }
    
    def _build_classification_prompt(self, incident_data: Dict[str, Any], classification_type: str) -> str:
        """Build prompt for incident classification."""
        if classification_type == "incident_type":
            return f"""
Classify the following ServiceNow incident into one of these categories:
- Hardware Issue
- Software Issue
- Network Issue
- Security Issue
- Access Issue
- Performance Issue
- Data Issue
- Other

Incident Details:
- Short Description: {incident_data.get('short_description', 'N/A')}
- Description: {incident_data.get('description', 'N/A')}
- Category: {incident_data.get('category', 'N/A')}

Respond in JSON format:
{{
    "category": "selected_category",
    "confidence": 0.0-1.0,
    "reasoning": "explanation for the classification"
}}
            """.strip()
        
        return f"Classify the incident: {incident_data.get('short_description', 'N/A')}"
    
    def _build_prioritization_prompt(self, incident_data: Dict[str, Any]) -> str:
        """Build prompt for incident prioritization."""
        return f"""
Assess the priority of this ServiceNow incident based on business impact and urgency.

Current Details:
- Priority: {incident_data.get('priority', 'N/A')}
- Urgency: {incident_data.get('urgency', 'N/A')}
- Impact: {incident_data.get('impact', 'N/A')}
- Short Description: {incident_data.get('short_description', 'N/A')}
- Description: {incident_data.get('description', 'N/A')}
- State: {incident_data.get('state', 'N/A')}

Priority Levels:
1 - Critical (Business stopped)
2 - High (Business severely impacted)
3 - Medium (Business moderately impacted)
4 - Low (Business minimally impacted)

Respond in JSON format:
{{
    "recommended_priority": "1-4",
    "confidence": 0.0-1.0,
    "justification": "detailed explanation",
    "business_impact": "description of business impact",
    "urgency_assessment": "assessment of urgency"
}}
        """.strip()
    
    def _build_recommendation_prompt(self, incident_data: Dict[str, Any], recommendation_type: str) -> str:
        """Build prompt for recommendations."""
        return f"""
Provide actionable recommendations for resolving this ServiceNow incident.

Incident Details:
- Number: {incident_data.get('number', 'N/A')}
- Short Description: {incident_data.get('short_description', 'N/A')}
- Description: {incident_data.get('description', 'N/A')}
- Priority: {incident_data.get('priority', 'N/A')}
- State: {incident_data.get('state', 'N/A')}
- Assignment Group: {incident_data.get('assignment_group', 'N/A')}

Provide specific, actionable recommendations in JSON format:
{{
    "immediate_actions": ["action1", "action2"],
    "investigation_steps": ["step1", "step2"],
    "resolution_steps": ["step1", "step2"],
    "preventive_measures": ["measure1", "measure2"],
    "estimated_resolution_time": "time estimate",
    "required_resources": ["resource1", "resource2"]
}}
        """.strip()
    
    def _build_escalation_prompt(self, incident_data: Dict[str, Any]) -> str:
        """Build prompt for escalation assessment."""
        return f"""
Assess whether this ServiceNow incident should be escalated based on standard escalation criteria.

Incident Details:
- Priority: {incident_data.get('priority', 'N/A')}
- State: {incident_data.get('state', 'N/A')}
- Opened: {incident_data.get('opened_at', 'N/A')}
- Updated: {incident_data.get('updated_at', 'N/A')}
- Assignment Group: {incident_data.get('assignment_group', 'N/A')}
- Short Description: {incident_data.get('short_description', 'N/A')}

Escalation Criteria:
- Priority 1: Escalate if open > 2 hours
- Priority 2: Escalate if open > 4 hours
- Priority 3: Escalate if open > 8 hours
- Priority 4: Escalate if open > 24 hours
- No progress for > 50% of SLA time
- Multiple failed resolution attempts

Respond in JSON format:
{{
    "should_escalate": true/false,
    "confidence": 0.0-1.0,
    "reason": "explanation for escalation decision",
    "escalation_type": "time_based/complexity_based/resource_based",
    "recommended_escalation_level": "L2/L3/Management"
}}
        """.strip()
    
    def _parse_classification_response(self, response: str) -> Dict[str, Any]:
        """Parse classification response from AI."""
        try:
            import json
            return json.loads(response)
        except:
            return {
                "category": "Other",
                "confidence": 0.5,
                "reasoning": "Could not parse AI response"
            }
    
    def _parse_priority_response(self, response: str) -> Dict[str, Any]:
        """Parse priority assessment response from AI."""
        try:
            import json
            return json.loads(response)
        except:
            return {
                "recommended_priority": "3",
                "confidence": 0.5,
                "justification": "Could not parse AI response"
            }
    
    def _parse_recommendations_response(self, response: str) -> Dict[str, Any]:
        """Parse recommendations response from AI."""
        try:
            import json
            return json.loads(response)
        except:
            return {
                "immediate_actions": ["Review incident details"],
                "investigation_steps": ["Gather more information"],
                "resolution_steps": ["Follow standard procedures"]
            }
    
    def _parse_escalation_response(self, response: str) -> Dict[str, Any]:
        """Parse escalation assessment response from AI."""
        try:
            import json
            return json.loads(response)
        except:
            return {
                "should_escalate": False,
                "confidence": 0.5,
                "reason": "Could not parse AI response"
            }
