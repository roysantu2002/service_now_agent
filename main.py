"""
FastAPI application entry point for ServiceNow incident processing + Agentic RAGChat.
"""

import structlog
import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

# Import app dependencies
logger = structlog.get_logger(__name__)

# -----------------------------------------------------
# ✅ Application Lifespan: startup & shutdown management
# -----------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown."""
    try:
        # Logging setup
        from app.core.logging import setup_logging
        from app.utils.db_utils import initialize_database, close_database, test_connection
        # from app.graph_utils import initialize_graph, close_graph, test_graph_connection

        setup_logging()
        logger.info("Starting ServiceNow Incident Processor + RAGChat API")

        # Initialize database connections
        await initialize_database()
        # await initialize_graph()

        db_ok = await test_connection()
        # graph_ok = await test_graph_connection()
        logger.info(f"Database health: {db_ok}")

        print("[DEBUG] Startup completed successfully")

    except Exception as e:
        logger.error("Startup failed", error=str(e))
        print(f"[DEBUG] Error during startup: {e}")
        raise

    yield

    # Graceful shutdown
    try:
        await close_database()
        await close_graph()
        logger.info("Closed database and graph connections")
    except Exception as e:
        logger.error("Error during shutdown", error=str(e))
        print(f"[DEBUG] Error during shutdown: {e}")

    logger.info("Shutting down ServiceNow Incident Processor API")


# -----------------------------------------------------
# ✅ Application Factory
# -----------------------------------------------------
def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    print("[DEBUG] Creating FastAPI app...")

    app = FastAPI(
        title="ServiceNow Incident Processor + Agentic RAGChat",
        description="Processes ServiceNow incidents with AI and supports RAG-based conversational analysis",
        version="2.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    print("[DEBUG] FastAPI app created")

    # --------------------------
    # Root Info Endpoint
    # --------------------------
    @app.get("/")
    async def root():
        """Root endpoint with API information."""
        return {
            "message": "ServiceNow Incident Processor + Agentic RAGChat API",
            "version": "2.0.0",
            "docs": "/docs",
            "health": "/api/v1/health",
            "ragchat": "/api/v1/ragchat",
        }

    print("[DEBUG] Root endpoint added")

    # --------------------------
    # CORS Middleware
    # --------------------------
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # TODO: tighten for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    print("[DEBUG] CORS middleware added")

    # --------------------------
    # Include Routers
    # --------------------------
    try:
        # Core incident processor routes
        from app.api.v1.router import api_router
        app.include_router(api_router, prefix="/api/v1")
        print("[DEBUG] Incident API router included successfully")

        # Add RAGChat endpoints (from agentic RAG system)
        from app.api.v1.endpoints import ragchat
        app.include_router(ragchat.router, prefix="/api/v1/ragchat", tags=["RAGChat"])
        print("[DEBUG] RAGChat router included successfully")

    except Exception as e:
        print(f"[DEBUG] Error including routers: {e}")
        logger.error("Error including routers", error=str(e))

        # Fallback health check
        @app.get("/api/v1/health/")
        async def simple_health():
            return {"status": "healthy", "message": "Simple health check"}
        print("[DEBUG] Added simple health endpoint as fallback")

    # --------------------------
    # Global Exception Handler
    # --------------------------
    from app.models.rag import ErrorResponse

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """Catch unhandled exceptions and return structured error response."""
        error_id = str(uuid.uuid4())
        logger.error("Unhandled exception", error=str(exc), request_id=error_id)
        return ErrorResponse(
            error=str(exc),
            error_type=type(exc).__name__,
            request_id=error_id,
        )

    print("[DEBUG] Global exception handler registered")
    print("[DEBUG] App creation completed")

    return app


# -----------------------------------------------------
# ✅ Application Entry Point
# -----------------------------------------------------
print("[DEBUG] Starting app creation...")
app = create_app()
print("[DEBUG] App instance created")

if __name__ == "__main__":
    import uvicorn
    print("[DEBUG] Starting uvicorn server...")
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_config=None,
    )
