"""Incident processing orchestration service with lazy imports to avoid circular dependencies."""

import tempfile
from fastapi.encoders import jsonable_encoder
import structlog
import json
import uuid
import os
import traceback
from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field, ValidationError
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, ListFlowable, ListItem
from reportlab.lib.styles import getSampleStyleSheet

from app.models.incident import IncidentProcessRequest, IncidentSummary
from app.abstracts.compliance import ComplianceLevel
from app.exceptions.servicenow import ServiceNowNotFoundError

logger = structlog.get_logger(__name__)


# ----------------------------
# Pydantic model for structured AI analysis
# ----------------------------
class IncidentAnalysisModel(BaseModel):
    id: str = Field(..., description="Auto-generated ID for the analysis")
    issue: str = Field(..., description="Short title or summary of the issue")
    description: str = Field(..., description="Detailed description of the incident")
    steps_to_resolve: List[str] = Field(..., description="Minimum 10 detailed steps to resolve the issue")
    technical_details: str = Field(..., description="Technical information and context")
    complete_description: str = Field(..., description="Comprehensive write-up combining all insights and recommendations")

# ----------------------------
# Orchestration Service
# ----------------------------
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

    # ----------------------------
    # Helper: Extract JSON from possibly noisy AI output
    # ----------------------------
    def _extract_json_from_ai(self, raw: str) -> str:
        """
        Attempt to obtain the JSON substring from the AI raw output.
        Strips markdown fences and extracts the first {...} block.
        Raises ValueError if no JSON block found.
        """
        if raw is None:
            raise ValueError("AI returned no content")

        content = raw.strip()

        # Remove common code fences
        if "```" in content:
            content = content.replace("```json", "").replace("```", "").strip()

        # Find the first JSON object boundaries
        start = content.find("{")
        end = content.rfind("}")
        if start == -1 or end == -1 or end < start:
            logger.error("No valid JSON found in AI output", raw_output=content[:1000])
            raise ValueError("AI output did not contain a valid JSON object")

        json_str = content[start : end + 1]
        return json_str

    # ----------------------------
    # Main processing entry
    # ----------------------------
    async def process_incident(self, request: IncidentProcessRequest) -> Dict[str, Any]:
        await self._ensure_initialized()
        start_time = datetime.utcnow()
        logger.info("Starting incident processing", sys_id=request.sys_id, analysis_type=request.analysis_type)

        try:
            # Step 1: Fetch incident
            incident = await self.servicenow.get_incident(request.sys_id)
            incident_dict = incident.model_dump()

            # Step 2: Compliance filtering
            compliance_level = ComplianceLevel(request.compliance_level)
            compliance_result = await self.compliance_filter.filter_data(incident_dict, compliance_level)

            # Step 3: AI analysis (raw)
            ai_analysis = await self.openai_service.analyze_incident(
                compliance_result.filtered_data, request.analysis_type
            )

            # --- Robust JSON parsing of AI response ---
            raw_content = (ai_analysis.content or "").strip()
            logger.info("AI raw output preview", preview=raw_content[:500])

            try:
                json_str = self._extract_json_from_ai(raw_content)
                parsed_json = json.loads(json_str)
            except Exception as parse_err:
                # Log and raise a clear error with raw content for debugging
                logger.error(
                    "Failed to extract/parse AI JSON",
                    error=str(parse_err),
                    raw_output=raw_content[:2000]
                )
                raise ValueError(f"Failed to parse AI JSON output: {parse_err}")

            # Validate against Pydantic model if the AI returned the structured model
            ai_result_structured: Optional[Dict[str, Any]] = None
            validated_analysis: Optional[IncidentAnalysisModel] = None
            try:
                # If the AI returned the expected model shape, validate it.
                validated_analysis = IncidentAnalysisModel(**parsed_json)
                ai_result_structured = validated_analysis.dict()
            except ValidationError:
                # AI returned JSON but not the exact model shape; keep parsed JSON as-is
                logger.warning("AI JSON did not validate to IncidentAnalysisModel; using raw parsed JSON")
                ai_result_structured = parsed_json

            # Step 4: Agentic insights (conditional)
            agentic_insights = None
            if request.analysis_type in ["priority_assessment", "classification", "recommendations"]:
                if request.analysis_type == "priority_assessment":
                    agentic_result = await self.agentic_service.analyze_incident_priority(compliance_result.filtered_data)
                elif request.analysis_type == "classification":
                    agentic_result = await self.agentic_service.classify_incident_type(compliance_result.filtered_data)
                else:  # recommendations
                    agentic_result = await self.agentic_service.recommend_actions(compliance_result.filtered_data)
                agentic_insights = getattr(agentic_result, "result", agentic_result)

            history = await self.servicenow.get_incident_history(request.sys_id) if request.include_history else None
            processing_time = (datetime.utcnow() - start_time).total_seconds()

            # If we validated into IncidentAnalysisModel, optionally generate PDF
            pdf_path: Optional[str] = None
            if validated_analysis:
                # ensure id exists
                if not validated_analysis.id:
                    validated_analysis.id = uuid.uuid4().hex
                pdf_path = await self._generate_incident_pdf(validated_analysis)

            return {
                "incident": incident,
                "ai_analysis": {
                    "content": ai_result_structured,
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
                "pdf_path": pdf_path,
                "processing_metadata": {
                    "processing_time": processing_time,
                    "timestamp": datetime.utcnow().isoformat(),
                    "services_used": ["servicenow", "openai", "compliance"]
                }
            }

        except ServiceNowNotFoundError:
            logger.error("Incident not found", sys_id=request.sys_id)
            raise
        except Exception as e:
            logger.error("Error processing incident", sys_id=request.sys_id, error=str(e))
            raise

#     # ----------------------------
#     # Single-incident structured analyze method (returns validated model + PDF)
#     # ----------------------------
#     async def analyze_incident_only(self, sys_id: str, analysis_type: str = "general") -> Dict[str, Any]:
#         """
#         Analyze a single incident, validate to IncidentAnalysisModel if possible,
#         generate a PDF (best-effort), and return structured response. This method
#         is intentionally defensive: AI parsing/validation errors won't raise a 500.
#         """
#         await self._ensure_initialized()
#         logger.info("Analyzing incident (single)", sys_id=sys_id, analysis_type=analysis_type)

#         incident = await self.servicenow.get_incident(sys_id)
#         incident_dict = incident.model_dump()
#         compliance_result = await self.compliance_filter.filter_data(incident_dict, ComplianceLevel.INTERNAL)

#         # Prepare prompt (unchanged)
#         incident_json = json.dumps(compliance_result.filtered_data, indent=2)
#         prompt = f"""
# You are an expert IT service analyst. Analyze the following ServiceNow incident data
# and produce a detailed JSON output matching this exact model:

# {{
#   "id": "auto-generated unique identifier (UUID or timestamp-based string)",
#   "issue": "Short title describing the problem in 1–2 sentences",
#   "description": "Detailed explanation of the incident and its context",
#   "steps_to_resolve": [
#     "Step 1 - clear, actionable technical instruction",
#     "Step 2 - continue until at least 10 detailed steps are provided"
#   ],
#   "technical_details": "Technical breakdown including affected systems, logs, errors, and configurations",
#   "complete_description": "Comprehensive summary combining issue, technical details, and recommended actions"
# }}

# Incident Data:
# {incident_json}

# Rules:
# - Respond ONLY in valid JSON format (no markdown, no ```json``` fences)
# - Must have at least 10 steps in steps_to_resolve
# - Ensure the output can be parsed directly into IncidentAnalysisModel
# """
#         ai_analysis = await self.openai_service.analyze_incident(prompt, analysis_type)

#         raw_content = (ai_analysis.content or "").strip()
#         logger.info("AI raw output preview (first 500 chars)", preview=raw_content[:500])

#         # Save raw AI output to a temp file for debugging (so you can inspect later)
#         raw_output_path = None
#         try:
#             tmpdir = tempfile.gettempdir()
#             raw_output_name = f"ai_raw_{sys_id}_{int(datetime.utcnow().timestamp())}.txt"
#             raw_output_path = os.path.join(tmpdir, raw_output_name)
#             with open(raw_output_path, "w", encoding="utf-8") as f:
#                 f.write(raw_content)
#         except Exception as e:
#             logger.warning("Failed to write AI raw output to temp file", error=str(e))

#         parsed_json = None
#         validated_struct: Optional[IncidentAnalysisModel] = None
#         parsing_error: Optional[str] = None
#         validation_error: Optional[str] = None

#         # 1) Try robust extraction + json.loads
#         try:
#             json_str = self._extract_json_from_ai(raw_content)
#             parsed_json = json.loads(json_str)
#         except Exception as e:
#             parsing_error = str(e)
#             logger.error("AI JSON extraction/parsing failed", error=parsing_error, sys_id=sys_id)

#         # 2) If parsed_json present, try to validate to Pydantic model
#         if parsed_json is not None:
#             try:
#                 validated_struct = IncidentAnalysisModel(**parsed_json)
#             except ValidationError as ve:
#                 validation_error = str(ve)
#                 logger.warning("AI JSON did not validate to IncidentAnalysisModel", error=validation_error)

#         # 3) Fallback: if no valid structured model, build a best-effort IncidentAnalysisModel
#         if validated_struct is None:
#             # create user-friendly defaults using incident data and parsed_json where available
#             fallback_id = None
#             fallback_issue = None
#             fallback_description = None
#             fallback_steps = None
#             fallback_tech = None
#             fallback_complete = None

#             if parsed_json:
#                 fallback_id = parsed_json.get("id")
#                 fallback_issue = parsed_json.get("issue")
#                 fallback_description = parsed_json.get("description")
#                 fallback_steps = parsed_json.get("steps_to_resolve")
#                 fallback_tech = parsed_json.get("technical_details")
#                 fallback_complete = parsed_json.get("complete_description")

#             # ensure minimum defaults
#             if not fallback_id:
#                 fallback_id = uuid.uuid4().hex
#             if not fallback_issue:
#                 # use incident short_description or number
#                 fallback_issue = getattr(incident, "short_description", None) or f"Incident {getattr(incident, 'number', sys_id)}"
#             if not fallback_description:
#                 fallback_description = getattr(incident, "description", "") or "No detailed description provided by AI."
#             if not fallback_steps or not isinstance(fallback_steps, list) or len(fallback_steps) < 10:
#                 # create placeholder steps from incident fields to reach 10 steps
#                 base_steps = []
#                 # prefer AI-provided steps if any
#                 if isinstance(fallback_steps, list):
#                     base_steps.extend([str(s) for s in fallback_steps if isinstance(s, str)])
#                 # add sensible technical investigation steps
#                 base_steps.extend([
#                     "1. Verify the incident details in ServiceNow and confirm affected services.",
#                     "2. Check relevant server/network logs for errors or timeouts.",
#                     "3. Gather recent configuration changes or deployment history.",
#                     "4. Reproduce the issue in a controlled environment if possible.",
#                     "5. Check hardware health and connectivity (NIC, switches, interfaces).",
#                     "6. Run diagnostic commands (ping, traceroute, netstat, tcpdump) as applicable.",
#                     "7. Validate firewall/ACL and routing policies for impacted flows.",
#                     "8. Apply a temporary mitigation (reroute, restart service) if safe.",
#                     "9. Update stakeholders and create an action plan.",
#                     "10. Perform root cause analysis and schedule preventive measures."
#                 ])
#                 # dedupe + limit to 20
#                 seen = set()
#                 cleaned_steps = []
#                 for s in base_steps:
#                     if s not in seen:
#                         cleaned_steps.append(s)
#                         seen.add(s)
#                     if len(cleaned_steps) >= 20:
#                         break
#                 fallback_steps = cleaned_steps

#             if not fallback_tech:
#                 fallback_tech = f"Affected CI: {getattr(incident, 'cmdb_ci', 'unknown')} | Assigned group: {getattr(incident, 'assignment_group', 'unknown')}"
#             if not fallback_complete:
#                 fallback_complete = (fallback_description or "") + "\n\nThis summary was generated by AI; it may require human review."

#             # Build validated_struct from fallbacks
#             try:
#                 validated_struct = IncidentAnalysisModel(
#                     id=fallback_id,
#                     issue=fallback_issue,
#                     description=fallback_description,
#                     steps_to_resolve=fallback_steps,
#                     technical_details=fallback_tech,
#                     complete_description=fallback_complete
#                 )
#             except Exception as e:
#                 # This should not happen given we provide all fields, but guard anyway
#                 logger.error("Failed to construct fallback IncidentAnalysisModel", error=str(e))
#                 raise

#         # 4) Generate PDF (best-effort) and return result; include parsing/validation error info
#         pdf_path = None
#         try:
#             pdf_path = await self._generate_incident_pdf(validated_struct)
#         except Exception as e:
#             logger.error("PDF generation failed", error=str(e), sys_id=sys_id)

#         response = {
#             "success": parsing_error is None and validation_error is None,
#             "sys_id": sys_id,
#             "analysis_type": analysis_type,
#             "ai_model": getattr(ai_analysis, "model", None),
#             "usage": getattr(ai_analysis, "usage", None),
#             "data": validated_struct.dict(),
#             "pdf_path": pdf_path,
#             "raw_ai_output_path": raw_output_path,
#             "parsing_error": parsing_error,
#             "validation_error": validation_error
#         }

#         # If parsing failed, log at error level and return response with success=False for caller to handle
#         if parsing_error or validation_error:
#             logger.error(
#                 "AI analysis completed with issues",
#                 sys_id=sys_id,
#                 parsing_error=parsing_error,
#                 validation_error=validation_error,
#                 raw_output_preview=(raw_content[:1000] + "...") if raw_content else None
#             )

#         return response
# ----------------------------
# Single-incident structured analyze method (returns validated model + PDF)
# ----------------------------
    async def analyze_incident_only(self, sys_id: str, analysis_type: str = "general") -> Dict[str, Any]:
        """
        Analyze a single incident, validate to IncidentAnalysisModel if possible,
        generate a PDF (best-effort), and return structured response.
        This method is defensive: AI parsing/validation errors won't raise a 500.
        """
        await self._ensure_initialized()
        logger.info("Analyzing incident (single)", sys_id=sys_id, analysis_type=analysis_type)

        try:
            # -----------------------------
            # Fetch incident & apply compliance filter
            # -----------------------------
            incident = await self.servicenow.get_incident(sys_id)
            incident_dict = incident.model_dump()
            compliance_result = await self.compliance_filter.filter_data(
                incident_dict, ComplianceLevel.INTERNAL
            )

            # -----------------------------
            # Serialize incident JSON safely
            # -----------------------------
            try:
                incident_json = json.dumps(
                    compliance_result.filtered_data,
                    indent=2,
                    default=lambda o: o.isoformat() if isinstance(o, datetime) else str(o)
                )
            except Exception as e:
                logger.error("Failed to serialize incident JSON", sys_id=sys_id, error=str(e))
                incident_json = "{}"

            # -----------------------------
            # Generate AI prompt and call OpenAI
            # -----------------------------
            prompt = f"Your AI prompt with incident JSON:\n{incident_json}"
            # Pass the dict directly to OpenAI service, don't json.dumps yet
            ai_analysis = await self.openai_service.analyze_incident(
                incident_data=compliance_result.filtered_data,
                analysis_type=analysis_type
            )
            raw_content = (ai_analysis.content or "").strip()
            logger.info("AI raw output preview (first 500 chars)", preview=raw_content[:500])

            # -----------------------------
            # Save raw AI output to temp file
            # -----------------------------
            raw_output_path = None
            try:
                tmpdir = tempfile.gettempdir()
                raw_output_name = f"ai_raw_{sys_id}_{int(datetime.utcnow().timestamp())}.txt"
                raw_output_path = os.path.join(tmpdir, raw_output_name)
                with open(raw_output_path, "w", encoding="utf-8") as f:
                    f.write(raw_content)
            except Exception as e:
                logger.warning("Failed to write AI raw output to temp file", error=str(e))

            # -----------------------------
            # Parse AI JSON safely
            # -----------------------------
            parsed_json = None
            validated_struct: Optional[IncidentAnalysisModel] = None
            parsing_error: Optional[str] = None
            validation_error: Optional[str] = None

            try:
                json_str = self._extract_json_from_ai(raw_content)
                parsed_json = json.loads(json_str)
            except Exception as e:
                parsing_error = f"{str(e)}\n{traceback.format_exc()}"
                logger.error("AI JSON extraction/parsing failed", error=parsing_error, sys_id=sys_id)

            # Ensure parsed_json is a dict
            if isinstance(parsed_json, str):
                try:
                    parsed_json = json.loads(parsed_json)
                except Exception as e:
                    parsing_error = f"parsed_json string failed json.loads: {str(e)}\n{traceback.format_exc()}"
                    logger.warning(parsing_error)
                    parsed_json = None

            # -----------------------------
            # Validate AI JSON to Pydantic model
            # -----------------------------
            if isinstance(parsed_json, dict):
                try:
                    validated_struct = IncidentAnalysisModel(**parsed_json)
                except ValidationError as ve:
                    validation_error = f"{str(ve)}\n{traceback.format_exc()}"
                    logger.warning("AI JSON did not validate to IncidentAnalysisModel", error=validation_error)

            # -----------------------------
            # Fallback: build best-effort model
            # -----------------------------
            if validated_struct is None:
                fallback_id = parsed_json.get("id") if isinstance(parsed_json, dict) else uuid.uuid4().hex
                fallback_issue = parsed_json.get("issue") if isinstance(parsed_json, dict) else getattr(incident, "short_description", f"Incident {getattr(incident, 'number', sys_id)}")
                fallback_description = parsed_json.get("description") if isinstance(parsed_json, dict) else getattr(incident, "description", "No detailed description provided by AI.")
                fallback_steps = parsed_json.get("steps_to_resolve") if isinstance(parsed_json, dict) else []
                fallback_tech = parsed_json.get("technical_details") if isinstance(parsed_json, dict) else f"Affected CI: {getattr(incident, 'cmdb_ci', 'unknown')} | Assigned group: {getattr(incident, 'assignment_group', 'unknown')}"
                fallback_complete = parsed_json.get("complete_description") if isinstance(parsed_json, dict) else fallback_description + "\n\nThis summary was generated by AI; it may require human review."

                # Ensure at least 10 steps
                if len(fallback_steps) < 10:
                    fallback_steps.extend([f"Step {i}" for i in range(len(fallback_steps)+1, 11)])

                validated_struct = IncidentAnalysisModel(
                    id=fallback_id,
                    issue=fallback_issue,
                    description=fallback_description,
                    steps_to_resolve=fallback_steps,
                    technical_details=fallback_tech,
                    complete_description=fallback_complete
                )

            # -----------------------------
            # Generate PDF (best-effort)
            # -----------------------------
            pdf_path = None
            try:
                pdf_path = await self._generate_incident_pdf(validated_struct)
            except Exception as e:
                logger.error("PDF generation failed", error=str(e), sys_id=sys_id)

            # -----------------------------
            # Build response safely
            # -----------------------------
            response = {
                "success": parsing_error is None and validation_error is None,
                "sys_id": sys_id,
                "analysis_type": analysis_type,
                "ai_model": getattr(ai_analysis, "model", None),
                "usage": getattr(ai_analysis, "usage", None),
                "data": validated_struct,  # jsonable_encoder below will handle Pydantic model
                "pdf_path": pdf_path,
                "raw_ai_output_path": raw_output_path,
                "parsing_error": parsing_error,
                "validation_error": validation_error
            }

            # Convert all objects to JSON-safe format
            safe_response = jsonable_encoder(response)

            if parsing_error or validation_error:
                logger.error(
                    "AI analysis completed with issues",
                    sys_id=sys_id,
                    parsing_error=parsing_error,
                    validation_error=validation_error,
                    raw_output_preview=(raw_content[:1000] + "...") if raw_content else None
                )

            return safe_response

        except ServiceNowNotFoundError:
            logger.error("Incident not found", sys_id=sys_id)
            raise
        except Exception as e:
            logger.error("Unexpected error during analyze_incident_only", sys_id=sys_id, error=str(e), traceback=traceback.format_exc())
            raise

    # ----------------------------
    # PDF generation
    # ----------------------------
    async def _generate_incident_pdf(self, analysis: IncidentAnalysisModel) -> str:
        """
        Generate a PDF for a given incident analysis and save it in ./output folder.
        Returns the full file path.
        """
        try:
            # Ensure output folder exists in the project root
            base_dir = os.getcwd()  # Main project path
            output_dir = os.path.join(base_dir, "output")
            os.makedirs(output_dir, exist_ok=True)

            file_name = f"{analysis.id}.pdf"
            file_path = os.path.join(output_dir, file_name)

            # Build PDF
            doc = SimpleDocTemplate(file_path, pagesize=A4)
            styles = getSampleStyleSheet()
            elements = []

            # Issue and Description
            elements.append(Paragraph(f"<b>Issue:</b> {analysis.issue}", styles["Heading2"]))
            elements.append(Paragraph(analysis.description or "", styles["Normal"]))
            elements.append(Spacer(1, 12))

            # Steps to Resolve
            elements.append(Paragraph("<b>Steps to Resolve:</b>", styles["Heading3"]))
            steps = [ListItem(Paragraph(str(s), styles["Normal"])) for s in (analysis.steps_to_resolve or [])]
            elements.append(ListFlowable(steps, bulletType="1"))
            elements.append(Spacer(1, 12))

            # Technical Details
            elements.append(Paragraph("<b>Technical Details:</b>", styles["Heading3"]))
            elements.append(Paragraph(analysis.technical_details or "", styles["Normal"]))
            elements.append(Spacer(1, 12))

            # Complete Description
            elements.append(Paragraph("<b>Complete Description:</b>", styles["Heading3"]))
            elements.append(Paragraph(analysis.complete_description or "", styles["Normal"]))

            # Build PDF
            doc.build(elements)
            logger.info("PDF generated successfully", file_path=file_path)

            return file_path

        except Exception as e:
            logger.error("Failed to generate PDF", error=str(e), analysis_id=analysis.id)
            raise

    # ----------------------------
    # Supporting Methods
    # ----------------------------
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

    async def get_incident_summary(self, sys_id: str) -> IncidentSummary:
        await self._ensure_initialized()
        try:
            incident = await self.servicenow.get_incident(sys_id)
            summary_parts = []
            if getattr(incident, "description", None):
                summary_parts.append(incident.description)
            if getattr(incident, "work_notes", None):
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

    async def cleanup(self) -> None:
        if self._initialized:
            await self.servicenow.disconnect()
            await self.openai_service.disconnect()
            await self.agentic_service.disconnect()
            await self.compliance_filter.disconnect()
            logger.info("Incident processor cleanup completed")