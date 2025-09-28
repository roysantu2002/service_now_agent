"""Compliance filtering service implementation."""
import re
import structlog
from typing import Dict, Any, List, Set, Optional
from datetime import datetime

from app.abstracts.compliance import (
    BaseComplianceFilter,
    ComplianceLevel,
    DataClassification,
    ComplianceResult
)

logger = structlog.get_logger(__name__)


class ComplianceFilter(BaseComplianceFilter):
    """Compliance filtering service implementation."""
    
    def __init__(self):
        super().__init__()
        self._sensitive_fields = self._initialize_sensitive_fields()
        self._classification_rules = self._initialize_classification_rules()
        self._masking_patterns = self._initialize_masking_patterns()
    
    async def initialize(self) -> None:
        """Initialize the compliance filter."""
        logger.info("Compliance filter initialized")
    
    async def health_check(self) -> bool:
        """Check if the compliance filter is healthy."""
        return True
    
    async def classify_data(self, data: Dict[str, Any]) -> List[DataClassification]:
        """Classify data fields according to compliance rules."""
        classifications = []
        
        for field_name, field_value in data.items():
            classification = self._classify_field(field_name, field_value)
            if classification:
                classifications.append(classification)
        
        logger.info("Data classification completed", 
                   field_count=len(data), 
                   classified_count=len(classifications))
        return classifications
    
    async def filter_data(
        self, 
        data: Dict[str, Any],
        target_level: ComplianceLevel = ComplianceLevel.INTERNAL
    ) -> ComplianceResult:
        """Filter data according to compliance requirements."""
        start_time = datetime.now()
        
        # Classify all fields
        classifications = await self.classify_data(data)
        
        # Apply filtering based on target level
        filtered_data = data.copy()
        removed_fields = []
        masked_fields = []
        
        for classification in classifications:
            field_name = classification.field_name
            
            if classification.action == "remove":
                if field_name in filtered_data:
                    del filtered_data[field_name]
                    removed_fields.append(field_name)
            
            elif classification.action == "mask":
                if field_name in filtered_data:
                    filtered_data[field_name] = self._mask_field_value(
                        field_name, 
                        filtered_data[field_name]
                    )
                    masked_fields.append(field_name)
            
            elif classification.action == "encrypt":
                if field_name in filtered_data:
                    filtered_data[field_name] = self._encrypt_field_value(
                        filtered_data[field_name]
                    )
        
        # Calculate compliance score
        compliance_score = self._calculate_compliance_score(
            classifications, target_level
        )
        
        processing_time = (datetime.now() - start_time).total_seconds()
        
        result = ComplianceResult(
            original_data=data,
            filtered_data=filtered_data,
            removed_fields=removed_fields,
            masked_fields=masked_fields,
            classifications=classifications,
            compliance_score=compliance_score
        )
        
        logger.info("Data filtering completed",
                   processing_time=processing_time,
                   compliance_score=compliance_score,
                   removed_count=len(removed_fields),
                   masked_count=len(masked_fields))
        
        return result
    
    async def mask_sensitive_fields(
        self, 
        data: Dict[str, Any],
        fields_to_mask: Set[str]
    ) -> Dict[str, Any]:
        """Mask sensitive fields in data."""
        masked_data = data.copy()
        
        for field_name in fields_to_mask:
            if field_name in masked_data:
                masked_data[field_name] = self._mask_field_value(
                    field_name, 
                    masked_data[field_name]
                )
        
        logger.info("Sensitive fields masked", field_count=len(fields_to_mask))
        return masked_data
    
    async def validate_compliance(
        self, 
        data: Dict[str, Any],
        required_level: ComplianceLevel
    ) -> bool:
        """Validate if data meets compliance requirements."""
        classifications = await self.classify_data(data)
        
        for classification in classifications:
            field_level = ComplianceLevel(classification.classification)
            
            # Check if field level is more restrictive than required
            if self._is_more_restrictive(field_level, required_level):
                if classification.action == "allow":
                    return False
        
        return True
    
    def get_sensitive_fields(self) -> Set[str]:
        """Get list of fields considered sensitive."""
        return self._sensitive_fields.copy()
    
    def _initialize_sensitive_fields(self) -> Set[str]:
        """Initialize set of sensitive field names."""
        return {
            # Personal Information
            'caller_id', 'user_id', 'email', 'phone', 'mobile_phone',
            'home_phone', 'address', 'location', 'building', 'department',
            'manager', 'employee_number', 'user_name', 'display_name',
            
            # System Information
            'password', 'token', 'api_key', 'secret', 'private_key',
            'certificate', 'hash', 'encrypted_password',
            
            # Network Information
            'ip_address', 'mac_address', 'hostname', 'domain',
            'network_adapter', 'subnet', 'gateway',
            
            # Financial Information
            'cost', 'price', 'budget', 'expense', 'invoice',
            'purchase_order', 'credit_card', 'bank_account',
            
            # Compliance Fields
            'ssn', 'social_security_number', 'tax_id', 'passport',
            'driver_license', 'national_id', 'medical_record',
            
            # Custom ServiceNow Fields
            'work_notes', 'comments', 'additional_comments',
            'resolution_notes', 'close_notes'
        }
    
    def _initialize_classification_rules(self) -> Dict[str, Dict[str, Any]]:
        """Initialize field classification rules."""
        return {
            # Highly Sensitive - Remove from external sharing
            'restricted': {
                'fields': {
                    'password', 'token', 'api_key', 'secret', 'private_key',
                    'ssn', 'social_security_number', 'credit_card', 'bank_account'
                },
                'patterns': [
                    r'\b\d{3}-\d{2}-\d{4}\b',  # SSN pattern
                    r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b',  # Credit card
                    r'(?i)(password|pwd|pass)\s*[:=]\s*\S+',  # Password patterns
                ],
                'action': 'remove'
            },
            
            # Confidential - Mask for internal use
            'confidential': {
                'fields': {
                    'caller_id', 'email', 'phone', 'mobile_phone', 'address',
                    'employee_number', 'ip_address', 'mac_address'
                },
                'patterns': [
                    r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',  # Email
                    r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',  # Phone number
                    r'\b(?:\d{1,3}\.){3}\d{1,3}\b',  # IP address
                ],
                'action': 'mask'
            },
            
            # Internal - Allow for internal systems
            'internal': {
                'fields': {
                    'department', 'manager', 'location', 'building',
                    'assignment_group', 'assigned_to', 'work_notes'
                },
                'patterns': [],
                'action': 'allow'
            },
            
            # Public - Safe for external sharing
            'public': {
                'fields': {
                    'number', 'short_description', 'state', 'priority',
                    'urgency', 'impact', 'category', 'subcategory',
                    'opened_at', 'updated_at', 'resolved_at'
                },
                'patterns': [],
                'action': 'allow'
            }
        }
    
    def _initialize_masking_patterns(self) -> Dict[str, str]:
        """Initialize field masking patterns."""
        return {
            'email': lambda x: self._mask_email(str(x)),
            'phone': lambda x: self._mask_phone(str(x)),
            'ip_address': lambda x: self._mask_ip(str(x)),
            'caller_id': lambda x: f"USER_{hash(str(x)) % 10000:04d}",
            'employee_number': lambda x: f"EMP_{hash(str(x)) % 10000:04d}",
            'default': lambda x: '*' * min(len(str(x)), 8)
        }
    
    def _classify_field(self, field_name: str, field_value: Any) -> Optional[DataClassification]:
        """Classify a single field."""
        field_name_lower = field_name.lower()
        field_value_str = str(field_value) if field_value is not None else ""
        
        # Check each classification level
        for level, rules in self._classification_rules.items():
            # Check field name matches
            if field_name_lower in rules['fields']:
                return DataClassification(
                    field_name=field_name,
                    classification=ComplianceLevel(level),
                    reason=f"Field name '{field_name}' matches {level} classification",
                    action=rules['action']
                )
            
            # Check pattern matches
            for pattern in rules['patterns']:
                if re.search(pattern, field_value_str):
                    return DataClassification(
                        field_name=field_name,
                        classification=ComplianceLevel(level),
                        reason=f"Field value matches {level} pattern",
                        action=rules['action']
                    )
        
        # Default to internal if not classified
        return DataClassification(
            field_name=field_name,
            classification=ComplianceLevel.INTERNAL,
            reason="Default classification",
            action="allow"
        )
    
    def _mask_field_value(self, field_name: str, field_value: Any) -> str:
        """Mask a field value based on its type."""
        field_name_lower = field_name.lower()
        
        # Use specific masking pattern if available
        for pattern_name, mask_func in self._masking_patterns.items():
            if pattern_name in field_name_lower:
                return mask_func(field_value)
        
        # Use default masking
        return self._masking_patterns['default'](field_value)
    
    def _encrypt_field_value(self, field_value: Any) -> str:
        """Encrypt a field value (placeholder implementation)."""
        # In a real implementation, use proper encryption
        import hashlib
        return f"ENCRYPTED_{hashlib.sha256(str(field_value).encode()).hexdigest()[:16]}"
    
    def _mask_email(self, email: str) -> str:
        """Mask email address."""
        if '@' in email:
            local, domain = email.split('@', 1)
            masked_local = local[0] + '*' * (len(local) - 2) + local[-1] if len(local) > 2 else '*' * len(local)
            return f"{masked_local}@{domain}"
        return '*' * len(email)
    
    def _mask_phone(self, phone: str) -> str:
        """Mask phone number."""
        digits_only = re.sub(r'\D', '', phone)
        if len(digits_only) >= 10:
            return f"***-***-{digits_only[-4:]}"
        return '*' * len(phone)
    
    def _mask_ip(self, ip: str) -> str:
        """Mask IP address."""
        parts = ip.split('.')
        if len(parts) == 4:
            return f"{parts[0]}.{parts[1]}.***.**"
        return '*' * len(ip)
    
    def _calculate_compliance_score(
        self, 
        classifications: List[DataClassification],
        target_level: ComplianceLevel
    ) -> float:
        """Calculate compliance score based on classifications."""
        if not classifications:
            return 1.0
        
        compliant_count = 0
        total_count = len(classifications)
        
        for classification in classifications:
            field_level = ComplianceLevel(classification.classification)
            
            # Check if field meets target compliance level
            if not self._is_more_restrictive(field_level, target_level):
                compliant_count += 1
            elif classification.action in ['mask', 'remove', 'encrypt']:
                compliant_count += 1
        
        return compliant_count / total_count
    
    def _is_more_restrictive(
        self, 
        field_level: ComplianceLevel, 
        target_level: ComplianceLevel
    ) -> bool:
        """Check if field level is more restrictive than target level."""
        level_hierarchy = {
            ComplianceLevel.PUBLIC: 0,
            ComplianceLevel.INTERNAL: 1,
            ComplianceLevel.CONFIDENTIAL: 2,
            ComplianceLevel.RESTRICTED: 3
        }
        
        return level_hierarchy[field_level] > level_hierarchy[target_level]
