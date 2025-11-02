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
    analysis_level: str = "L3"   # NEW: L1|L2|L3


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
            # Default KB (fallback). You can replace load with reading a JSON file if kb_path is provided.
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
                    "infrastructure": "high",
                    "software": "medium",
                    "network": "high",
                    "hardware": "high"
                },
                "context_rules": {
                    "production": {"multiplier": 1.5, "max_severity": "critical"},
                    "staging": {"multiplier": 1.2, "max_severity": "high"},
                    "development": {"multiplier": 0.8, "max_severity": "medium"}
                }
            }

            # If a KB JSON filepath was provided, attempt to load it (non-fatal)
            if self.kb_path:
                try:
                    with open(self.kb_path, "r", encoding="utf-8") as fh:
                        file_kb = json.load(fh)
                        # If the file wraps KB under "knowledge_base", normalize
                        if "knowledge_base" in file_kb:
                            self._kb_data = file_kb
                        else:
                            # allow older style content directly as "categories"
                            self._kb_data = {"knowledge_base": {"categories": file_kb}} if isinstance(file_kb, dict) else self._kb_data
                except Exception as e:
                    logger.warning(f"Could not load KB from {self.kb_path}, using defaults: {e}")

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

        # Support either direct patterns or wrapped KB structure
        if "patterns" in self._kb_data:
            patterns = self._kb_data.get("patterns", {}).get(pattern_type, [])
        else:
            patterns = []
        text_lower = (text or "").lower()
        return [p for p in patterns if p.lower() in text_lower]

    def get_severity_mapping(self, category: str) -> str:
        """Get default severity for a category"""
        if not self._loaded:
            # synchronous fallback: return medium
            return "medium"
        # If KB has 'knowledge_base' wrapper (as in your large KB), navigate into it
        kb = self._kb_data
        if "knowledge_base" in kb and "categories" in kb["knowledge_base"]:
            cat_def = kb["knowledge_base"]["categories"].get(category, {})
            # if KB category defines tier rules with severity mapping, use that; otherwise fallback to severity_mapping
            # try to derive severity from category-level definition (no direct mapping available in your JSON, so keep default)
            return self._kb_data.get("severity_mapping", {}).get(category, "medium")
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
        """Analyze incident using AI connector. Returns a dict (possibly empty) rather than raising on parse problems."""
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

            try:
                parsed_json = self._extract_json_from_ai(raw_text)
                # Ensure parsed_json is a dict
                if not isinstance(parsed_json, dict):
                    logger.warning("Parsed AI output is not a dict; falling back to empty dict")
                    return {}
                return parsed_json
            except Exception as parse_err:
                # Don't raise here — fallback to empty dict and continue with KB-only enhancement
                logger.warning(f"AI JSON parse failed, falling back to KB-only logic: {parse_err}", exc_info=True)
                return {}

        except Exception as e:
            logger.error("AI analysis failed", extra={"error": str(e)}, exc_info=True)
            # bubble up a more specific exception so callers can decide whether to continue
            raise IncidentClassifierError(f"AI analysis failed: {e}")

    def _get_ai_raw_text(self, ai_analysis) -> str:
        """Extract raw text from AI response"""
        raw_text = ""
        # Gemini format (candidates -> content -> parts)
        try:
            if hasattr(ai_analysis, "candidates") and ai_analysis.candidates:
                candidate = ai_analysis.candidates[0]
                parts = getattr(getattr(candidate, "content", {}), "parts", []) or []
                raw_text = "".join([getattr(p, "text", "") for p in parts if getattr(p, "text", None)]).strip()
        except Exception:
            # best effort; continue to other strategies
            logger.debug("gemini parsing flow did not match, trying alternate extraction")

        # OpenAI / default or fallback to string
        if not raw_text:
            raw_text = getattr(ai_analysis, "content", "") or str(ai_analysis) or ""
        return raw_text.strip()

    def _extract_json_from_ai(self, raw_text: str) -> Dict[str, Any]:
        """Safely extract JSON from AI output. Raises ValueError if not found."""
        if not raw_text or not raw_text.strip():
            raise ValueError("AI returned no content")

        # strip code fences
        content = raw_text.replace("```json", "").replace("```", "").strip()

        # find first JSON object in the text
        start = content.find("{")
        end = content.rfind("}")
        if start == -1 or end == -1 or end < start:
            # try to handle simple key-value lines "key: value" -> convert to dict
            import re
            kv_lines = re.findall(r'^\s*("?(\w+)"?)\s*[:=]\s*(.+)$', content, flags=re.MULTILINE)
            if kv_lines:
                parsed = {}
                for full, key, val in kv_lines:
                    # remove trailing commas and code fences
                    v = val.strip().rstrip(",")
                    # try to convert JSON-like values
                    try:
                        parsed_val = json.loads(v)
                    except Exception:
                        parsed_val = v.strip().strip('"').strip("'")
                    parsed[key] = parsed_val
                return parsed
            raise ValueError("No JSON object found in AI output")

        json_substr = content[start:end + 1]
        try:
            return json.loads(json_substr)
        except json.JSONDecodeError:
            # fallback: extract simple "key": "value" pairs
            import re
            kv_pairs = re.findall(r'"([\w_]+)"\s*:\s*(".*?"|\d+(\.\d+)?|true|false|null)', json_substr, flags=re.IGNORECASE)
            if kv_pairs:
                simple = {}
                for k, v, _ in kv_pairs:
                    vs = v
                    # strip quotes
                    vs = vs.strip()
                    if vs.startswith('"') and vs.endswith('"'):
                        vs = vs[1:-1]
                    # convert numbers/booleans/null where possible
                    if vs.lower() in ("true", "false", "null"):
                        simple[k] = {"true": True, "false": False, "null": None}[vs.lower()]
                    else:
                        try:
                            if "." in vs:
                                simple[k] = float(vs)
                            else:
                                simple[k] = int(vs)
                        except Exception:
                            simple[k] = vs
                return simple
            # give up
            raise ValueError("AI JSON extraction failed: invalid JSON structure")

    async def _enhance_with_kb(self, ai_result: Dict[str, Any], incident_text: str) -> Dict[str, Any]:
        """Enhance AI result using full KB context"""
        try:
            if not getattr(self.kb_loader, "_loaded", False):
                await self.kb_loader.load_kb()

            kb_data = self.kb_loader._kb_data
            # If KB is the big wrapped object, navigate into categories
            if "knowledge_base" in kb_data and "categories" in kb_data["knowledge_base"]:
                categories = kb_data["knowledge_base"]["categories"]
            else:
                # KB default structure: categories may be at top-level
                categories = kb_data.get("categories", {}) or kb_data.get("knowledge_base", {}) or {}

            text_lower = (incident_text or "").lower()
            best_match = None
            match_score = 0

            # --- Category detection based on keyword frequency ---
            for category_name, cat_data in categories.items():
                keywords = cat_data.get("keywords", [])
                # count occurrences (simple containment)
                count = sum(1 for kw in keywords if kw and kw.lower() in text_lower)
                if count > match_score:
                    match_score = count
                    best_match = category_name

            # If KB does not match any category, prefer AI result category if provided
            if not best_match:
                best_match = ai_result.get("category") or "unknown"

            # Normalize category: KB's keys might be 'network' 'application' etc.
            normalized_category = str(best_match).lower() if best_match else "unknown"

            category_data = categories.get(best_match, {}) or categories.get(normalized_category, {})

            tier_rules = category_data.get("tier_rules", {}) if isinstance(category_data, dict) else {}

            # --- Determine tier (L1/L2/L3) based on keywords ---
            analysis_level = ai_result.get("analysis_level") or "L3"
            tier_match_score = {"L1": 0, "L2": 0, "L3": 0}

            for tier, tier_data in (tier_rules.items() if isinstance(tier_rules, dict) else []):
                for kw in tier_data.get("keywords", []):
                    if kw and kw.lower() in text_lower:
                        tier_match_score[tier] = tier_match_score.get(tier, 0) + 1

            if any(tier_match_score.values()):
                # pick tier with highest count (ties arbitrarily resolved by max)
                analysis_level = max(tier_match_score, key=lambda k: tier_match_score[k])

            # --- Severity Mapping (based on KB or analysis_level) ---
            # prefer KB-provided mapping for category if available, else use analysis_level->severity mapping
            default_severity = self.kb_loader.get_severity_mapping(normalized_category) or "medium"

            if not default_severity:
                # Map analysis_level to severity (L1 -> critical, L2 -> high, L3 -> medium)
                if analysis_level == "L1":
                    default_severity = "critical"
                elif analysis_level == "L2":
                    default_severity = "high"
                else:
                    default_severity = "medium"

            # Coerce severity to known enum-friendly string
            default_severity = str(default_severity).lower()

            # --- Suggested Priority derived from severity + context ---
            try:
                severity_enum = IncidentSeverity(default_severity)
            except Exception:
                severity_enum = IncidentSeverity.MEDIUM

            suggested_priority = await self._calculate_priority(severity_enum, {"environment": "production"})

            # --- Merge everything back into the AI result ---
            enhanced = dict(ai_result or {})
            enhanced.update({
                "category": normalized_category,
                "kb_matches": match_score,
                "analysis_level": analysis_level,
                "severity": default_severity,
                "suggested_priority": suggested_priority,
                "kb_applied": True
            })

            logger.info(f"KB enhanced: category={normalized_category}, level={analysis_level}, severity={default_severity}, priority={suggested_priority}")
            return enhanced

        except Exception as e:
            logger.error(f"❌ KB enhancement failed: {e}", exc_info=True)
            return ai_result or {}

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
            priority = max(1, int(priority * float(context_rule.get("multiplier", 1.0))))
        return priority

    def _determine_analysis_level(self, severity: IncidentSeverity, suggested_priority: int) -> str:
        """
        Determine analysis_level L1/L2/L3:
        - L1: critical/high or priority 1-2
        - L2: medium or priority 3
        - L3: low/info or priority >=4
        """
        sev = severity.value if isinstance(severity, IncidentSeverity) else str(severity)
        if sev in ("critical", "high") or suggested_priority in (1, 2):
            return "L1"
        if sev in ("medium",) or suggested_priority == 3:
            return "L2"
        return "L3"

    def _safe_category(self, value: Optional[str]) -> IncidentCategory:
        """Return an IncidentCategory enum value with safe fallback"""
        if not value:
            return IncidentCategory.UNKNOWN
        try:
            # normalize common variants
            v = str(value).strip().lower()
            # if it's already one of enum values, map directly
            for cat in IncidentCategory:
                if cat.value == v:
                    return cat
            # try a few synonyms
            mapping = {
                "app": "functionality",
                "application": "functionality",
                "software": "software" if "software" in [c.value for c in IncidentCategory] else "functionality",
                "network": "infrastructure",
                "infra": "infrastructure",
            }
            mapped = mapping.get(v, v)
            for cat in IncidentCategory:
                if cat.value == mapped:
                    return cat
            return IncidentCategory.UNKNOWN
        except Exception:
            return IncidentCategory.UNKNOWN

    def _safe_severity(self, value: Optional[str]) -> IncidentSeverity:
        """Return an IncidentSeverity enum value with safe fallback"""
        if not value:
            return IncidentSeverity.MEDIUM
        try:
            v = str(value).strip().lower()
            for sev in IncidentSeverity:
                if sev.value == v:
                    return sev
            # synonyms
            synonyms = {
                "critical": "critical",
                "crit": "critical",
                "high": "high",
                "medium": "medium",
                "med": "medium",
                "low": "low",
                "info": "info",
            }
            mapped = synonyms.get(v, "medium")
            return IncidentSeverity(mapped)
        except Exception:
            return IncidentSeverity.MEDIUM

    async def analyze_incident(self, incident_text: str, context: Optional[Dict[str, Any]] = None) -> ClassificationResult:
        """Main entrypoint: analyze incident"""
        try:
            await self._ensure_initialized()
            context = context or {}

            # run AI; do not fail hard if AI produces no JSON (we will rely on KB)
            try:
                ai_result = await self._analyze_with_ai(incident_text, context)
            except IncidentClassifierError as e:
                # If AI subsystem failed, log and treat as empty ai_result so KB controls outcome
                logger.warning(f"AI subsystem returned error, proceeding with KB-only fallback: {e}")
                ai_result = {}

            # Use AI result but enhance with KB (KB will try to find categories/tiers if AI incomplete)
            enhanced_result = await self._enhance_with_kb(ai_result or {}, incident_text)

            # Safely convert category/severity strings to enums with defaults
            cat_str = enhanced_result.get("category") or enhanced_result.get("kb_category") or "unknown"
            sev_str = enhanced_result.get("severity") or enhanced_result.get("default_severity") or "medium"

            category_enum = self._safe_category(cat_str)
            severity_enum = self._safe_severity(sev_str)

            confidence = float(enhanced_result.get("confidence", 0.5))
            reasoning = enhanced_result.get("reasoning", "No reasoning provided")
            supporting_evidence = enhanced_result.get("supporting_evidence", []) or []
            # Accept either "suggested_actions" or "recommended_actions"
            recommended_actions = enhanced_result.get("suggested_actions") or enhanced_result.get("recommended_actions") or []
            # suggested_priority may be provided by KB enhancement; otherwise calculate
            suggested_priority = enhanced_result.get("suggested_priority")
            if suggested_priority is None:
                suggested_priority = await self._calculate_priority(severity_enum, context)

            related_incidents = enhanced_result.get("related_incidents") or enhanced_result.get("kb_matches") or []

            # Determine analysis level: prefer enhanced_result.analysis_level if present, else derive
            analysis_level = enhanced_result.get("analysis_level")
            if not analysis_level:
                analysis_level = self._determine_analysis_level(severity_enum, int(suggested_priority))

            # Build ClassificationResult dataclass
            result = ClassificationResult(
                category=category_enum,
                severity=severity_enum,
                confidence=confidence,
                reasoning=reasoning,
                supporting_evidence=supporting_evidence,
                suggested_priority=int(suggested_priority),
                recommended_actions=recommended_actions,
                related_incidents=related_incidents,
                metadata={
                    "ai_analysis": ai_result,
                    "kb_enhanced": True,
                    "environment": context.get("environment", "unknown"),
                    "raw_enhanced": enhanced_result
                },
                timestamp=datetime.utcnow(),
                analysis_level=analysis_level
            )
            return result
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
                    timestamp=datetime.utcnow(),
                    analysis_level="L3"
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
