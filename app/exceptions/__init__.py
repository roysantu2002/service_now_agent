"""Custom exceptions for the application."""

from .servicenow import (
    ServiceNowError,
    ServiceNowConnectionError,
    ServiceNowAuthenticationError,
    ServiceNowNotFoundError,
    ServiceNowAPIError
)

__all__ = [
    "ServiceNowError",
    "ServiceNowConnectionError", 
    "ServiceNowAuthenticationError",
    "ServiceNowNotFoundError",
    "ServiceNowAPIError"
]
