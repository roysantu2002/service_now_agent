"""Logging configuration."""
import sys
import logging
import structlog
from typing import Any, Dict

from app.core.config import get_settings


def setup_logging() -> None:
    """Configure structured logging."""
    settings = get_settings()
    
    log_level_mapping = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }
    
    log_level = log_level_mapping.get(settings.LOG_LEVEL.upper(), logging.INFO)
    
    # Configure standard logging
    logging.basicConfig(
        level=log_level,
        format="%(message)s",
        stream=sys.stdout,
    )
    
    # Configure structlog
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer() if settings.LOG_FORMAT == "console" 
            else structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        logger_factory=structlog.WriteLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.BoundLogger:
    """Get a structured logger instance."""
    return structlog.get_logger(name)


def configure_uvicorn_logging() -> Dict[str, Any]:
    """Configure uvicorn logging to work with structlog."""
    settings = get_settings()
    
    log_level_mapping = {
        "DEBUG": "debug",
        "INFO": "info", 
        "WARNING": "warning",
        "ERROR": "error",
        "CRITICAL": "critical",
    }
    
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            },
        },
        "handlers": {
            "default": {
                "formatter": "default",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
            },
        },
        "root": {
            "level": settings.LOG_LEVEL.upper(),
            "handlers": ["default"],
        },
        "loggers": {
            "uvicorn": {
                "level": log_level_mapping.get(settings.LOG_LEVEL.upper(), "info"),
                "handlers": ["default"],
                "propagate": False,
            },
            "uvicorn.error": {
                "level": log_level_mapping.get(settings.LOG_LEVEL.upper(), "info"),
                "handlers": ["default"],
                "propagate": False,
            },
            "uvicorn.access": {
                "level": log_level_mapping.get(settings.LOG_LEVEL.upper(), "info"),
                "handlers": ["default"],
                "propagate": False,
            },
        },
    }
