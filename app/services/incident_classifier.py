"""
Incident Classification Service

This service provides AI-powered incident classification capabilities using generic AI connectors
and knowledge base integration. It follows factory patterns and async programming paradigms.
"""

import logging
import json
import traceback
from typing import Dict, List, Optional, Union, Any
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum

from app.services.generic_ai_connector import AIConnectorFactory

logger = logging.getLogger(__name__)


class IncidentSeverity(Enum):
    """Incident severity levels"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class IncidentCategory(Enum):
    """Incident categories for classification"""
    SECURITY = "security"
    PERFORMANCE = "performance"
    AVAILABILITY = "availability"
    FUNCTIONALITY = "functionality"
    DATA = "data"
    INFRASTRUCTURE = "infrastructure"
    USER_EXPERIENCE = "user_experience"
    INTEGRATION = "integration"
    UNKNOWN = "unknown"


@dataclass
class ClassificationResult:
    """Result of incident classification"""
    category: IncidentCategory
    severity: IncidentSeverity
    confidence: float
    reasoning: str
    supporting_evidence: List[str]
    suggested_priority: int
    recommended_actions: List[str]
    related_incidents: List[str]
    metadata: Dict[str, Any]
    timestamp: datetime


class IncidentClassifierError(Exception):
    """Custom exception for incident classification errors"""
    pass


class KBLoader:
    """
    Knowledge Base Loader for incident classification
    Loads and manages incident knowledge base data
    """
    
    def __init__(self, kb_path: Optional[str] = None):
        print(f"📝 KBLoader initializing...")
        self.kb_path = kb_path
        self._kb_data = {}
        self._loaded = False
        print(f"📋 KBLoader initialized with path: {self.kb_path}")
    
    async def load_kb(self) -> None:
        """Load knowledge base data"""
        try:
            self._kb_data = {
                "patterns": {
                    "security_incidents": [
                        "unauthorized access", "data breach", "malware detection", "suspicious activity"
                    ],
                    "performance_incidents": [
                        "slow response time", "high CPU usage", "memory leak", "database timeout"
                    ],
                    "availability_incidents": [
                        "service down", "connection timeout", "server unreachable", "cluster failure"
                    ]
                },
                "severity_mapping": {
                    "security": "critical",
                    "performance": "high",
                    "availability": "high",
                    "functionality": "medium",
                    "data": "medium",
                    "infrastructure": "high"
                },
                "context_rules": {
                    "production": {"multiplier": 1.5, "max_severity": "critical"},
                    "staging": {"multiplier": 1.2, "max_severity": "high"},
                    "development": {"multiplier": 0.8, "max_severity": "medium"}
                }
            }
            self._loaded = True
            print(f"✅ SUCCESS: Knowledge Base loaded successfully from {self.kb_path}")
            logger.info(f"Knowledge base loaded from {self.kb_path}")
        except Exception as e:
            print(f"❌ ERROR: Failed to load knowledge base: {e}")
            logger.error(f"Failed to load knowledge base: {e}")
            raise IncidentClassifierError(f"KB loading failed: {e}")
    
    async def search_patterns(self, text: str, pattern_type: str) -> List[str]:
        """Search knowledge base for matching patterns"""
        if not self._loaded:
            await self.load_kb()
        
        patterns = self._kb_data.get("patterns", {}).get(pattern_type, [])
        text_lower = text.lower()
        return [p for p in patterns if p.lower() in text_lower]
    
    def get_severity_mapping(self, category: str) -> str:
        """Get default severity for a category"""
        return self._kb_data.get("severity_mapping", {}).get(category, "medium")
    
    def get_context_rule(self, context: str) -> Dict:
        """Get context-specific rules"""
        return self._kb_data.get("context_rules", {}).get(context, {})


class IncidentClassifierService:
    """
    Main incident classification service using AI and knowledge base
    """
    
    def __init__(self, 
                 provider_name: Optional[str] = None,
                 kb_loader: Optional[KBLoader] = None):
        self.provider_name = provider_name or "gemini"
        self.ai_service = AIConnectorFactory.get_connector(self.provider_name)
        self.kb_loader = kb_loader or KBLoader()
        self._initialized = False
        
    async def _ensure_initialized(self) -> None:
        """Ensure the service is initialized"""
        if not self._initialized:
            if hasattr(self.ai_service, "initialize"):
                await self.ai_service.initialize()
            if not getattr(self.kb_loader, "_loaded", False):
                await self.kb_loader.load_kb()
            self._initialized = True
            logger.info("Incident classifier service initialized", extra={"provider": self.provider_name})
    
    async def _analyze_with_ai(self, incident_text: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze incident using AI connector"""
        try:
            await self._ensure_initialized()
            
            prompt = f"""
            Analyze the following incident and provide classification:
            
            Incident Description: {incident_text}
            Context: {json.dumps(context, indent=2)}
            
            Provide analysis in JSON format with:
            - category: one of security, performance, availability, functionality, data, infrastructure, user_experience, integration
            - severity: one of critical, high, medium, low, info
            - confidence: float between 0 and 1
            - reasoning: detailed explanation
            - supporting_evidence: list of key indicators found
            - suggested_actions: recommended actions
            """
            
            ai_analysis = await self.ai_service.generate_text({
                "prompt": prompt,
                "context": context,
                "max_tokens": 2000,
                "temperature": 0.3
            })
            
            raw_text = self._get_ai_raw_text(ai_analysis)
            logger.info("AI raw text retrieved", extra={"length": len(raw_text)})
            
            parsed_json = self._extract_json_from_ai(raw_text)
            return parsed_json
            
        except Exception as e:
            logger.error("AI analysis failed", extra={"error": str(e)}, exc_info=True)
            raise IncidentClassifierError(f"AI analysis failed: {e}")
    
    def _get_ai_raw_text(self, ai_analysis) -> str:
        """Extract raw text from AI response"""
        raw_text = ""
        # Gemini format
        if hasattr(ai_analysis, "candidates") and ai_analysis.candidates:
            candidate = ai_analysis.candidates[0]
            parts = getattr(getattr(candidate, "content", {}), "parts", [])
            raw_text = "".join([getattr(p, "text", "") for p in parts if getattr(p, "text", None)]).strip()
        # OpenAI / default
        if not raw_text:
            raw_text = getattr(ai_analysis, "content", "") or str(ai_analysis)
        return raw_text.strip()
    
    def _extract_json_from_ai(self, raw_text: str) -> Dict[str, Any]:
        """Safely extract JSON from AI output"""
        if not raw_text.strip():
            raise ValueError("AI returned no content")
        
        content = raw_text.replace("```json", "").replace("```", "").strip()
        start, end = content.find("{"), content.rfind("}")
        
        if start == -1:
            raise ValueError("No JSON object found in AI output")
        
        json_substr = content[start:end + 1]
        try:
            return json.loads(json_substr)
        except json.JSONDecodeError:
            import re
            kv_pairs = re.findall(r'"(\w+)":\s*"([^"]*)"', json_substr)
            return {k: v for k, v in kv_pairs}
    
    async def _enhance_with_kb(self, ai_result: Dict[str, Any], incident_text: str) -> Dict[str, Any]:
        """Enhance AI result with KB info"""
        try:
            category = ai_result.get("category", "unknown")
            kb_matches = await self.kb_loader.search_patterns(incident_text, f"{category}_incidents")
            default_severity = self.kb_loader.get_severity_mapping(category)
            
            enhanced = ai_result.copy()
            enhanced["kb_matches"] = kb_matches
            enhanced["default_severity"] = default_severity
            
            if kb_matches:
                enhanced["confidence"] = min(0.95, float(enhanced.get("confidence", 0.5)) + 0.1)
            
            return enhanced
        except Exception as e:
            logger.error(f"KB enhancement failed: {e}")
            return ai_result
    
    async def _calculate_priority(self, severity: IncidentSeverity, context: Dict[str, Any]) -> int:
        """Calculate priority based on severity and context"""
        base_priority = {
            IncidentSeverity.CRITICAL: 1,
            IncidentSeverity.HIGH: 2,
            IncidentSeverity.MEDIUM: 3,
            IncidentSeverity.LOW: 4,
            IncidentSeverity.INFO: 5
        }
        priority = base_priority.get(severity, 3)
        env = context.get("environment", "production")
        context_rule = self.kb_loader.get_context_rule(env)
        if context_rule:
            priority = max(1, int(priority * context_rule.get("multiplier", 1.0)))
        return priority
    
    async def analyze_incident(self, incident_text: str, context: Optional[Dict[str, Any]] = None) -> ClassificationResult:
        """Main entrypoint: analyze incident"""
        try:
            await self._ensure_initialized()
            context = context or {}
            ai_result = await self._analyze_with_ai(incident_text, context)
            enhanced_result = await self._enhance_with_kb(ai_result, incident_text)
            
            category = IncidentCategory(enhanced_result.get("category", "unknown"))
            severity = IncidentSeverity(enhanced_result.get("severity", "medium"))
            confidence = float(enhanced_result.get("confidence", 0.5))
            reasoning = enhanced_result.get("reasoning", "No reasoning provided")
            supporting_evidence = enhanced_result.get("supporting_evidence", [])
            recommended_actions = enhanced_result.get("suggested_actions", [])
            priority = await self._calculate_priority(severity, context)
            related_incidents = enhanced_result.get("kb_matches", [])
            
            return ClassificationResult(
                category=category,
                severity=severity,
                confidence=confidence,
                reasoning=reasoning,
                supporting_evidence=supporting_evidence,
                suggested_priority=priority,
                recommended_actions=recommended_actions,
                related_incidents=related_incidents,
                metadata={
                    "ai_analysis": ai_result,
                    "kb_enhanced": True,
                    "environment": context.get("environment", "unknown")
                },
                timestamp=datetime.utcnow()
            )
        except Exception as e:
            logger.error("Classification failed", extra={"error": str(e)}, exc_info=True)
            raise IncidentClassifierError(str(e))
    
    async def batch_analyze_incidents(self, incidents: List[Dict[str, Any]]) -> List[ClassificationResult]:
        """Batch analyze multiple incidents"""
        results = []
        for inc in incidents:
            try:
                result = await self.analyze_incident(
                    incident_text=inc["text"],
                    context=inc.get("context", {})
                )
                results.append(result)
            except Exception as e:
                results.append(ClassificationResult(
                    category=IncidentCategory.UNKNOWN,
                    severity=IncidentSeverity.MEDIUM,
                    confidence=0.0,
                    reasoning=f"Classification failed: {str(e)}",
                    supporting_evidence=[],
                    suggested_priority=3,
                    recommended_actions=["Review logs"],
                    related_incidents=[],
                    metadata={"error": str(e)},
                    timestamp=datetime.utcnow()
                ))
        return results
    
    def to_dict(self, result: ClassificationResult) -> Dict[str, Any]:
        """Convert result to dict"""
        r = asdict(result)
        r["category"] = result.category.value
        r["severity"] = result.severity.value
        r["timestamp"] = result.timestamp.isoformat()
        return r
    
    async def health_check(self) -> Dict[str, Any]:
        """Health check"""
        status = {"status": "healthy", "timestamp": datetime.utcnow().isoformat(), "components": {}}
        try:
            if hasattr(self.ai_service, "health_check"):
                await self.ai_service.health_check()
            status["components"]["ai_connector"] = "healthy"
        except Exception as e:
            status["components"]["ai_connector"] = f"unhealthy: {e}"
            status["status"] = "degraded"
        try:
            if not getattr(self.kb_loader, "_loaded", False):
                await self.kb_loader.load_kb()
            status["components"]["kb_loader"] = "healthy"
        except Exception as e:
            status["components"]["kb_loader"] = f"unhealthy: {e}"
            status["status"] = "degraded"
        return status
    
    async def cleanup(self) -> None:
        """Cleanup resources"""
        try:
            if hasattr(self.ai_service, "disconnect"):
                await self.ai_service.disconnect()
            logger.info("Incident classifier cleanup completed")
        except Exception as e:
            logger.warning(f"Cleanup failed: {e}")


# Factory
def create_incident_classifier(provider_name: Optional[str] = None, kb_path: Optional[str] = None) -> IncidentClassifierService:
    kb_loader = KBLoader(kb_path)
    return IncidentClassifierService(provider_name=provider_name, kb_loader=kb_loader)


# Example standalone test
if __name__ == "__main__":
    import asyncio
    async def main():
        classifier = create_incident_classifier(provider_name="gemini")
        incident = {
            "text": "Database timeout and connection issues detected in production",
            "context": {"environment": "production", "source": "monitoring_system"}
        }
        result = await classifier.analyze_incident(**incident)
        print(json.dumps(classifier.to_dict(result), indent=2))
    asyncio.run(main())
