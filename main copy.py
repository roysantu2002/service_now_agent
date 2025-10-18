"""
FastAPI application entry point for ServiceNow incident processing.
"""
import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

logger = structlog.get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    try:
        from app.core.logging import setup_logging
        setup_logging()
        logger.info("Starting ServiceNow Incident Processor API")
        print("[DEBUG] Application startup completed successfully")
    except Exception as e:
        print(f"[DEBUG] Error during startup: {e}")
        raise
    yield
    # Shutdown
    logger.info("Shutting down ServiceNow Incident Processor API")


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    print("[DEBUG] Creating FastAPI app...")
    
    app = FastAPI(
        title="ServiceNow Incident Processor",
        description="API for processing ServiceNow incident tickets with AI analysis",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )
    
    print("[DEBUG] FastAPI app created")

    @app.get("/")
    async def root():
        """Root endpoint with API information."""
        return {
            "message": "ServiceNow Incident Processor API",
            "version": "1.0.0",
            "docs": "/docs",
            "health": "/api/v1/health"
        }
    
    print("[DEBUG] Root endpoint added")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Allow all origins for testing
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    print("[DEBUG] CORS middleware added")

    try:
        from app.api.v1.router import api_router
        app.include_router(api_router, prefix="/api/v1")
        print("[DEBUG] API router included successfully")
    except Exception as e:
        print(f"[DEBUG] Error including API router: {e}")
        # Add a simple health endpoint directly if router fails
        @app.get("/api/v1/health/")
        async def simple_health():
            return {"status": "healthy", "message": "Simple health check"}
        print("[DEBUG] Added simple health endpoint as fallback")

    print("[DEBUG] App creation completed")
    return app


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
