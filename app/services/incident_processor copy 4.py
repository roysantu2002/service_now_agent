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

    async def _ensure_initialized(self) -> None:
        if not self._initialized:
            await self.servicenow.initialize()
            await self.ai_service.initialize()
            await self.agentic_service.initialize()
            await self.compliance_filter.initialize()
            self._initialized = True
            logger.info("Incident processor initialized")

    def _build_ai_prompt(self, incident_data: Dict[str, Any], analysis_type: str) -> str:
        incident_json = json.dumps(incident_data, indent=2, default=str)
        categories_json = json.dumps(ISSUE_CATEGORIES, indent=2)
        prompt = f"""
You are an expert IT service analyst. Analyze the following ServiceNow incident data
and return a structured JSON object exactly matching this model:

{{
"id": "auto-generated UUID",
"issue": "Short title describing the problem",
"issue_category": "One of the predefined categories: {list(ISSUE_CATEGORIES.values())}",
"description": "Detailed explanation of the incident",
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

    # def _extract_json_from_ai(self, raw: str) -> str:
    #     if not raw:
    #         raise ValueError("AI returned no content")
    #     content = raw.strip().replace("```json", "").replace("```", "").strip()
    #     start, end = content.find("{"), content.rfind("}")
    #     if start == -1 or end == -1 or end < start:
    #         logger.error("No valid JSON found in AI output", raw_output=content[:1000])
    #         raise ValueError("AI output did not contain a valid JSON object")
    #     return content[start:end + 1]
    
    # ----------------------------
    # Extract JSON safely from AI output (OpenAI or Gemini)
    # ----------------------------
    # def _extract_json_from_ai(self, raw: str) -> str:
    #     """
    #     Robust JSON extraction from AI output.
    #     Supports:
    #     - OpenAI: single string content
    #     - Gemini: candidates[0].content.parts list
    #     """
    #     # Normalize raw content
    #     if not raw or not raw.strip():
    #         raise ValueError("AI returned no content")
        
    #     content = raw.strip()
        
    #     # Remove Markdown code fences if present
    #     if content.startswith("```json"):
    #         content = content[7:]
    #     content = content.replace("```", "").strip()
        
    #     # Find first { and last } to extract JSON substring
    #     start = content.find("{")
    #     end = content.rfind("}")
    #     if start == -1 or end == -1 or end < start:
    #         # Try to fix common Gemini formatting quirks: flatten and search again
    #         content_flat = content.replace("\n", "").replace("\r", "")
    #         start = content_flat.find("{")
    #         end = content_flat.rfind("}")
    #         if start == -1 or end == -1 or end < start:
    #             raise ValueError(f"AI output did not contain a valid JSON object: {content[:500]}")
    #         content = content_flat
        
    #     return content[start:end + 1]


    # # ----------------------------
    # # Normalizing AI output for Gemini or OpenAI
    # # ----------------------------
    # def _get_ai_raw_text(self, ai_analysis) -> str:
    #     """
    #     Return normalized raw text from AI connector output.
    #     Works for OpenAI or Gemini.
    #     """
    #     raw_text = ""

    #     # Gemini: candidates[0].content.parts
    #     if hasattr(ai_analysis, "candidates") and ai_analysis.candidates:
    #         candidate = ai_analysis.candidates[0]
    #         parts = getattr(getattr(candidate, "content", {}), "parts", [])
    #         raw_text = "".join([getattr(p, "text", "") for p in parts if getattr(p, "text", None)]).strip()

    #     # Fallback: OpenAI style
    #     if not raw_text:
    #         raw_text = getattr(ai_analysis, "content", "") or ""

    #     return raw_text.strip()
    
    # ----------------------------
    # Normalize AI output from Gemini or OpenAI
    # ----------------------------
    def _get_ai_raw_text(self, ai_analysis) -> str:
        """
        Extract raw text from AI output.
        - Gemini: concatenates all parts in candidates[0].content.parts
        - OpenAI: uses content
        """
        raw_text = ""

        # Gemini
        if hasattr(ai_analysis, "candidates") and ai_analysis.candidates:
            candidate = ai_analysis.candidates[0]
            parts = getattr(getattr(candidate, "content", {}), "parts", [])
            raw_text = "".join([getattr(p, "text", "") for p in parts if getattr(p, "text", None)]).strip()

        # OpenAI fallback
        if not raw_text:
            raw_text = getattr(ai_analysis, "content", "") or ""

        return raw_text.strip()


    # ----------------------------
    # Robust JSON extraction
    # ----------------------------
    def _extract_json_from_ai(self, raw_text: str) -> str:
        """
        Extract JSON safely from AI output. Removes Markdown fences and fixes truncation if possible.
        """
        if not raw_text or not raw_text.strip():
            raise ValueError("AI returned no content")

        content = raw_text.strip()
        content = content.replace("```json", "").replace("```", "").strip()

        # Attempt to locate first { and last } for JSON substring
        start = content.find("{")
        end = content.rfind("}")

        if start == -1 or end == -1 or end < start:
            # Try flattening newlines for Gemini style long strings
            flat = content.replace("\n", "").replace("\r", "")
            start = flat.find("{")
            end = flat.rfind("}")
            if start == -1 or end == -1 or end < start:
                raise ValueError(f"AI output did not contain a valid JSON object: {content[:500]}")
            content = flat

        json_str = content[start:end + 1]

        # Optional: strip numbered prefixes in steps_to_resolve
        try:
            parsed = json.loads(json_str)
            steps = parsed.get("steps_to_resolve", [])
            cleaned_steps = [s.lstrip("0123456789. -") for s in steps]
            parsed["steps_to_resolve"] = cleaned_steps
            return json.dumps(parsed)
        except Exception:
            # fallback: return raw substring if parsing fails
            return json_str

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

    # async def analyze_incident_only(self, sys_id: str, analysis_type: str = "general") -> Dict[str, Any]:
    #     await self._ensure_initialized()
    #     logger.info("Analyzing incident", sys_id=sys_id, analysis_type=analysis_type)

    #     raw_output_path = None
    #     parsing_error = validation_error = None
    #     validated_struct: Optional[IncidentAnalysisModel] = None

    #     try:
    #         # Fetch incident & filter
    #         incident = await self.servicenow.get_incident(sys_id)
    #         incident_dict = incident.model_dump()
    #         compliance_result = await self.compliance_filter.filter_data(incident_dict, ComplianceLevel.INTERNAL)

    #         # Build prompt & call AI
    #         prompt = self._build_ai_prompt(compliance_result.filtered_data, analysis_type)
    #         ai_analysis = await self.ai_service.generate_text({
    #             "prompt": prompt,
    #             "context": {"analysis_type": analysis_type},
    #             "max_tokens": 1200,
    #             "temperature": 0.3
    #         })

    #         # Save raw output
    #         try:
    #             tmpdir = tempfile.gettempdir()
    #             raw_output_path = os.path.join(tmpdir, f"ai_raw_{sys_id}_{int(datetime.utcnow().timestamp())}.txt")
    #             with open(raw_output_path, "w", encoding="utf-8") as f:
    #                 f.write(ai_analysis.content or "")
    #         except Exception as e:
    #             logger.warning("Failed to write AI raw output", error=str(e))

    #         # ----------------------------
    #         # Detect provider and parse JSON
    #         # ----------------------------
    #         provider_name = getattr(self.ai_service, "provider_name", "").lower()
    #         parsed_json: Dict[str, Any] = {}

    #         try:
    #             if "gemini" in provider_name:
    #                 # Gemini specific parsing
    #                 candidates = getattr(ai_analysis, "candidates", [])
    #                 if candidates:
    #                     parts = getattr(candidates[0].content, "parts", [])
    #                     gemini_text = "".join([getattr(p, "text", "") for p in parts if getattr(p, "text", None)])
    #                     json_str = self._extract_json_from_ai(gemini_text)
    #                 else:
    #                     json_str = "{}"
    #             else:
    #                 # OpenAI / default
    #                 json_str = self._extract_json_from_ai(ai_analysis.content or "")

    #             parsed_json = json.loads(json_str)

    #         except Exception as e:
    #             parsing_error = f"{str(e)}\n{traceback.format_exc()}"
    #             logger.error("AI JSON extraction/parsing failed", error=parsing_error, sys_id=sys_id)

    #         # ----------------------------
    #         # Validate or fallback to defaults
    #         # ----------------------------
    #         validated_struct = IncidentAnalysisModel(
    #             id=str(parsed_json.get("id") or uuid.uuid4().hex),
    #             issue=str(parsed_json.get("issue") or getattr(incident, "short_description", f"Incident {sys_id}")),
    #             issue_category=str(parsed_json.get("issue_category") or "Other"),
    #             description=str(parsed_json.get("description") or getattr(incident, "description", "No description available")),
    #             steps_to_resolve=self._ensure_ten_steps(parsed_json.get("steps_to_resolve")),
    #             technical_details=str(parsed_json.get("technical_details") or f"Affected CI: {getattr(incident, 'cmdb_ci', 'unknown')} | Assigned group: {getattr(incident, 'assignment_group', 'unknown')}"),
    #             complete_description=str(parsed_json.get("complete_description") or getattr(incident, "description", "No description available") + "\n\nThis summary was generated by AI; it may require human review.")
    #         )

    #         pdf_path = await self._generate_incident_pdf(validated_struct)

    #         return jsonable_encoder({
    #             "success": parsing_error is None and validation_error is None,
    #             "sys_id": sys_id,
    #             "analysis_type": analysis_type,
    #             "ai_model": getattr(ai_analysis, "model", None),
    #             "usage": getattr(ai_analysis, "usage", None),
    #             "data": validated_struct,
    #             "pdf_path": pdf_path,
    #             "raw_ai_output_path": raw_output_path,
    #             "parsing_error": parsing_error,
    #             "validation_error": validation_error
    #         })

    #     except ServiceNowNotFoundError:
    #         logger.error("Incident not found", sys_id=sys_id)
    #         raise
    #     except Exception as e:
    #         logger.error("Unexpected error during analyze_incident_only", sys_id=sys_id, error=str(e), traceback=traceback.format_exc())
    #         raise

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
                    "max_tokens": 2000,  # increase to avoid truncation
                    "temperature": 0.3
                }
            )

            # ----------------------------
            # Extract raw AI output
            # ----------------------------
            def _get_ai_raw_text(ai_analysis) -> str:
                raw_text = ""

                # Gemini style
                if hasattr(ai_analysis, "candidates") and ai_analysis.candidates:
                    candidate = ai_analysis.candidates[0]
                    parts = getattr(getattr(candidate, "content", {}), "parts", [])
                    raw_text = "".join([getattr(p, "text", "") for p in parts if getattr(p, "text", None)]).strip()

                # OpenAI fallback
                if not raw_text:
                    raw_text = getattr(ai_analysis, "content", "") or ""

                return raw_text.strip()

            raw_text = _get_ai_raw_text(ai_analysis)
            print("⚡ AI Raw Output:\n", raw_text[:2000])

            # Save AI raw output
            try:
                tmpdir = tempfile.gettempdir()
                raw_output_path = os.path.join(tmpdir, f"ai_raw_{sys_id}_{int(datetime.utcnow().timestamp())}.txt")
                with open(raw_output_path, "w", encoding="utf-8") as f:
                    f.write(raw_text)
            except Exception as e:
                logger.warning("Failed to write AI raw output", error=str(e))

            # ----------------------------
            # Parse JSON safely
            # ----------------------------
            try:
                def _extract_json_from_ai(raw_text: str) -> str:
                    if not raw_text or not raw_text.strip():
                        raise ValueError("AI returned no content")

                    content = raw_text.replace("```json", "").replace("```", "").strip()
                    start, end = content.find("{"), content.rfind("}")
                    if start == -1 or end == -1 or end < start:
                        raise ValueError(f"AI output did not contain a valid JSON object: {content[:500]}")
                    json_str = content[start:end + 1]

                    # Clean numbered steps
                    try:
                        parsed = json.loads(json_str)
                        steps = parsed.get("steps_to_resolve", [])
                        parsed["steps_to_resolve"] = [s.lstrip("0123456789. -") for s in steps]
                        return json.dumps(parsed)
                    except Exception:
                        return json_str

                parsed_json: Dict[str, Any] = json.loads(_extract_json_from_ai(raw_text))
            except Exception as e:
                parsing_error = f"{str(e)}\n{traceback.format_exc()}"
                logger.error("AI JSON extraction/parsing failed", error=parsing_error, sys_id=sys_id)
                parsed_json = {}

            # ----------------------------
            # Validate or fallback to defaults
            # ----------------------------
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

        
    async def cleanup(self) -> None:
        if self._initialized:
            await self.servicenow.disconnect()
            await self.ai_service.disconnect()
            await self.agentic_service.disconnect()
            await self.compliance_filter.disconnect()
            logger.info("Incident processor cleanup completed")
