"""Abstract agentic connector interface."""
from abc import abstractmethod
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from enum import Enum

from app.abstracts.base import BaseConnector


class AgentAction(str, Enum):
    """Available agent actions."""
    ANALYZE = "analyze"
    CLASSIFY = "classify"
    PRIORITIZE = "prioritize"
    RECOMMEND = "recommend"
    ESCALATE = "escalate"


class AgentTask(BaseModel):
    """Agent task model."""
    action: AgentAction
    data: Dict[str, Any]
    context: Optional[Dict[str, Any]] = None
    priority: int = 1
    timeout: Optional[int] = None


class AgentResult(BaseModel):
    """Agent result model."""
    task_id: str
    action: AgentAction
    result: Dict[str, Any]
    confidence: float
    execution_time: float
    status: str


class BaseAgenticConnector(BaseConnector):
    """Abstract base class for agentic AI connectors."""
    
    @abstractmethod
    async def execute_task(self, task: AgentTask) -> AgentResult:
        """Execute an agent task."""
        pass
    
    @abstractmethod
    async def analyze_incident_priority(
        self, 
        incident_data: Dict[str, Any]
    ) -> AgentResult:
        """Analyze and determine incident priority."""
        pass
    
    @abstractmethod
    async def classify_incident_type(
        self, 
        incident_data: Dict[str, Any]
    ) -> AgentResult:
        """Classify the type of incident."""
        pass
    
    @abstractmethod
    async def recommend_actions(
        self, 
        incident_data: Dict[str, Any]
    ) -> AgentResult:
        """Recommend actions for incident resolution."""
        pass
    
    @abstractmethod
    async def check_escalation_criteria(
        self, 
        incident_data: Dict[str, Any]
    ) -> AgentResult:
        """Check if incident meets escalation criteria."""
        pass
