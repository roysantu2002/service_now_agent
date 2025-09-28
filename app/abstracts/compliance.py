"""Abstract compliance interface."""
from abc import abstractmethod
from typing import Dict, Any, List, Set, Optional
from pydantic import BaseModel
from enum import Enum

from app.abstracts.base import BaseService


class ComplianceLevel(str, Enum):
    """Compliance levels."""
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


class DataClassification(BaseModel):
    """Data classification model."""
    field_name: str
    classification: ComplianceLevel
    reason: str
    action: str  # "allow", "mask", "remove", "encrypt"


class ComplianceResult(BaseModel):
    """Compliance filtering result."""
    original_data: Dict[str, Any]
    filtered_data: Dict[str, Any]
    removed_fields: List[str]
    masked_fields: List[str]
    classifications: List[DataClassification]
    compliance_score: float


class BaseComplianceFilter(BaseService):
    """Abstract base class for compliance filtering."""
    
    @abstractmethod
    async def classify_data(self, data: Dict[str, Any]) -> List[DataClassification]:
        """Classify data fields according to compliance rules."""
        pass
    
    @abstractmethod
    async def filter_data(
        self, 
        data: Dict[str, Any],
        target_level: ComplianceLevel = ComplianceLevel.INTERNAL
    ) -> ComplianceResult:
        """Filter data according to compliance requirements."""
        pass
    
    @abstractmethod
    async def mask_sensitive_fields(
        self, 
        data: Dict[str, Any],
        fields_to_mask: Set[str]
    ) -> Dict[str, Any]:
        """Mask sensitive fields in data."""
        pass
    
    @abstractmethod
    async def validate_compliance(
        self, 
        data: Dict[str, Any],
        required_level: ComplianceLevel
    ) -> bool:
        """Validate if data meets compliance requirements."""
        pass
    
    @abstractmethod
    def get_sensitive_fields(self) -> Set[str]:
        """Get list of fields considered sensitive."""
        pass
