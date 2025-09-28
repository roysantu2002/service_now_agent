"""Main API router for v1 endpoints."""

from fastapi import APIRouter
import structlog

logger = structlog.get_logger(__name__)
api_router = APIRouter()

# --- Import routers safely ---
routers = []

try:
    from app.api.v1.endpoints import health
    routers.append(("health", health.router))
    logger.debug("Health endpoint imported successfully")
except Exception as e:
    logger.error("Error importing health endpoint", error=str(e))

try:
    from app.api.v1.endpoints import incidents
    routers.append(("incidents", incidents.router))
    logger.debug("Incidents endpoint imported successfully")
except Exception as e:
    logger.error("Error importing incidents endpoint", error=str(e))

# --- Include routers ---
for prefix, router in routers:
    api_router.include_router(router, prefix=f"/{prefix}", tags=[prefix])
    logger.debug("Included router", prefix=prefix, route_count=len(router.routes))

logger.debug("Final API router setup complete", total_routes=len(api_router.routes))

# Optional: Print all routes for quick debug
for route in api_router.routes:
    methods = getattr(route, "methods", "N/A")
    logger.debug("API Route loaded", path=route.path, methods=methods)
