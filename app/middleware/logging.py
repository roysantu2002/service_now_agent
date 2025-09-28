"""Logging middleware implementation."""
import time
import uuid
import structlog
from typing import Dict, Any
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import json

logger = structlog.get_logger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    """Logging middleware for request/response tracking."""
    
    def __init__(self, app):
        super().__init__(app)
    
    async def dispatch(self, request: Request, call_next):
        """Process request through logging middleware."""
        # Generate correlation ID for request tracking
        correlation_id = str(uuid.uuid4())
        
        # Add correlation ID to request state
        request.state.correlation_id = correlation_id
        
        # Log request start
        start_time = time.time()
        
        request_body = None
        if request.method in ["POST", "PUT", "PATCH"]:
            try:
                body = await request.body()
                if body:
                    request_body = body.decode("utf-8")
                    # Re-create request with body for downstream processing
                    request._body = body
            except Exception as e:
                logger.warning("Could not read request body", error=str(e))
        
        logger.info(
            "Request started",
            correlation_id=correlation_id,
            method=request.method,
            url=str(request.url),
            path=request.url.path,
            query_params=dict(request.query_params),
            headers=dict(request.headers),
            client_ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            request_body_size=len(request_body) if request_body else 0
        )
        
        try:
            # Process request
            response = await call_next(request)
            
            # Calculate processing time
            processing_time = time.time() - start_time
            
            # Read response body for logging (if needed)
            response_body = None
            if hasattr(response, 'body'):
                try:
                    response_body = response.body.decode('utf-8') if response.body else None
                except:
                    response_body = "<binary_content>"
            
            # Log successful response
            logger.info(
                "Request completed",
                correlation_id=correlation_id,
                method=request.method,
                url=str(request.url),
                path=request.url.path,
                status_code=response.status_code,
                processing_time=processing_time,
                response_headers=dict(response.headers),
                response_body_size=len(response_body) if response_body else 0
            )
            
            # Add correlation ID to response headers
            response.headers["X-Correlation-ID"] = correlation_id
            
            return response
            
        except Exception as e:
            # Calculate processing time for error case
            processing_time = time.time() - start_time
            
            # Log error
            logger.error(
                "Request failed",
                correlation_id=correlation_id,
                method=request.method,
                url=str(request.url),
                path=request.url.path,
                processing_time=processing_time,
                error=str(e),
                error_type=type(e).__name__
            )
            
            # Re-raise the exception
            raise


class StructuredLogger:
    """Enhanced structured logger with context management."""
    
    def __init__(self, name: str):
        self.logger = structlog.get_logger(name)
        self.context: Dict[str, Any] = {}
    
    def bind(self, **kwargs) -> 'StructuredLogger':
        """Bind context to logger."""
        new_logger = StructuredLogger(self.logger._logger.name)
        new_logger.context = {**self.context, **kwargs}
        new_logger.logger = self.logger.bind(**new_logger.context)
        return new_logger
    
    def info(self, message: str, **kwargs):
        """Log info message with context."""
        self.logger.info(message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        """Log warning message with context."""
        self.logger.warning(message, **kwargs)
    
    def error(self, message: str, **kwargs):
        """Log error message with context."""
        self.logger.error(message, **kwargs)
    
    def debug(self, message: str, **kwargs):
        """Log debug message with context."""
        self.logger.debug(message, **kwargs)
    
    def critical(self, message: str, **kwargs):
        """Log critical message with context."""
        self.logger.critical(message, **kwargs)


def get_logger(name: str) -> StructuredLogger:
    """Get a structured logger instance."""
    return StructuredLogger(name)


class AuditLogger:
    """Audit logger for compliance and security events."""
    
    def __init__(self):
        self.logger = structlog.get_logger("audit")
    
    async def log_data_access(
        self,
        user_id: str,
        resource: str,
        action: str,
        data_classification: str,
        success: bool,
        details: Dict[str, Any] = None
    ):
        """Log data access events for compliance."""
        self.logger.info(
            "Data access event",
            event_type="data_access",
            user_id=user_id,
            resource=resource,
            action=action,
            data_classification=data_classification,
            success=success,
            timestamp=time.time(),
            details=details or {}
        )
    
    async def log_compliance_event(
        self,
        event_type: str,
        compliance_level: str,
        data_fields: list,
        action_taken: str,
        details: Dict[str, Any] = None
    ):
        """Log compliance-related events."""
        self.logger.info(
            "Compliance event",
            event_type=event_type,
            compliance_level=compliance_level,
            data_fields=data_fields,
            action_taken=action_taken,
            timestamp=time.time(),
            details=details or {}
        )
    
    async def log_ai_usage(
        self,
        user_id: str,
        model: str,
        prompt_type: str,
        tokens_used: int,
        cost_estimate: float = None,
        success: bool = True,
        details: Dict[str, Any] = None
    ):
        """Log AI service usage for tracking and billing."""
        self.logger.info(
            "AI usage event",
            event_type="ai_usage",
            user_id=user_id,
            model=model,
            prompt_type=prompt_type,
            tokens_used=tokens_used,
            cost_estimate=cost_estimate,
            success=success,
            timestamp=time.time(),
            details=details or {}
        )


# Global audit logger instance
audit_logger = AuditLogger()
