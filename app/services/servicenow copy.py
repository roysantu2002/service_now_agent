import httpx
import structlog
from typing import Optional
from app.services.servicenow_base import BaseServiceNowConnector, ServiceNowError, ServiceNowNotFoundError
from app.core.config import get_settings

logger = structlog.get_logger(__name__)


class ServiceNowConnector(BaseServiceNowConnector):
    """Full ServiceNow connector implementation."""

    def __init__(self):
        super().__init__()
        self.settings = get_settings()
        self.base_url = self.settings.SERVICE_NOW_REST_API_URL.rstrip('/')
        self.username = self.settings.SERVICE_NOW_USER
        self.password = self.settings.SERVICE_NOW_PASSWORD
        self.client: Optional[httpx.AsyncClient] = None

    async def initialize(self):
        if not self.client:
            self.client = httpx.AsyncClient(
                auth=(self.username, self.password),
                timeout=10,
                headers={"Accept": "application/json", "Content-Type": "application/json"}
            )
            logger.info("ServiceNowConnector initialized")

    async def disconnect(self):
        if self.client:
            await self.client.aclose()
            self.client = None
            logger.info("ServiceNowConnector disconnected")

    async def health_check(self) -> bool:
        await self.initialize()
        try:
            resp = await self.client.get(f"{self.base_url}/api/now/table/sys_user")
            return resp.status_code == 200
        except Exception as e:
            logger.error("ServiceNow health check failed", error=str(e))
            return False
