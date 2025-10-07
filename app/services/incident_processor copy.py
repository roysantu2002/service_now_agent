"""Incident processing orchestration service with lazy imports to avoid circular dependencies."""

import structlog
from typing import Dict, Any, List
from datetime import datetime

from app.models.incident import IncidentProcessRequest, IncidentSummary
from app.abstracts.compliance import ComplianceLevel
from app.exceptions.servicenow import ServiceNowNotFoundError

logger = structlog.get_logger(__name__)


class IncidentProcessor:
    """Orchestration service for ServiceNow incident processing."""

    def __init__(self):
        # Lazy imports to avoid circular dependency
        from app.services.servicenow import ServiceNowConnector
        from app.services.openai_connector import OpenAIConnector
        from app.services.agentic_service import AgenticAIService
        from app.services.compliance import ComplianceFilter

        self.servicenow = ServiceNowConnector()
        self.openai_service = OpenAIConnector()
        self.agentic_service = AgenticAIService()
        self.compliance_filter = ComplianceFilter()
        self._initialized = False

    async def _ensure_initialized(self) -> None:
        if not self._initialized:
            await self.servicenow.initialize()
            await self.openai_service.initialize()
            await self.agentic_service.initialize()
            await self.compliance_filter.initialize()
            self._initialized = True
            logger.info("Incident processor initialized")

    async def process_incident(self, request: IncidentProcessRequest) -> Dict[str, Any]:
        await self._ensure_initialized()
        start_time = datetime.utcnow()
        logger.info("Starting incident processing", sys_id=request.sys_id)

        try:
            # Step 1: Fetch incident
            incident = await self.servicenow.get_incident(request.sys_id)
            incident_dict = incident.model_dump()

            # Step 2: Apply compliance
            compliance_result = await self.compliance_filter.filter_data(
                incident_dict, ComplianceLevel(request.compliance_level)
            )

            # Step 3: AI analysis
            ai_analysis = await self.openai_service.analyze_incident(
                compliance_result.filtered_data, request.analysis_type
            )

            # Step 4: Agentic insights
            agentic_insights = None
            if request.analysis_type in ["priority_assessment", "classification", "recommendations"]:
                if request.analysis_type == "priority_assessment":
                    agentic_result = await self.agentic_service.analyze_incident_priority(compliance_result.filtered_data)
                elif request.analysis_type == "classification":
                    agentic_result = await self.agentic_service.classify_incident_type(compliance_result.filtered_data)
                elif request.analysis_type == "recommendations":
                    agentic_result = await self.agentic_service.recommend_actions(compliance_result.filtered_data)
                agentic_insights = agentic_result.result

            # Step 5: Incident history
            history = await self.servicenow.get_incident_history(request.sys_id) if request.include_history else None

            processing_time = (datetime.utcnow() - start_time).total_seconds()

            return {
                "incident": incident,
                "ai_analysis": {
                    "content": ai_analysis.content,
                    "model": ai_analysis.model,
                    "analysis_type": request.analysis_type,
                    "usage": ai_analysis.usage
                },
                "agentic_insights": agentic_insights,
                "compliance_info": {
                    "compliance_level": request.compliance_level,
                    "compliance_score": compliance_result.compliance_score,
                    "removed_fields": compliance_result.removed_fields,
                    "masked_fields": compliance_result.masked_fields,
                    "classifications": [c.model_dump() for c in compliance_result.classifications]
                },
                "history": history,
                "processing_metadata": {
                    "processing_time": processing_time,
                    "timestamp": datetime.utcnow().isoformat(),
                    "services_used": ["servicenow", "openai", "compliance"]
                }
            }

        except Exception as e:
            logger.error("Error processing incident", sys_id=request.sys_id, error=str(e))
            raise

    async def get_incident_summary(self, sys_id: str) -> IncidentSummary:
        await self._ensure_initialized()
        try:
            incident = await self.servicenow.get_incident(sys_id)

            # Prepare a truncated summary from description and work notes
            summary_parts = []
            if incident.description:
                summary_parts.append(incident.description)
            if incident.work_notes:
                summary_parts.append(incident.work_notes)
            summary_text = " | ".join(summary_parts)
            if len(summary_text) > 200:
                summary_text = summary_text[:200] + "..."

            return IncidentSummary(
                sys_id=incident.sys_id,
                number=incident.number,
                title=incident.short_description,
                status=incident.state,
                priority=incident.priority,
                urgency=incident.urgency,
                impact=incident.impact,
                category=incident.category,
                subcategory=incident.subcategory,
                assigned_to=incident.assigned_to,
                assignment_group=incident.assignment_group,
                caller_id=incident.caller_id,
                created=incident.opened_at,
                updated=incident.updated_at,
                resolved_at=incident.resolved_at,
                short_description=incident.short_description,
                description=incident.description,
                work_notes=incident.work_notes,
                summary=summary_text,
                additional_fields=incident.additional_fields
            )
        except Exception as e:
            logger.error("Error getting incident summary", sys_id=sys_id, error=str(e))
            raise

    async def analyze_incident_only(self, sys_id: str, analysis_type: str = "general") -> Dict[str, Any]:
        await self._ensure_initialized()
        incident = await self.servicenow.get_incident(sys_id)
        incident_dict = incident.model_dump()
        compliance_result = await self.compliance_filter.filter_data(incident_dict, ComplianceLevel.INTERNAL)
        ai_analysis = await self.openai_service.analyze_incident(compliance_result.filtered_data, analysis_type)
        return {
            "content": ai_analysis.content,
            "model": ai_analysis.model,
            "analysis_type": analysis_type,
            "usage": ai_analysis.usage
        }

    async def filter_incident_data_only(self, sys_id: str, compliance_level: str = "internal") -> Dict[str, Any]:
        await self._ensure_initialized()
        incident = await self.servicenow.get_incident(sys_id)
        incident_dict = incident.model_dump()
        compliance_result = await self.compliance_filter.filter_data(incident_dict, ComplianceLevel(compliance_level))
        return {
            "filtered_data": compliance_result.filtered_data,
            "compliance_score": compliance_result.compliance_score,
            "removed_fields": compliance_result.removed_fields,
            "masked_fields": compliance_result.masked_fields,
            "classifications": [c.model_dump() for c in compliance_result.classifications]
        }

    async def get_incident_history(self, sys_id: str) -> List[Dict[str, Any]]:
        await self._ensure_initialized()
        return await self.servicenow.get_incident_history(sys_id)

    async def cleanup(self) -> None:
        if self._initialized:
            await self.servicenow.disconnect()
            await self.openai_service.disconnect()
            await self.agentic_service.disconnect()
            logger.info("Incident processor cleanup completed")
