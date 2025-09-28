"""Security middleware implementation."""
import time
import structlog
from typing import Dict, Any, Optional
from fastapi import Request, Response, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
import jwt
from datetime import datetime, timedelta

from app.core.config import get_settings
from app.abstracts.security import SecurityContext, SecurityEvent

logger = structlog.get_logger(__name__)


class SecurityMiddleware(BaseHTTPMiddleware):
    """Security middleware for request validation and rate limiting."""
    
    def __init__(self, app):
        super().__init__(app)
        self.settings = get_settings()
        self.rate_limit_store: Dict[str, Dict[str, Any]] = {}
        self.security_bearer = HTTPBearer(auto_error=False)
    
    async def dispatch(self, request: Request, call_next):
        """Process request through security middleware."""
        start_time = time.time()
        
        # Extract client information
        client_ip = self._get_client_ip(request)
        user_agent = request.headers.get("user-agent", "")
        
        # Log security event
        await self._log_security_event(
            event_type="request_received",
            ip_address=client_ip,
            resource=str(request.url.path),
            action=request.method,
            result="processing",
            details={
                "user_agent": user_agent,
                "query_params": dict(request.query_params)
            }
        )
        
        try:
            # Rate limiting check
            if not await self._check_rate_limit(client_ip, request.url.path):
                await self._log_security_event(
                    event_type="rate_limit_exceeded",
                    ip_address=client_ip,
                    resource=str(request.url.path),
                    action=request.method,
                    result="blocked"
                )
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Rate limit exceeded"}
                )
            
            # Security headers validation
            if not self._validate_security_headers(request):
                await self._log_security_event(
                    event_type="invalid_headers",
                    ip_address=client_ip,
                    resource=str(request.url.path),
                    action=request.method,
                    result="blocked"
                )
                return JSONResponse(
                    status_code=400,
                    content={"detail": "Invalid security headers"}
                )
            
            # Process request
            response = await call_next(request)
            
            # Add security headers to response
            response = self._add_security_headers(response)
            
            # Log successful request
            processing_time = time.time() - start_time
            await self._log_security_event(
                event_type="request_completed",
                ip_address=client_ip,
                resource=str(request.url.path),
                action=request.method,
                result="success",
                details={
                    "status_code": response.status_code,
                    "processing_time": processing_time
                }
            )
            
            return response
            
        except Exception as e:
            processing_time = time.time() - start_time
            await self._log_security_event(
                event_type="request_error",
                ip_address=client_ip,
                resource=str(request.url.path),
                action=request.method,
                result="error",
                details={
                    "error": str(e),
                    "processing_time": processing_time
                }
            )
            raise
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request."""
        # Check for forwarded headers first
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip
        
        # Fallback to direct client IP
        return request.client.host if request.client else "unknown"
    
    async def _check_rate_limit(self, identifier: str, resource: str) -> bool:
        """Check if request is within rate limits."""
        current_time = time.time()
        window_size = 60  # 1 minute window
        max_requests = 100  # Max requests per window
        
        # Clean old entries
        self.rate_limit_store = {
            k: v for k, v in self.rate_limit_store.items()
            if current_time - v.get("window_start", 0) < window_size
        }
        
        key = f"{identifier}:{resource}"
        
        if key not in self.rate_limit_store:
            self.rate_limit_store[key] = {
                "count": 1,
                "window_start": current_time
            }
            return True
        
        entry = self.rate_limit_store[key]
        
        # Check if we're in a new window
        if current_time - entry["window_start"] >= window_size:
            entry["count"] = 1
            entry["window_start"] = current_time
            return True
        
        # Increment count and check limit
        entry["count"] += 1
        return entry["count"] <= max_requests
    
    def _validate_security_headers(self, request: Request) -> bool:
        """Validate security-related headers."""
        # Skip validation for health checks and docs
        if request.url.path in ["/health", "/docs", "/redoc", "/openapi.json"]:
            return True
        
        # Add custom header validations here
        # For example, check for required API keys, CSRF tokens, etc.
        
        return True
    
    def _add_security_headers(self, response: Response) -> Response:
        """Add security headers to response."""
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = "default-src 'self'"
        
        return response
    
    async def _log_security_event(
        self,
        event_type: str,
        ip_address: str,
        resource: str,
        action: str,
        result: str,
        user_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log security event."""
        event = SecurityEvent(
            event_type=event_type,
            user_id=user_id,
            ip_address=ip_address,
            resource=resource,
            action=action,
            result=result,
            timestamp=datetime.now(),
            details=details
        )
        
        logger.info("Security event", **event.model_dump())


class JWTAuthService:
    """JWT authentication service."""
    
    def __init__(self):
        self.settings = get_settings()
        self.secret_key = self.settings.SECRET_KEY
        self.algorithm = self.settings.ALGORITHM
        self.access_token_expire_minutes = self.settings.ACCESS_TOKEN_EXPIRE_MINUTES
    
    def create_access_token(self, data: Dict[str, Any]) -> str:
        """Create JWT access token."""
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)
        to_encode.update({"exp": expire})
        
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt
    
    def verify_token(self, token: str) -> Dict[str, Any]:
        """Verify and decode JWT token."""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token has expired")
        except jwt.JWTError:
            raise HTTPException(status_code=401, detail="Invalid token")
    
    def get_security_context(self, token: str) -> SecurityContext:
        """Get security context from token."""
        payload = self.verify_token(token)
        
        return SecurityContext(
            user_id=payload.get("sub"),
            roles=payload.get("roles", []),
            permissions=payload.get("permissions", []),
            timestamp=datetime.now()
        )


# Dependency for JWT authentication
security_bearer = HTTPBearer()
jwt_service = JWTAuthService()


async def get_current_user(credentials: HTTPAuthorizationCredentials = security_bearer) -> SecurityContext:
    """Dependency to get current authenticated user."""
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    return jwt_service.get_security_context(credentials.credentials)


async def require_permissions(required_permissions: list):
    """Dependency factory for permission-based access control."""
    def permission_checker(context: SecurityContext = get_current_user) -> SecurityContext:
        if not any(perm in context.permissions for perm in required_permissions):
            raise HTTPException(
                status_code=403,
                detail=f"Required permissions: {required_permissions}"
            )
        return context
    
    return permission_checker
