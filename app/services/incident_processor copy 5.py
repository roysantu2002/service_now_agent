import os
import json
import uuid
import tempfile
import traceback
from datetime import datetime
from typing import Any, Dict, List, Optional

import structlog
from fastapi.encoders import jsonable_encoder
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, ListFlowable, ListItem
from reportlab.lib.styles import getSampleStyleSheet

from app.models.incident import IncidentAnalysisModel
from app.abstracts.compliance import ComplianceLevel
from app.exceptions.servicenow import ServiceNowNotFoundError
from app.services.generic_ai_connector import AIConnectorFactory

logger = structlog.get_logger(__name__)

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

    # -------------------------------------------------------------------
    async def _ensure_initialized(self) -> None:
        if not self._initialized:
            await self.servicenow.initialize()
            await self.ai_service.initialize()
            await self.agentic_service.initialize()
            await self.compliance_filter.initialize()
            self._initialized = True
            logger.info("Incident processor initialized")

    # -------------------------------------------------------------------
    def _build_ai_prompt(self, incident_data: Dict[str, Any], analysis_type: str) -> str:
        incident_json = json.dumps(incident_data, indent=2, default=str)
        categories_json = json.dumps(ISSUE_CATEGORIES, indent=2)
        return f"""
You are an expert IT service analyst. Analyze the following ServiceNow incident data
and return a structured JSON object exactly matching this model:

{{
"id": "auto-generated UUID",
"issue": "Short title describing the problem",
"issue_category": "One of: {list(ISSUE_CATEGORIES.values())}",
"description": "Detailed explanation of the incident",
"steps_to_resolve": [
  "Step 1 - actionable instruction",
  "... at least 10 steps"
],
"technical_details": "Technical breakdown including affected systems, logs, errors, configurations",
"complete_description": "Comprehensive summary combining issue, technical details, and recommended actions"
}}

Incident Data:
{incident_json}

Categories:
{categories_json}

Rules:
1. Respond ONLY in valid JSON (no markdown or explanations)
2. At least 10 steps in steps_to_resolve
3. No field left empty
4. Use ServiceNow fields like number, cmdb_ci, assignment_group, opened_at, etc.
"""

    # -------------------------------------------------------------------
    def _get_ai_raw_text(self, ai_analysis) -> str:
        raw_text = ""

        # Gemini format
        if hasattr(ai_analysis, "candidates") and ai_analysis.candidates:
            candidate = ai_analysis.candidates[0]
            parts = getattr(getattr(candidate, "content", {}), "parts", [])
            raw_text = "".join(
                [getattr(p, "text", "") for p in parts if getattr(p, "text", None)]
            ).strip()

        # Fallback: OpenAI-like format
        if not raw_text:
            raw_text = getattr(ai_analysis, "content", "") or ""

        return raw_text.strip()

    # -------------------------------------------------------------------
    def _extract_json_from_ai(self, raw_text: str) -> Dict[str, Any]:
        """Safely extract JSON from AI output."""
        if not raw_text or not raw_text.strip():
            raise ValueError("AI returned no content")

        content = raw_text.replace("```json", "").replace("```", "").strip()
        start, end = content.find("{"), content.rfind("}")

        if start == -1:
            raise ValueError("No JSON object found in AI output")

        if end == -1 or end < start:
            json_substr = content[start:]
            try:
                return json.loads(json_substr)
            except json.JSONDecodeError:
                import re
                kv_pairs = re.findall(r'"(\w+)":\s*"([^"]*)"', json_substr)
                return {k: v for k, v in kv_pairs}

        json_substr = content[start:end + 1]
        try:
            parsed = json.loads(json_substr)
        except json.JSONDecodeError:
            import re
            parsed = {}
            steps_match = re.search(r'"steps_to_resolve"\s*:\s*\[(.*?)\]', json_substr, re.DOTALL)
            if steps_match:
                parsed["steps_to_resolve"] = [
                    s.strip().strip('"') for s in steps_match.group(1).split(",") if s.strip()
                ]
            for field in ["id", "issue", "issue_category", "description", "technical_details", "complete_description"]:
                m = re.search(rf'"{field}"\s*:\s*"([^"]*)"', json_substr)
                parsed[field] = m.group(1) if m else None

        if "steps_to_resolve" in parsed:
            parsed["steps_to_resolve"] = [s.lstrip("0123456789. -") for s in parsed["steps_to_resolve"]]
        return parsed

    # -------------------------------------------------------------------
    def _ensure_ten_steps(self, steps: Optional[List[str]]) -> List[str]:
        """Ensure exactly 10 meaningful steps exist."""
        default_steps = [
            "Verify incident details and confirm affected services.",
            "Check server/network logs for errors.",
            "Review recent changes or deployments.",
            "Attempt to reproduce in test environment.",
            "Check hardware and connectivity.",
            "Run diagnostics (ping, traceroute, netstat).",
            "Validate firewall and routing policies.",
            "Apply safe temporary mitigation.",
            "Update stakeholders and plan next steps.",
            "Perform root cause analysis and prevention plan."
        ]
        if not steps or not isinstance(steps, list):
            steps = []
        cleaned_steps = [s.lstrip("0123456789. -") for s in steps]
        for step in default_steps:
            if len(cleaned_steps) >= 10:
                break
            if step not in cleaned_steps:
                cleaned_steps.append(step)
        return [f"Step {i+1}: {s}" for i, s in enumerate(cleaned_steps[:10])]

    # -------------------------------------------------------------------
    async def _generate_incident_pdf(self, analysis: IncidentAnalysisModel) -> str:
        """Generate PDF and return file path."""
        try:
            pdf_dir = os.path.join(os.getcwd(), "output_pdf")
            os.makedirs(pdf_dir, exist_ok=True)
            pdf_path = os.path.join(pdf_dir, f"{analysis.id}.pdf")

            doc = SimpleDocTemplate(pdf_path, pagesize=A4)
            styles = getSampleStyleSheet()
            elements = [
                Paragraph(f"<b>Issue:</b> {analysis.issue}", styles["Heading2"]),
                Paragraph(analysis.description or "", styles["Normal"]),
                Spacer(1, 12),
                Paragraph("<b>Steps to Resolve:</b>", styles["Heading3"]),
                ListFlowable(
                    [ListItem(Paragraph(str(s), styles["Normal"])) for s in analysis.steps_to_resolve],
                    bulletType="1"
                ),
                Spacer(1, 12),
                Paragraph("<b>Technical Details:</b>", styles["Heading3"]),
                Paragraph(analysis.technical_details or "", styles["Normal"]),
                Spacer(1, 12),
                Paragraph("<b>Complete Description:</b>", styles["Heading3"]),
                Paragraph(analysis.complete_description or "", styles["Normal"])
            ]
            doc.build(elements)
            logger.info("PDF generated successfully", path=pdf_path)
            return pdf_path
        except Exception as e:
            logger.error("Failed to generate PDF", error=str(e))
            raise

    # -------------------------------------------------------------------
    async def _save_json_output(self, analysis: IncidentAnalysisModel) -> str:
        """Save incident analysis as JSON in json_output/."""
        try:
            json_dir = os.path.join(os.getcwd(), "json_output")
            os.makedirs(json_dir, exist_ok=True)
            json_path = os.path.join(json_dir, f"{analysis.id}.json")

            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(jsonable_encoder(analysis), f, indent=2, ensure_ascii=False)

            logger.info("JSON output saved successfully", path=json_path)
            return json_path
        except Exception as e:
            logger.error("Failed to save JSON output", error=str(e))
            raise

    # -------------------------------------------------------------------
    async def analyze_incident_only(self, sys_id: str, analysis_type: str = "general") -> Dict[str, Any]:
        """Analyze incident, save both PDF & JSON outputs."""
        await self._ensure_initialized()
        logger.info("Starting incident analysis", sys_id=sys_id, analysis_type=analysis_type)

        raw_output_path = parsing_error = validation_error = None
        validated_struct: Optional[IncidentAnalysisModel] = None

        try:
            incident = await self.servicenow.get_incident(sys_id)
            incident_dict = incident.model_dump()
            compliance_result = await self.compliance_filter.filter_data(incident_dict, ComplianceLevel.INTERNAL)

            prompt = self._build_ai_prompt(compliance_result.filtered_data, analysis_type)
            ai_analysis = await self.ai_service.generate_text({
                "prompt": prompt,
                "context": {"analysis_type": analysis_type},
                "max_tokens": 2000,
                "temperature": 0.3
            })

            raw_text = self._get_ai_raw_text(ai_analysis)
            logger.info("AI raw text retrieved", length=len(raw_text))

            # Save raw AI output temporarily
            try:
                tmpdir = tempfile.gettempdir()
                raw_output_path = os.path.join(tmpdir, f"ai_raw_{sys_id}_{int(datetime.utcnow().timestamp())}.txt")
                with open(raw_output_path, "w", encoding="utf-8") as f:
                    f.write(raw_text)
            except Exception as e:
                logger.warning("Failed to save raw AI output", error=str(e))

            # Parse AI output
            try:
                parsed_json: Dict[str, Any] = self._extract_json_from_ai(raw_text)
            except Exception as e:
                parsing_error = f"{e}\n{traceback.format_exc()}"
                logger.error("AI JSON extraction failed", error=parsing_error)
                parsed_json = {}

            # Build validated model
            validated_struct = IncidentAnalysisModel(
                id=str(parsed_json.get("id") or uuid.uuid4().hex),
                issue=str(parsed_json.get("issue") or getattr(incident, "short_description", f"Incident {sys_id}")),
                issue_category=str(parsed_json.get("issue_category") or "Other"),
                description=str(parsed_json.get("description") or getattr(incident, "description", "No description available")),
                steps_to_resolve=self._ensure_ten_steps(parsed_json.get("steps_to_resolve")),
                technical_details=str(parsed_json.get("technical_details") or f"Affected CI: {getattr(incident, 'cmdb_ci', 'unknown')} | Group: {getattr(incident, 'assignment_group', 'unknown')}"),
                complete_description=str(parsed_json.get("complete_description") or getattr(incident, "description", "No description available"))
            )

            # Save both PDF and JSON outputs
            pdf_path = await self._generate_incident_pdf(validated_struct)
            json_path = await self._save_json_output(validated_struct)

            return jsonable_encoder({
                "success": parsing_error is None and validation_error is None,
                "sys_id": sys_id,
                "analysis_type": analysis_type,
                "ai_model": getattr(ai_analysis, "model", None),
                "usage": getattr(ai_analysis, "usage", None),
                "data": validated_struct,
                "pdf_path": pdf_path,
                "json_path": json_path,
                "raw_ai_output_path": raw_output_path,
                "parsing_error": parsing_error,
                "validation_error": validation_error
            })

        except ServiceNowNotFoundError:
            logger.error("Incident not found", sys_id=sys_id)
            raise
        except Exception as e:
            logger.error("Unexpected error", sys_id=sys_id, error=str(e), traceback=traceback.format_exc())
            raise

    # -------------------------------------------------------------------
    async def cleanup(self) -> None:
        if self._initialized:
            await self.servicenow.disconnect()
            await self.ai_service.disconnect()
            await self.agentic_service.disconnect()
            await self.compliance_filter.disconnect()
            logger.info("Incident processor cleanup completed")
