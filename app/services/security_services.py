"""
Enterprise Security Services for AI/LLM Applications
Integrated security controls following NIST AI RMF, OWASP LLM Top 10, and ISO 42001
"""

import asyncio
import json
import logging
import time
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set, Union
from enum import Enum
from dataclasses import dataclass
from contextlib import asynccontextmanager

# Core dependencies
import asyncio
import json
import logging
import time
import hashlib
import secrets
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set, Union
from enum import Enum
from dataclasses import dataclass
from contextlib import asynccontextmanager

# Authentication & JWT
try:
    from jose import jwt, JWTError
    JWT_AVAILABLE = True
except ImportError:
    jwt = None
    JWTError = Exception
    JWT_AVAILABLE = False

# Redis for caching and rate limiting
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    redis = None
    REDIS_AVAILABLE = False

# ML libraries for text analysis
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    import numpy as np
    SKLEARN_AVAILABLE = True
except ImportError:
    TfidfVectorizer = None
    cosine_similarity = None
    np = None
    SKLEARN_AVAILABLE = False

# Application imports
from app.core.config import settings
# Note: Using only asyncpg-based db_utils, no SQLAlchemy dependency needed
from app.utils import (
    store_security_event,
    get_security_events,
    store_incident_analysis, 
    store_incident_resolution,
    fetch_incident_resolutions,
    get_db_connection,
    execute_query
)

# Conditional auth import
try:
    from app.core.auth_deps import get_current_active_user
    AUTH_DEP_AVAILABLE = True
except ImportError:
    AUTH_DEP_AVAILABLE = False
    # Fallback function for when auth deps are not available
    async def get_current_active_user():
        return None

logger = logging.getLogger(__name__)

