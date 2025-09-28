"""ServiceNow-related exceptions."""


class ServiceNowError(Exception):
    """Base ServiceNow exception."""
    pass


class ServiceNowConnectionError(ServiceNowError):
    """ServiceNow connection error."""
    pass


class ServiceNowAuthenticationError(ServiceNowError):
    """ServiceNow authentication error."""
    pass


class ServiceNowNotFoundError(ServiceNowError):
    """ServiceNow resource not found error."""
    pass


class ServiceNowAPIError(ServiceNowError):
    """ServiceNow API error."""
    
    def __init__(self, message: str, status_code: int = None, response_data: dict = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data
