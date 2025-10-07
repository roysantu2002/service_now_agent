"""Health check endpoints for ServiceNow Incident Processor."""
from fastapi import APIRouter
from typing import Dict, Any
import structlog
from datetime import datetime
from datetime import datetime, timezone

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.get("/", summary="Basic health check")
async def health_check() -> Dict[str, Any]:
    """
    Simple endpoint to check if the API service is running.
    """
    return {
        "status": "healthy",
        "service": "ServiceNow Incident Processor",
        "version": "1.0.0"
    }


@router.get("/detailed", summary="Detailed health check for all services")
async def detailed_health_check() -> Dict[str, Any]:
    """
    Performs a detailed health check for all integrated services.
    Currently supports:
        - ServiceNow API connectivity
    """
    logger.info("Starting detailed health check")
    
    # Local import to avoid circular imports
    from app.services.servicenow import ServiceNowConnector

    servicenow = ServiceNowConnector()
    
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "services": {}
    }
    
    # Check ServiceNow connectivity
    try:
        is_healthy = await servicenow.health_check()
        health_status["services"]["servicenow"] = {
            "status": "healthy" if is_healthy else "unhealthy",
            "details": "ServiceNow API connection"
        }
    except Exception as e:
        logger.error("ServiceNow health check failed", error=str(e))
        health_status["services"]["servicenow"] = {
            "status": "unhealthy",
            "details": f"Error: {str(e)}"
        }
    
    # Determine overall status
    all_services_healthy = all(
        svc["status"] == "healthy" for svc in health_status["services"].values()
    )
    health_status["status"] = "healthy" if all_services_healthy else "degraded"
    
    # Cleanup
    await servicenow.disconnect()
    
    logger.info(
        "Detailed health check completed",
        overall_status=health_status["status"],
        service_status=health_status["services"]
    )
    
    return health_status
