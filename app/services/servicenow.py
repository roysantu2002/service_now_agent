"""ServiceNow connector implementation fully compliant with BaseServiceNowConnector."""
import httpx
import structlog
from typing import Dict, Any, List, Optional
from datetime import datetime

from app.abstracts.servicenow_connector import (
    BaseServiceNowConnector,
    IncidentData,
    ServiceNowQuery,
    ServiceNowResponse
)
from app.core.config import get_settings
from app.exceptions.servicenow import ServiceNowError, ServiceNowNotFoundError

logger = structlog.get_logger(__name__)


class ServiceNowConnector(BaseServiceNowConnector):
    """ServiceNow REST API connector implementation."""

    def __init__(self):
        super().__init__()
        self.settings = get_settings()
        self.base_url = self.settings.SERVICE_NOW_REST_API_URL.rstrip('/')
        self.username = self.settings.SERVICE_NOW_USER
        self.password = self.settings.SERVICE_NOW_PASSWORD
        self.timeout = self.settings.SERVICENOW_TIMEOUT
        self.client: Optional[httpx.AsyncClient] = None

    # -------------------------------
    # Connection Methods
    # -------------------------------
    async def initialize(self) -> None:
        """Initialize ServiceNow AsyncClient."""
        if self.client is None:
            self.client = httpx.AsyncClient(
                auth=(self.username, self.password),
                timeout=self.timeout,
                headers={'Accept': 'application/json', 'Content-Type': 'application/json'}
            )
            logger.info("ServiceNow connector initialized", base_url=self.base_url)

    async def connect(self) -> bool:
        """Establish connection to ServiceNow by testing credentials."""
        try:
            await self.initialize()
            return await self.health_check()
        except Exception as e:
            logger.error("Failed to connect to ServiceNow", error=str(e))
            return False

    async def disconnect(self) -> None:
        """Close ServiceNow client connection."""
        if self.client:
            await self.client.aclose()
            self.client = None
            logger.info("ServiceNow connection closed")

    async def health_check(self) -> bool:
        """Health check for ServiceNow."""
        try:
            if not self.client:
                await self.initialize()
            response = await self.client.get(f"{self.base_url}/api/now/table/incident", params={'sysparm_limit': 1})
            return response.status_code == 200
        except Exception as e:
            logger.error("ServiceNow health check failed", error=str(e))
            return False

    # -------------------------------
    # Credential Validation
    # -------------------------------
    def validate_credentials(self) -> bool:
        """Check that base URL, username, and password are set."""
        return bool(self.base_url and self.username and self.password)

    # -------------------------------
    # Incident Methods
    # -------------------------------
    async def get_incident(self, sys_id: str) -> IncidentData:
        """Fetch a single incident by sys_id."""
        if not self.client:
            await self.initialize()
        try:
            url = f"{self.base_url}/api/now/table/incident/{sys_id}"
            response = await self.client.get(url)
            
            if response.status_code == 404:
                raise ServiceNowNotFoundError(f"Incident {sys_id} not found")
            if response.status_code in (401, 403):
                raise ServiceNowError(f"Access error: {response.status_code}")
            
            data = response.json()
            # print(data['result'])
            if 'result' not in data:
                raise ServiceNowError("Invalid response: missing 'result'")
            
            return self._parse_incident_data(data['result'])
        except Exception as e:
            logger.error("Error fetching incident", sys_id=sys_id, error=str(e))
            raise ServiceNowError(str(e))

    async def query_incidents(self, query: ServiceNowQuery) -> List[IncidentData]:
        """Query incidents with optional filters."""
        if not self.client:
            await self.initialize()
        try:
            url = f"{self.base_url}/api/now/table/{query.table}"
            params = {}
            if query.query:
                params['sysparm_query'] = query.query
            if query.fields:
                params['sysparm_fields'] = ','.join(query.fields)
            if query.limit:
                params['sysparm_limit'] = query.limit
            if query.offset:
                params['sysparm_offset'] = query.offset
            
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            
            incidents = []
            for item in response.json().get('result', []):
                incidents.append(self._parse_incident_data(item))
            return incidents
        except Exception as e:
            logger.error("Error querying incidents", error=str(e))
            raise ServiceNowError(str(e))

    async def update_incident(self, sys_id: str, updates: Dict[str, Any]) -> ServiceNowResponse:
        """Update incident fields."""
        if not self.client:
            await self.initialize()
        try:
            url = f"{self.base_url}/api/now/table/incident/{sys_id}"
            start_time = datetime.utcnow()
            response = await self.client.patch(url, json=updates)
            elapsed = (datetime.utcnow() - start_time).total_seconds()
            success = response.status_code == 200
            return ServiceNowResponse(
                success=success,
                data=response.json() if success else None,
                error=response.text if not success else None,
                status_code=response.status_code,
                response_time=elapsed
            )
        except Exception as e:
            logger.error("Error updating incident", sys_id=sys_id, error=str(e))
            return ServiceNowResponse(success=False, error=str(e), status_code=500, response_time=0.0)

    async def add_work_note(self, sys_id: str, note: str) -> ServiceNowResponse:
        """Add a work note to an incident."""
        return await self.update_incident(sys_id, {'work_notes': note})

    async def get_incident_history(self, sys_id: str) -> List[Dict[str, Any]]:
        """Fetch audit history for an incident."""
        if not self.client:
            await self.initialize()
        try:
            url = f"{self.base_url}/api/now/table/sys_audit"
            params = {
                'sysparm_query': f'tablename=incident^documentkey={sys_id}',
                'sysparm_order_by': 'sys_created_on'
            }
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            return response.json().get('result', [])
        except Exception as e:
            logger.error("Error fetching incident history", sys_id=sys_id, error=str(e))
            raise ServiceNowError(str(e))

    # -------------------------------
    # Helper Methods
    # -------------------------------
    # def _parse_incident_data(self, raw_data: Dict[str, Any]) -> IncidentData:
    #     """Convert raw incident dict to IncidentData model."""
    #     try:
    #         opened_at = self._parse_datetime(raw_data.get('opened_at'))
    #         updated_at = self._parse_datetime(raw_data.get('sys_updated_on'))
    #         resolved_at = self._parse_datetime(raw_data.get('resolved_at')) if raw_data.get('resolved_at') else None
            
        #     return IncidentData(
        #         sys_id=raw_data.get('sys_id', ''),
        #         number=raw_data.get('number', ''),
        #         short_description=raw_data.get('short_description', ''),
        #         description=raw_data.get('description'),
        #         state=raw_data.get('state', ''),
        #         priority=raw_data.get('priority', ''),
        #         urgency=raw_data.get('urgency', ''),
        #         impact=raw_data.get('impact', ''),
        #         category=raw_data.get('category'),
        #         subcategory=raw_data.get('subcategory'),
        #         assigned_to=(raw_data.get('assigned_to') or {}).get('display_value') if isinstance(raw_data.get('assigned_to'), dict) else raw_data.get('assigned_to'),
        #         assignment_group=(raw_data.get('assignment_group') or {}).get('display_value') if isinstance(raw_data.get('assignment_group'), dict) else raw_data.get('assignment_group'),
        #         caller_id=(raw_data.get('caller_id') or {}).get('display_value') if isinstance(raw_data.get('caller_id'), dict) else raw_data.get('caller_id'),
        #         opened_at=opened_at,
        #         updated_at=updated_at,
        #         resolved_at=resolved_at,
        #         notes=raw_data.get('comments'),
        #         work_notes=raw_data.get('work_notes'),
        #         additional_fields={k: v for k, v in raw_data.items() if k not in self._get_core_fields()}
        #     )
        # except Exception as e:
        #     logger.error("Error parsing incident data", error=str(e), raw_data=raw_data)
        #     raise ServiceNowError(f"Failed to parse incident data: {str(e)}")

    def _parse_incident_data(self, raw_data: Dict[str, Any]) -> IncidentData:
        """Convert raw incident dict to IncidentData model."""
        try:
            # Parse dates
            opened_at = self._parse_datetime(raw_data.get('opened_at'))
            updated_at = self._parse_datetime(raw_data.get('sys_updated_on'))
            resolved_at = self._parse_datetime(raw_data.get('resolved_at')) if raw_data.get('resolved_at') else None

            # Helper to extract 'value' from nested dicts
            def get_value(field):
                if isinstance(field, dict):
                    return field.get('value') or ''
                return field or ''

            return IncidentData(
                sys_id=raw_data.get('sys_id', ''),
                number=raw_data.get('number', ''),
                short_description=raw_data.get('short_description', ''),
                description=raw_data.get('description', ''),
                state=raw_data.get('incident_state', ''),
                priority=raw_data.get('priority', ''),
                urgency=raw_data.get('urgency', ''),
                impact=raw_data.get('impact', ''),
                category=raw_data.get('category', ''),
                subcategory=raw_data.get('subcategory', ''),
                assigned_to=get_value(raw_data.get('assigned_to')),
                assignment_group=get_value(raw_data.get('assignment_group')),
                caller_id=get_value(raw_data.get('caller_id')),
                opened_at=opened_at,
                updated_at=updated_at,
                resolved_at=resolved_at,
                notes=raw_data.get('comments', ''),
                work_notes=raw_data.get('work_notes', ''),
                additional_fields={k: v for k, v in raw_data.items() if k not in self._get_core_fields()}
            )
        except Exception as e:
            logger.error("Error parsing incident data", error=str(e), raw_data=raw_data)
            raise ServiceNowError(f"Failed to parse incident data: {str(e)}")
    
    def _parse_datetime(self, date_str: Optional[str]) -> datetime:
        """Parse ServiceNow datetime string."""
        if not date_str:
            return datetime.utcnow()
        try:
            return datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            try:
                return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            except Exception:
                return datetime.utcnow()

    def _get_core_fields(self) -> set:
        """Return core incident field names."""
        return {
            'sys_id', 'number', 'short_description', 'description', 'state',
            'priority', 'urgency', 'impact', 'category', 'subcategory',
            'assigned_to', 'assignment_group', 'caller_id', 'opened_at',
            'sys_updated_on', 'resolved_at', 'comments', 'work_notes'
        }

    async def create_incident(self, data: Dict[str, Any]) -> Dict[str, Any]:
        if not self.client:
            await self.initialize()
        try:
            url = f"{self.base_url}/api/now/table/incident"
            response = await self.client.post(url, json=data)
            response.raise_for_status()
            return response.json().get("result", {})  # return dict
        except Exception as e:
            logger.error("Error creating incident", error=str(e))
            raise ServiceNowError(str(e))