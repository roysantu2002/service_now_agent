"""
Incident processing orchestration service with robust AI analysis,
structured prompts, fallback defaults, and PDF generation.
"""

import os
import json
import uuid
import tempfile
import traceback
from datetime import datetime
from typing import Any, Dict, List, Optional

import structlog
from fastapi.encoders import jsonable_encoder
from pydantic import ValidationError
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, ListFlowable, ListItem
from reportlab.lib.styles import getSampleStyleSheet

from app.models.incident import IncidentProcessRequest, IncidentSummary, IncidentAnalysisModel
from app.abstracts.compliance import ComplianceLevel
from app.exceptions.servicenow import ServiceNowNotFoundError
from app.services.generic_ai_connector import AIConnectorFactory

logger = structlog.get_logger(__name__)

# ----------------------------
# Category mapping
# ----------------------------
ISSUE_CATEGORIES = {
    "network": "Network Issue",
    "hardware": "Hardware Failure",
    "software": "Software Bug",
    "security": "Security Incident",
    "database": "Database Issue",
    "performance": "Performance Degradation",
    "configuration": "Configuration Error",
    "other": "Other"
}


# ----------------------------
# Incident Processing Service
# ----------------------------
class IncidentProcessor:
    """Orchestration service for ServiceNow incident processing."""

    def __init__(self, provider_name: Optional[str] = None):
        from app.services.servicenow import ServiceNowConnector
        from app.services.agentic_service import AgenticAIService
        from app.services.compliance import ComplianceFilter

        self.servicenow = ServiceNowConnector()
        self.ai_service = AIConnectorFactory.get_connector(provider_name)
        self.agentic_service = AgenticAIService()
        self.compliance_filter = ComplianceFilter()
        self._initialized = False

    # ----------------------------
    # Ensure connectors initialized
    # ----------------------------
    async def _ensure_initialized(self) -> None:
        if not self._initialized:
            await self.servicenow.initialize()
            await self.ai_service.initialize()
            await self.agentic_service.initialize()
            await self.compliance_filter.initialize()
            self._initialized = True
            logger.info("Incident processor initialized")

    # ----------------------------
    # Build AI prompt for structured JSON
    # ----------------------------
    def _build_ai_prompt(self, incident_data: Dict[str, Any], analysis_type: str) -> str:
        incident_json = json.dumps(incident_data, indent=2, default=str)
        categories_json = json.dumps(ISSUE_CATEGORIES, indent=2)
        prompt = f"""
            You are an expert IT service analyst. Analyze the following ServiceNow incident data
            and return a structured JSON object exactly matching this model:

            {{
            "id": "auto-generated UUID",
            "issue": "Short title describing the problem",
            "issue_category": "One of the predefined categories based on the problem: {list(ISSUE_CATEGORIES.values())}",
            "description": "Detailed explanation of the incident and its context",
            "steps_to_resolve": [
                "Step 1 - actionable instruction",
                "... up to at least 10 steps"
            ],
            "technical_details": "Technical breakdown including affected systems, logs, errors, configurations",
            "complete_description": "Comprehensive summary combining issue, technical details, and recommended actions"
            }}

            Incident Data:
            {incident_json}

            Available Categories:
            {categories_json}

            Rules:
            1. Respond ONLY in valid JSON (no markdown, no explanations).
            2. Ensure at least 10 steps in steps_to_resolve.
            3. Fill all fields meaningfully; do not leave any field empty.
            4. Use available incident fields (number, short_description, cmdb_ci, assignment_group, opened_at, updated_at) where applicable.
            """
        return prompt

    # ----------------------------
    # Extract JSON safely from AI output
    # ----------------------------
    def _extract_json_from_ai(self, raw: str) -> str:
        if not raw:
            raise ValueError("AI returned no content")
        content = raw.strip().replace("```json", "").replace("```", "").strip()
        start, end = content.find("{"), content.rfind("}")
        if start == -1 or end == -1 or end < start:
            logger.error("No valid JSON found in AI output", raw_output=content[:1000])
            raise ValueError("AI output did not contain a valid JSON object")
        return content[start:end + 1]

    # ----------------------------
    # Ensure at least 10 resolution steps
    # ----------------------------
    def _ensure_ten_steps(self, steps: Optional[List[str]]) -> List[str]:
        default_steps = [
            "Verify the incident details in ServiceNow and confirm affected services.",
            "Check relevant server/network logs for errors or timeouts.",
            "Gather recent configuration changes or deployment history.",
            "Reproduce the issue in a controlled environment if possible.",
            "Check hardware health and connectivity (NIC, switches, interfaces).",
            "Run diagnostic commands (ping, traceroute, netstat, tcpdump) as applicable.",
            "Validate firewall/ACL and routing policies for impacted flows.",
            "Apply a temporary mitigation (reroute, restart service) if safe.",
            "Update stakeholders and create an action plan.",
            "Perform root cause analysis and schedule preventive measures."
        ]
        if not steps or not isinstance(steps, list):
            steps = []
        for step in default_steps:
            if len(steps) >= 10:
                break
            if step not in steps:
                steps.append(step)
        return steps[:10]

    # ----------------------------
    # Generate PDF
    # ----------------------------
    async def _generate_incident_pdf(self, analysis: IncidentAnalysisModel) -> str:
        try:
            output_dir = os.path.join(os.getcwd(), "output")
            os.makedirs(output_dir, exist_ok=True)
            file_path = os.path.join(output_dir, f"{analysis.id}.pdf")

            doc = SimpleDocTemplate(file_path, pagesize=A4)
            styles = getSampleStyleSheet()
            elements = [
                Paragraph(f"<b>Issue:</b> {analysis.issue}", styles["Heading2"]),
                Paragraph(analysis.description or "", styles["Normal"]),
                Spacer(1, 12),
                Paragraph("<b>Steps to Resolve:</b>", styles["Heading3"]),
                ListFlowable([ListItem(Paragraph(str(s), styles["Normal"])) for s in analysis.steps_to_resolve], bulletType="1"),
                Spacer(1, 12),
                Paragraph("<b>Technical Details:</b>", styles["Heading3"]),
                Paragraph(analysis.technical_details or "", styles["Normal"]),
                Spacer(1, 12),
                Paragraph("<b>Complete Description:</b>", styles["Heading3"]),
                Paragraph(analysis.complete_description or "", styles["Normal"])
            ]
            doc.build(elements)
            logger.info("PDF generated successfully", file_path=file_path)
            return file_path
        except Exception as e:
            logger.error("Failed to generate PDF", error=str(e), analysis_id=analysis.id)
            raise

    # ----------------------------
    # Analyze a single incident
    # ----------------------------
    async def analyze_incident_only(self, sys_id: str, analysis_type: str = "general") -> Dict[str, Any]:
        await self._ensure_initialized()
        logger.info("Analyzing incident", sys_id=sys_id, analysis_type=analysis_type)

        raw_output_path = None
        parsing_error = validation_error = None
        validated_struct: Optional[IncidentAnalysisModel] = None

        try:
            # Fetch incident & filter
            incident = await self.servicenow.get_incident(sys_id)
            incident_dict = incident.model_dump()
            compliance_result = await self.compliance_filter.filter_data(incident_dict, ComplianceLevel.INTERNAL)

            # Build prompt & call AI
            prompt = self._build_ai_prompt(compliance_result.filtered_data, analysis_type)
            ai_analysis = await self.ai_service.generate_text(
                {
                    "prompt": prompt,
                    "context": {"analysis_type": analysis_type},
                    "max_tokens": 1200,
                    "temperature": 0.3
                }
            )

            raw_content = (ai_analysis.content or "").strip()
            print("⚡ AI Raw Output:\n", raw_content[:2000])

            # Save AI raw output
            try:
                tmpdir = tempfile.gettempdir()
                raw_output_path = os.path.join(tmpdir, f"ai_raw_{sys_id}_{int(datetime.utcnow().timestamp())}.txt")
                with open(raw_output_path, "w", encoding="utf-8") as f:
                    f.write(raw_content)
            except Exception as e:
                logger.warning("Failed to write AI raw output", error=str(e))

            # Parse JSON safely
            parsed_json: Dict[str, Any] = {}
            try:
                json_str = self._extract_json_from_ai(raw_content)
                parsed_json = json.loads(json_str)
            except Exception as e:
                parsing_error = f"{str(e)}\n{traceback.format_exc()}"
                logger.error("AI JSON extraction/parsing failed", error=parsing_error, sys_id=sys_id)

            # Validate or fallback to defaults
            validated_struct = IncidentAnalysisModel(
                id=str(parsed_json.get("id") or uuid.uuid4().hex),
                issue=str(parsed_json.get("issue") or getattr(incident, "short_description", f"Incident {sys_id}")),
                issue_category=str(parsed_json.get("issue_category") or "Other"),
                description=str(parsed_json.get("description") or getattr(incident, "description", "No description available")),
                steps_to_resolve=self._ensure_ten_steps(parsed_json.get("steps_to_resolve")),
                technical_details=str(parsed_json.get("technical_details") or f"Affected CI: {getattr(incident, 'cmdb_ci', 'unknown')} | Assigned group: {getattr(incident, 'assignment_group', 'unknown')}"),
                complete_description=str(parsed_json.get("complete_description") or getattr(incident, "description", "No description available") + "\n\nThis summary was generated by AI; it may require human review.")
            )

            # Generate PDF
            pdf_path = await self._generate_incident_pdf(validated_struct)

            return jsonable_encoder({
                "success": parsing_error is None and validation_error is None,
                "sys_id": sys_id,
                "analysis_type": analysis_type,
                "ai_model": getattr(ai_analysis, "model", None),
                "usage": getattr(ai_analysis, "usage", None),
                "data": validated_struct,
                "pdf_path": pdf_path,
                "raw_ai_output_path": raw_output_path,
                "parsing_error": parsing_error,
                "validation_error": validation_error
            })

        except ServiceNowNotFoundError:
            logger.error("Incident not found", sys_id=sys_id)
            raise
        except Exception as e:
            logger.error("Unexpected error during analyze_incident_only", sys_id=sys_id, error=str(e), traceback=traceback.format_exc())
            raise

    # ----------------------------
    # Cleanup
    # ----------------------------
    async def cleanup(self) -> None:
        if self._initialized:
            await self.servicenow.disconnect()
            await self.ai_service.disconnect()
            await self.agentic_service.disconnect()
            await self.compliance_filter.disconnect()
            logger.info("Incident processor cleanup completed")
