"""Compliance rules configuration and utilities."""
from typing import Dict, List, Set, Any
from enum import Enum

from app.abstracts.compliance import ComplianceLevel


class ComplianceRuleType(str, Enum):
    """Types of compliance rules."""
    FIELD_NAME = "field_name"
    PATTERN_MATCH = "pattern_match"
    VALUE_TYPE = "value_type"
    CONTENT_ANALYSIS = "content_analysis"


class ComplianceRuleConfig:
    """Configuration for compliance rules."""
    
    @staticmethod
    def get_servicenow_field_mappings() -> Dict[str, ComplianceLevel]:
        """Get ServiceNow specific field compliance mappings."""
        return {
            # System fields - Public
            'sys_id': ComplianceLevel.PUBLIC,
            'sys_created_on': ComplianceLevel.PUBLIC,
            'sys_updated_on': ComplianceLevel.PUBLIC,
            'number': ComplianceLevel.PUBLIC,
            'state': ComplianceLevel.PUBLIC,
            'priority': ComplianceLevel.PUBLIC,
            'urgency': ComplianceLevel.PUBLIC,
            'impact': ComplianceLevel.PUBLIC,
            'category': ComplianceLevel.PUBLIC,
            'subcategory': ComplianceLevel.PUBLIC,
            
            # Business fields - Internal
            'short_description': ComplianceLevel.INTERNAL,
            'description': ComplianceLevel.INTERNAL,
            'assignment_group': ComplianceLevel.INTERNAL,
            'assigned_to': ComplianceLevel.INTERNAL,
            'business_service': ComplianceLevel.INTERNAL,
            'cmdb_ci': ComplianceLevel.INTERNAL,
            
            # Personal information - Confidential
            'caller_id': ComplianceLevel.CONFIDENTIAL,
            'opened_by': ComplianceLevel.CONFIDENTIAL,
            'contact_type': ComplianceLevel.CONFIDENTIAL,
            'location': ComplianceLevel.CONFIDENTIAL,
            'company': ComplianceLevel.CONFIDENTIAL,
            
            # Sensitive notes - Restricted
            'work_notes': ComplianceLevel.RESTRICTED,
            'comments': ComplianceLevel.RESTRICTED,
            'close_notes': ComplianceLevel.RESTRICTED,
            'resolution_notes': ComplianceLevel.RESTRICTED,
            'additional_comments': ComplianceLevel.RESTRICTED,
        }
    
    @staticmethod
    def get_pii_patterns() -> List[Dict[str, Any]]:
        """Get PII detection patterns."""
        return [
            {
                'name': 'ssn',
                'pattern': r'\b\d{3}-\d{2}-\d{4}\b',
                'level': ComplianceLevel.RESTRICTED,
                'action': 'remove'
            },
            {
                'name': 'email',
                'pattern': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
                'level': ComplianceLevel.CONFIDENTIAL,
                'action': 'mask'
            },
            {
                'name': 'phone',
                'pattern': r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',
                'level': ComplianceLevel.CONFIDENTIAL,
                'action': 'mask'
            },
            {
                'name': 'ip_address',
                'pattern': r'\b(?:\d{1,3}\.){3}\d{1,3}\b',
                'level': ComplianceLevel.CONFIDENTIAL,
                'action': 'mask'
            },
            {
                'name': 'credit_card',
                'pattern': r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b',
                'level': ComplianceLevel.RESTRICTED,
                'action': 'remove'
            }
        ]
    
    @staticmethod
    def get_security_patterns() -> List[Dict[str, Any]]:
        """Get security-related patterns."""
        return [
            {
                'name': 'password',
                'pattern': r'(?i)(password|pwd|pass)\s*[:=]\s*\S+',
                'level': ComplianceLevel.RESTRICTED,
                'action': 'remove'
            },
            {
                'name': 'api_key',
                'pattern': r'(?i)(api[_-]?key|apikey)\s*[:=]\s*[A-Za-z0-9_-]+',
                'level': ComplianceLevel.RESTRICTED,
                'action': 'remove'
            },
            {
                'name': 'token',
                'pattern': r'(?i)(token|bearer)\s*[:=]\s*[A-Za-z0-9._-]+',
                'level': ComplianceLevel.RESTRICTED,
                'action': 'remove'
            }
        ]
    
    @staticmethod
    def get_compliance_actions() -> Dict[ComplianceLevel, List[str]]:
        """Get allowed actions for each compliance level."""
        return {
            ComplianceLevel.PUBLIC: ['allow'],
            ComplianceLevel.INTERNAL: ['allow', 'log'],
            ComplianceLevel.CONFIDENTIAL: ['mask', 'encrypt', 'log'],
            ComplianceLevel.RESTRICTED: ['remove', 'encrypt', 'log']
        }