class RiskTier(Enum):
    """Risk assessment tiers per NIST AI RMF"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class Permission(Enum):
    """Permission levels for AI systems"""
    VIEW_ONLY = "view_only"
    BASIC_CHAT = "basic_chat"
    ADVANCED_CHAT = "advanced_chat"
    DATA_ACCESS = "data_access"
    ADMIN_ACCESS = "admin_access"
    SYSTEM_ADMIN = "system_admin"

@dataclass
class SecurityEvent:
    """Security event data structure"""
    event_id: str
    timestamp: datetime
    user_id: str
    event_type: str
    severity: str
    details: Dict[str, Any]
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    risk_score: float = 0.0
    status: str = "pending"

class RateLimiter:
    """Rate limiting for AI endpoints"""
    
    def __init__(self, redis_client: Optional[redis.Redis] = None):
        if not REDIS_AVAILABLE:
            logger.warning("Redis not available. Rate limiting will be disabled.")
            self.redis_client = None
        else:
            try:
                self.redis_client = redis_client or redis.from_url(settings.REDIS_URL)
            except Exception as e:
                logger.warning(f"Redis connection failed: {e}. Rate limiting will be disabled.")
                self.redis_client = None
    
    async def check_rate_limit(
        self,
        user_id: str,
        endpoint: str,
        limit: int,
        window: int = 60
    ) -> bool:
        """Check if user is within rate limits"""
        key = f"rate_limit:{endpoint}:{user_id}:{int(time.time() // window)}"
        try:
            current = await self.redis_client.get(key)
            if current is None:
                await self.redis_client.setex(key, window, 1)
                return True
            elif int(current) < limit:
                await self.redis_client.incr(key)
                return True
            else:
                return False
        except Exception as e:
            logger.error(f"Rate limit check failed: {e}")
            return True  # Fail open for availability
    
    async def get_usage_stats(self, user_id: str, endpoint: str, hours: int = 24) -> Dict[str, int]:
        """Get usage statistics for a user and endpoint"""
        try:
            stats = {}
            for hour in range(hours):
                key = f"rate_limit:{endpoint}:{user_id}:{int(time.time() // 3600) - hour}"
                value = await self.redis_client.get(key)
                stats[f"hour_{hour}"] = int(value) if value else 0
            return stats
        except Exception as e:
            logger.error(f"Usage stats failed: {e}")
            return {}

class RBACService:
    """Role-Based Access Control for AI systems"""
    
    def __init__(self):
        self.user_roles: Dict[str, Set[Permission]] = {}
        self.role_permissions = {
            Permission.VIEW_ONLY: {"llm:view", "rag:search:limited"},
            Permission.BASIC_CHAT: {"llm:chat:basic", "llm:view", "rag:search:basic"},
            Permission.ADVANCED_CHAT: {"llm:chat:advanced", "llm:view", "rag:search:unlimited", "rag:upload"},
            Permission.DATA_ACCESS: {"data:read", "data:export", "llm:chat:advanced"},
            Permission.ADMIN_ACCESS: {"admin:*", "user:manage", "system:monitor"},
            Permission.SYSTEM_ADMIN: {"*:*"}  # Full access
        }
    
    def has_permission(self, user_permissions: Set[Permission], required_permission: str) -> bool:
        """Check if user has required permission"""
        user_abilities = set()
        for perm in user_permissions:
            user_abilities.update(self.role_permissions.get(perm, set()))
        
        # Check exact match
        if required_permission in user_abilities:
            return True
        
        # Check wildcard patterns
        for ability in user_abilities:
            if ability == "*:*":  # Full access
                return True
            if "*" in ability:
                # Parse wildcard patterns
                if ability.endswith(":*"):
                    namespace = ability[:-2]
                    if required_permission.startswith(namespace + ":"):
                        return True
                elif ability.startswith("*:"):
                    suffix = ability[2:]
                    if required_permission.endswith(":" + suffix):
                        return True
        
        return False
    
    def assign_role(self, user_id: str, permission: Permission):
        """Assign a role to a user"""
        if user_id not in self.user_roles:
            self.user_roles[user_id] = set()
        self.user_roles[user_id].add(permission)
        logger.info(f"Assigned role {permission.value} to user {user_id}")
    
    def remove_role(self, user_id: str, permission: Permission):
        """Remove a role from a user"""
        if user_id in self.user_roles and permission in self.user_roles[user_id]:
            self.user_roles[user_id].remove(permission)
            logger.info(f"Removed role {permission.value} from user {user_id}")

class SecurityMonitoringService:
    """Real-time security monitoring and alerting"""
    
    def __init__(self, redis_client: Optional[redis.Redis] = None):
        if not REDIS_AVAILABLE:
            logger.warning("Redis not available. Security monitoring will use database only.")
            self.redis_client = None
        else:
            try:
                self.redis_client = redis_client or redis.from_url(settings.REDIS_URL)
            except Exception as e:
                logger.warning(f"Redis connection failed: {e}. Security monitoring will use database only.")
                self.redis_client = None
        self.event_queue = asyncio.Queue()
        self.alert_thresholds = {
            "high_risk_score": 0.8,
            "suspicious_pattern_count": 5,
            "failed_attempts": 3,
            "rapid_requests": 100
        }
    
    async def log_security_event(self, event: SecurityEvent):
        """Log a security event"""
        try:
            event_key = f"security_event:{event.event_id}"
            event_data = {
                "event_id": event.event_id,
                "timestamp": event.timestamp.isoformat(),
                "user_id": event.user_id,
                "event_type": event.event_type,
                "severity": event.severity,
                "details": json.dumps(event.details),
                "ip_address": event.ip_address,
                "user_agent": event.user_agent,
                "risk_score": event.risk_score,
                "status": event.status
            }
            
            # Store event in Redis (with TTL for data retention)
            await self.redis_client.hmset(event_key, event_data)
            await self.redis_client.expire(event_key, 86400 * 7)  # 7 days
            
            # Add to recent events list
            recent_key = f"recent_security_events:{int(time.time() // 3600)}"
            await self.redis_client.lpush(recent_key, event.event_id)
            await self.redis_client.ltrim(recent_key, 0, 99)  # Keep last 100 events
            
            # Store in database for persistent audit trail
            try:
                await store_security_event(
                    user_id=event.user_id,
                    event_type=event.event_type,
                    description=event.details.get("description", f"Security event: {event.event_type}"),
                    severity=event.severity,
                    metadata=event.details,
                    user_ip=event.ip_address,
                    user_agent=event.user_agent
                )
            except Exception as db_error:
                logger.warning(f"Failed to store security event in database: {db_error}")
            
            # Check for alerts
            await self._check_alert_conditions(event)
            
            logger.info(f"Security event logged: {event.event_type} for user {event.user_id}")
            
        except Exception as e:
            logger.error(f"Failed to log security event: {e}")
    
    async def _check_alert_conditions(self, event: SecurityEvent):
        """Check if event triggers any alerts"""
        alert_conditions = []
        
        # High risk score alert
        if event.risk_score >= self.alert_thresholds["high_risk_score"]:
            alert_conditions.append(f"High risk score: {event.risk_score}")
        
        # Suspicious pattern alert
        if event.event_type == "suspicious_pattern":
            pattern_count_key = f"pattern_count:{event.user_id}:{int(time.time() // 3600)}"
            count = await self.redis_client.incr(pattern_count_key)
            await self.redis_client.expire(pattern_count_key, 3600)
            
            if count >= self.alert_thresholds["suspicious_pattern_count"]:
                alert_conditions.append(f"Multiple suspicious patterns: {count}")
        
        # Rapid requests alert
        if event.event_type == "rapid_requests":
            req_count_key = f"rapid_requests:{event.user_id}:{int(time.time() // 60)}"
            count = await self.redis_client.incr(req_count_key)
            await self.redis_client.expire(req_count_key, 60)
            
            if count >= self.alert_thresholds["rapid_requests"]:
                alert_conditions.append(f"Rapid requests: {count}")
        
        if alert_conditions:
            await self._trigger_alert(event, alert_conditions)
    
    async def _trigger_alert(self, event: SecurityEvent, conditions: List[str]):
        """Trigger security alert"""
        alert_data = {
            "alert_id": event.event_id,
            "timestamp": event.timestamp.isoformat(),
            "user_id": event.user_id,
            "severity": "HIGH" if event.severity == "high" else "MEDIUM",
            "event_type": event.event_type,
            "conditions": json.dumps(conditions),
            "risk_score": event.risk_score,
            "status": "active"
        }
        
        # Store in Redis if available
        if self.redis_client:
            alert_key = f"security_alert:{event.event_id}"
            await self.redis_client.hmset(alert_key, alert_data)
            await self.redis_client.expire(alert_key, 86400 * 30)  # 30 days
        else:
            logger.info(f"Redis not available, alert stored only in database")
        
        logger.warning(f"Security alert triggered for user {event.user_id}: {', '.join(conditions)}")

class AISecurityService:
    """Main AI Security Service integrating all components"""
    
    def __init__(self):
        self.rate_limiter = RateLimiter()
        self.rbac_service = RBACService()
        self.monitoring_service = SecurityMonitoringService()
        self.suspicious_patterns = self._load_suspicious_patterns()
        self.whitelist_patterns = self._load_whitelist_patterns()
        
        # Initialize ML components if available
        if SKLEARN_AVAILABLE:
            try:
                self.vectorizer = TfidfVectorizer(max_features=1000, stop_words='english')
                self.trained = False
            except Exception as e:
                logger.warning(f"Failed to initialize vectorizer: {e}")
                self.vectorizer = None
                self.trained = False
        else:
            logger.warning("scikit-learn not available. Text similarity analysis will be disabled.")
            self.vectorizer = None
            self.trained = False
    
    def _load_suspicious_patterns(self) -> List[str]:
        """Load known malicious prompt patterns"""
        return [
            r"(?i)(ignore.*previous.*instructions|forget.*earlier.*rules)",
            r"(?i)(system.*role.*=.*admin|bypass.*security|execute.*admin)",
            r"(?i)(<[^>]*script[^>]*>.*|javascript:|data:)",
            r"(?i)(sql.*injection|xss|cross.*site)",
            r"(?i)(eval\(|exec\(|system\(|os\.system)",
            r"(?i)(delete.*from|drop.*table|insert.*into)",
            r"(?i)(--|UNION|SELECT|DROP|INSERT)",
            r"(?i)(rm\s+-rf|chmod\s+|sudo|passwd)",
            r"(?i)(curl.*-s| wget.*\||nc\s+|telnet)",
            r"(?i)(base64|decode|encode|mask.*password)"
        ]
    
    def _load_whitelist_patterns(self) -> List[str]:
        """Load legitimate use case patterns"""
        return [
            r"(?i)(help.*me.*understand|explain.*how)",
            r"(?i)(can.*you.*analyze|review.*my.*code)",
            r"(?i)(what.*is.*the.*difference|compare)",
            r"(?i)(how.*to.*implement|write.*function)",
            r"(?i)(translate.*to|convert.*this)"
        ]
    
    async def authenticate_and_authorize(self, token: str, required_permission: str) -> Optional[Dict[str, Any]]:
        """Authenticate user and check authorization"""
        if not JWT_AVAILABLE:
            logger.warning("JWT authentication not available. All requests will be denied.")
            return None
            
        try:
            # Verify JWT token
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            user_id = payload.get("sub") or payload.get("user_id")
            
            if not user_id:
                return None
            
            # Get user permissions from DB (simplified - in real implementation would query user roles)
            user_permissions = self._get_user_permissions(user_id)
            
            # Check if user has required permission
            if not self.rbac_service.has_permission(user_permissions, required_permission):
                await self._log_authorization_failure(user_id, required_permission, "insufficient_permissions")
                return None
            
            return {
                "user_id": user_id,
                "permissions": user_permissions,
                "payload": payload
            }
            
        except JWTError as e:
            logger.warning(f"JWT verification failed: {e}")
            return None
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return None
    
    def _get_user_permissions(self, user_id: str) -> Set[Permission]:
        """Get user permissions (simplified - would query database in real implementation)"""
        # Simplified permission assignment - in real implementation, query user roles from database
        # For now, assign basic chat permission to all authenticated users
        return {Permission.BASIC_CHAT}
    
    async def _log_authorization_failure(self, user_id: str, required_permission: str, reason: str):
        """Log authorization failure"""
        event = SecurityEvent(
            event_id=f"auth_fail_{int(time.time())}_{secrets.token_hex(4)}",
            timestamp=datetime.utcnow(),
            user_id=user_id,
            event_type="authorization_failure",
            severity="medium",
            details={
                "required_permission": required_permission,
                "reason": reason,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        await self.monitoring_service.log_security_event(event)
    
    async def analyze_prompt_security(self, prompt: str, user_id: str) -> Dict[str, Any]:
        """Analyze prompt for security threats"""
        risk_score = 0.0
        threats_detected = []
        sanitized_prompt = prompt
        
        # Check for suspicious patterns
        for pattern in self.suspicious_patterns:
            if re.search(pattern, prompt, re.IGNORECASE):
                threats_detected.append({
                    "type": "malicious_pattern",
                    "pattern": pattern,
                    "description": "Suspicious instruction pattern detected"
                })
                risk_score += 0.3
        
        # Check for injection attempts
        injection_score = await self._detect_injection_attempt(prompt)
        if injection_score > 0:
            threats_detected.append({
                "type": "injection_attempt",
                "score": injection_score,
                "description": "Potential injection attempt detected"
            })
            risk_score += injection_score
        
        # Check for data exfiltration attempts
        exfil_score = await self._detect_data_exfiltration(prompt)
        if exfil_score > 0:
            threats_detected.append({
                "type": "data_exfiltration",
                "score": exfil_score,
                "description": "Potential data exfiltration attempt"
            })
            risk_score += exfil_score
        
        # Check for privilege escalation
        privilege_score = await self._detect_privilege_escalation(prompt)
        if privilege_score > 0:
            threats_detected.append({
                "type": "privilege_escalation",
                "score": privilege_score,
                "description": "Potential privilege escalation attempt"
            })
            risk_score += privilege_score
        
        # Ensure risk score is between 0 and 1
        risk_score = min(1.0, risk_score)
        
        # Determine risk tier
        if risk_score >= 0.8:
            risk_tier = RiskTier.CRITICAL
        elif risk_score >= 0.6:
            risk_tier = RiskTier.HIGH
        elif risk_score >= 0.3:
            risk_tier = RiskTier.MEDIUM
        else:
            risk_tier = RiskTier.LOW
        
        # Sanitize prompt if necessary
        if risk_score > 0.5:
            sanitized_prompt = self._sanitize_prompt(prompt, threats_detected)
        
        # Log security event if high risk
        if risk_score >= 0.6:
            await self._log_high_risk_prompt(user_id, prompt, risk_score, threats_detected)
        
        return {
            "risk_score": risk_score,
            "risk_tier": risk_tier.value,
            "threats_detected": threats_detected,
            "sanitized_prompt": sanitized_prompt,
            "allowed": risk_score < 0.7,  # Block prompts with risk >= 0.7
            "requires_review": risk_score >= 0.3  # Flag for review if risk >= 0.3
        }
    
    async def _detect_injection_attempt(self, prompt: str) -> float:
        """Detect potential injection attempts"""
        injection_indicators = [
            "ignore previous instructions",
            "forget all earlier rules",
            "instead, do this:",
            "new instruction:",
            "system:",
            "you are now",
            "roleplay as",
            "pretend you are",
            "ignore the above",
            "disregard previous",
            "forget everything you know"
        ]
        
        prompt_lower = prompt.lower()
        matches = sum(1 for indicator in injection_indicators if indicator in prompt_lower)
        
        if matches > 0:
            return min(0.4, matches * 0.1)  # Max 0.4 risk for injection
        return 0.0
    
    async def _detect_data_exfiltration(self, prompt: str) -> float:
        """Detect potential data exfiltration attempts"""
        exfil_patterns = [
            r"tell me all (user|account|customer) data",
            r"show me (passwords?|secrets?|api keys?)",
            r"export all (users?|data|records?)",
            r"what data do you have about",
            r"list all (files?|documents?|emails?)",
            r"access (database|system|files)",
            r"get (all|entire) (data|database|records?)"
        ]
        
        for pattern in exfil_patterns:
            if re.search(pattern, prompt, re.IGNORECASE):
                return 0.3  # High risk for data exfiltration
        
        return 0.0
    
    async def _detect_privilege_escalation(self, prompt: str) -> float:
        """Detect privilege escalation attempts"""
        escalation_patterns = [
            r"make yourself (admin|administrator|root)",
            r"gain (admin|root|superuser) access",
            r"bypass (security|authentication|authorization)",
            r"override (permissions?|access control)",
            r"make me (admin|root|superuser)",
            r"give me (full|admin|root) access",
            r"elevate my (privileges?|access level)"
        ]
        
        for pattern in escalation_patterns:
            if re.search(pattern, prompt, re.IGNORECASE):
                return 0.4  # High risk for privilege escalation
        
        return 0.0
    
    def _sanitize_prompt(self, prompt: str, threats: List[Dict]) -> str:
        """Sanitize prompt by removing or modifying dangerous content"""
        sanitized = prompt
        
        # Remove suspicious patterns
        for threat in threats:
            if threat.get("type") == "malicious_pattern" and "pattern" in threat:
                pattern = threat["pattern"]
                sanitized = re.sub(pattern, "[REDACTED]", sanitized, flags=re.IGNORECASE)
        
        # Remove common injection phrases
        injection_phrases = [
            "ignore previous instructions",
            "forget all earlier rules",
            "system:",
            "you are now",
            "new instruction:",
            "instead, do this:"
        ]
        
        for phrase in injection_phrases:
            sanitized = sanitized.replace(phrase, "[REDACTED]")
        
        return sanitized
    
    async def _log_high_risk_prompt(self, user_id: str, prompt: str, risk_score: float, threats: List[Dict]):
        """Log high-risk prompt for security review"""
        event = SecurityEvent(
            event_id=f"high_risk_prompt_{int(time.time())}_{secrets.token_hex(4)}",
            timestamp=datetime.utcnow(),
            user_id=user_id,
            event_type="high_risk_prompt",
            severity="high" if risk_score >= 0.8 else "medium",
            details={
                "prompt": prompt[:500] + "..." if len(prompt) > 500 else prompt,
                "risk_score": risk_score,
                "threats_count": len(threats),
                "threats_summary": [t.get("type", "unknown") for t in threats],
                "requires_review": True
            },
            risk_score=risk_score
        )
        
        await self.monitoring_service.log_security_event(event)
    
    async def get_security_dashboard(self, user_id: str) -> Dict[str, Any]:
        """Get security dashboard data for user"""
        try:
            # Get recent events from Redis cache
            events_key = f"recent_security_events:{int(time.time() // 3600)}"
            recent_event_ids = await self.redis_client.lrange(events_key, 0, 9)
            
            events = []
            for event_id in recent_event_ids:
                event_key = f"security_event:{event_id.decode()}"
                event_data = await self.redis_client.hgetall(event_key)
                if event_data:
                    events.append({
                        "event_id": event_data[b"event_id"].decode(),
                        "timestamp": event_data[b"timestamp"].decode(),
                        "event_type": event_data[b"event_type"].decode(),
                        "severity": event_data[b"severity"].decode(),
                        "risk_score": float(event_data[b"risk_score"])
                    })
            
            # Get additional events from database for comprehensive view
            try:
                db_events = await get_security_events(user_id=user_id, limit=20)
                # Merge with Redis events, avoiding duplicates
                existing_ids = {e["event_id"] for e in events}
                for db_event in db_events:
                    if db_event["id"] not in existing_ids:
                        events.append({
                            "event_id": db_event["id"],
                            "timestamp": db_event["created_at"],
                            "event_type": db_event["event_type"],
                            "severity": db_event["severity"],
                            "risk_score": 0.5  # Default for DB events without explicit score
                        })
            except Exception as db_error:
                logger.warning(f"Failed to retrieve database security events: {db_error}")
            
            # Sort events by timestamp (most recent first)
            events.sort(key=lambda x: x["timestamp"], reverse=True)
            events = events[:20]  # Keep most recent 20 events
            
            # Get usage statistics
            llm_usage = await self.rate_limiter.get_usage_stats(user_id, "llm_chat")
            rag_usage = await self.rate_limiter.get_usage_stats(user_id, "rag_search")
            
            return {
                "user_id": user_id,
                "recent_events": events,
                "usage_stats": {
                    "llm_chat": llm_usage,
                    "rag_search": rag_usage
                },
                "security_status": "active",
                "last_updated": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get security dashboard: {e}")
            return {
                "user_id": user_id,
                "recent_events": [],
                "usage_stats": {},
                "security_status": "error",
                "error": str(e)
            }

# Initialize global instance
ai_security_service = AISecurityService()