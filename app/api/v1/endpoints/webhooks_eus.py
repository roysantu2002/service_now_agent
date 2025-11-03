"""
ServiceNow Webhook Handlers

This module provides webhook endpoints for receiving and processing ServiceNow incident updates.
It handles incident data synchronization, AI analysis triggering, and logging for audit purposes.
"""

import json
from fastapi import APIRouter, HTTPException, Path, Request, Depends, Query
from typing import Dict, Any, Optional, List
import structlog
from datetime import datetime

from app.services.servicenow import ServiceNowConnector
from app.exceptions.servicenow import ServiceNowError
from app.services.incident_classifier import (
    IncidentClassifierService,
    IncidentClassifierError,
    create_incident_classifier,
)
from app.models.incident import ServiceNowIncident, ServiceNowIncidentUpdateRequest
from app.utils.db_utils import (
    execute_query,
    fetch_many,
    fetch_one,
    initialize_database,
    initialize_tables,
    upsert_webhook_event,   # ✅ Added import for upsert support
    store_incident_analysis, # ensure imported (using module path)
)

# -------------------------------------------------------
# Structured logger setup
# -------------------------------------------------------
logger = structlog.get_logger(__name__)
router = APIRouter()

print(">>> webhooks_eus.py LOADED")


# -------------------------------------------------------
# Initialize database and ensure tables exist
# -------------------------------------------------------
async def _init_db_once():
    try:
        await initialize_database()
        await initialize_tables()
        logger.info("✅ Database initialized and tables verified (webhook_events, incident_analysis)")
    except Exception as e:
        logger.error("❌ Database initialization failed", error=str(e))

@router.on_event("startup")
async def ensure_db_tables():
    await _init_db_once()

# -------------------------------------------------------
# Dependency: Get ServiceNow connector
# -------------------------------------------------------
async def get_servicenow_connector() -> ServiceNowConnector:
    conn = ServiceNowConnector()
    await conn.initialize()
    return conn

# -------------------------------------------------------
# Enum & Level Mapping
# -------------------------------------------------------
def map_servicenow_enums(data: dict) -> dict:
    """
    Normalize ServiceNow enums into values acceptable by ServiceNowIncident model.
    Also derive an additional `level` field for display (L1/L2/L3).
    """
    # Priority normalization
    priority_map = {
        "1": "critical",
        "2": "high",
        "3": "medium",
        "4": "low",
        "5": "planned",
    }

    # Category normalization
    category_map = {
        "database": "software",
        "application": "software",
        "network": "network",
        "hardware": "hardware",
        "question": "question",
        "request": "request",
        "problem": "problem",
        "inquiry": "inquiry",
    }

    # Severity normalization
    severity_map = {
        "1": "high",
        "2": "medium",
        "3": "low",
        "L1": "high",
        "L2": "medium",
        "L3": "low",
        "High": "high",
        "Medium": "medium",
        "Low": "low",
    }

    # Incident state normalization
    state_map = {
        "1": "New",
        "2": "In Progress",
        "3": "On Hold",
        "6": "Resolved",
        "7": "Closed",
        "8": "Canceled",
    }

    # Derive level (L1/L2/L3) based on impact or urgency
    def derive_level(val: Any) -> str:
        if str(val) in ["1", "high", "High", "critical", "Critical"]:
            return "L1"
        if str(val) in ["2", "medium", "Medium"]:
            return "L2"
        if str(val) in ["3", "low", "Low"]:
            return "L3"
        return "L3"

    # Apply all mappings
    if "priority" in data:
        data["priority"] = priority_map.get(str(data["priority"]), data["priority"])
    if "impact" in data:
        data["impact"] = severity_map.get(str(data["impact"]), "medium")
    if "urgency" in data:
        data["urgency"] = severity_map.get(str(data["urgency"]), "medium")
    if "category" in data:
        data["category"] = category_map.get(str(data["category"]).lower(), "software")
    if "state" in data:
        data["state"] = state_map.get(str(data["state"]), "New")

    # Add derived level
    data["level"] = derive_level(data.get("impact") or data.get("urgency") or data.get("priority"))

    return data


# -------------------------------------------------------
# Database utility functions
# -------------------------------------------------------
async def store_webhook_event(incident_id, sys_id, action_type, payload, incident_data) -> str:
    """
    Insert a webhook event into the database and return its UUID.
    This method is still available but not used for primary upserts.
    """
    try:
        payload_json = json.dumps(payload, ensure_ascii=False)
        incident_data_json = json.dumps(incident_data, ensure_ascii=False)

        query = """
            INSERT INTO webhook_events 
            (incident_id, sys_id, action_type, payload, incident_data, status, created_at)
            VALUES ($1, $2, $3, $4, $5, $6, NOW())
            RETURNING id::text
        """

        record_id = await execute_query(
            query,
            incident_id, sys_id, action_type, payload_json, incident_data_json, "received",
            return_value=True
        )

        logger.info("Webhook stored in DB", incident_id=incident_id, sys_id=sys_id, record_id=record_id)
        return str(record_id)

    except Exception as e:
        logger.error("DB insert failed", incident_id=incident_id, sys_id=sys_id, error=str(e))
        raise IncidentClassifierError(f"DB storage failed: {str(e)}")


async def update_webhook_processing(record_id, status, ai_processed=False, ai_analysis_results=None, error_message=None):
    """
    Update the processing status of a webhook event.
    """
    try:
        await execute_query(
            """
            UPDATE webhook_events 
            SET status = $2, 
                ai_processed = $3, 
                ai_analysis_results = $4,
                error_message = $5,
                processing_completed_at = NOW(),
                updated_at = NOW()
            WHERE id = $1::uuid
            """,
            record_id, status, ai_processed, json.dumps(ai_analysis_results or {}), error_message
        )
        logger.info("Webhook status updated", record_id=record_id, status=status)
    except Exception as e:
        logger.error("Webhook update failed", record_id=record_id, error=str(e))


# -------------------------------------------------------
# Store AI Analysis (uses db_utils.store_incident_analysis under-the-hood)
# -------------------------------------------------------
async def store_analysis_record(webhook_event_id, incident_id, sys_id, analysis_result_obj, ai_model_used="unknown"):
    """
    Accepts either a dict or ClassificationResult-like object.
    Ensures correct fields and passes analysis_level to DB.
    """
    # Support both dict and dataclass-like objects
    if hasattr(analysis_result_obj, "category"):
        # dataclass-like (ClassificationResult)
        analysis_results = {
            "category": getattr(analysis_result_obj, "category").value if hasattr(analysis_result_obj, "category") else analysis_result_obj.category,
            "severity": getattr(analysis_result_obj, "severity").value if hasattr(analysis_result_obj, "severity") else analysis_result_obj.severity,
            "confidence": getattr(analysis_result_obj, "confidence", None),
            "reasoning": getattr(analysis_result_obj, "reasoning", None),
            "supporting_evidence": getattr(analysis_result_obj, "supporting_evidence", []),
            "suggested_priority": getattr(analysis_result_obj, "suggested_priority", None),
            "recommended_actions": getattr(analysis_result_obj, "recommended_actions", []),
            "related_incidents": getattr(analysis_result_obj, "related_incidents", []),
            "metadata": getattr(analysis_result_obj, "metadata", {}),
        }
        analysis_level = getattr(analysis_result_obj, "analysis_level", None)
    else:
        analysis_results = analysis_result_obj
        analysis_level = analysis_results.get("analysis_level")

    # Persist using db_utils helper
    return await store_incident_analysis(
        webhook_event_id=webhook_event_id,
        incident_id=incident_id,
        sys_id=sys_id,
        analysis_results=analysis_results,
        ai_model_used=ai_model_used,
        analysis_level=analysis_level
    )


# -------------------------------------------------------
# Logging helpers
# -------------------------------------------------------
def log_webhook_event(event_type, incident_id, sys_id, status, details):
    logger.info(
        "ServiceNow webhook event",
        event_type=event_type,
        incident_id=incident_id,
        sys_id=sys_id,
        status=status,
        timestamp=datetime.utcnow().isoformat(),
        **details,
    )


def log_ai_decision(sys_id, incident_id, decision, confidence, reasoning, tier=None):
    logger.info(
        "AI decision logged",
        sys_id=sys_id,
        incident_id=incident_id,
        decision=decision,
        confidence=confidence,
        reasoning=reasoning,
        predicted_tier=tier,
        timestamp=datetime.utcnow().isoformat(),
    )

# -------------------------------------------------------
# AI Processing
# -------------------------------------------------------
async def trigger_ai_analysis(
    incident: ServiceNowIncident,
    servicenow_integration: Optional[ServiceNowConnector] = None
) -> Dict[str, Any]:
    try:
        classifier = create_incident_classifier()
        text = incident.short_description or incident.description or "No description provided"
        context = {
            "environment": "production",
            "source": "servicenow_webhook",
            "sys_id": incident.sys_id,
            "incident_number": incident.number,
            "category": getattr(incident.category, "value", None),
            "priority": getattr(incident.priority, "value", None),
            "assignment_group": incident.assignment_group,
        }

        logger.info("Starting AI analysis", sys_id=incident.sys_id, text_preview=text[:100])

        # NOTE: analyze_incident returns a ClassificationResult dataclass instance
        result = await classifier.analyze_incident(text, context)

        log_ai_decision(
            sys_id=incident.sys_id,
            incident_id=incident.number,
            decision="tier_classification",
            confidence=result.confidence,
            reasoning=result.reasoning,
            tier=result.category.value,
        )

        # Build analysis_results dict from ClassificationResult
        analysis_results = {
            "category": result.category.value,
            "severity": result.severity.value,
            "confidence": result.confidence,
            "reasoning": result.reasoning,
            "supporting_evidence": result.supporting_evidence,
            "suggested_priority": result.suggested_priority,
            "recommended_actions": result.recommended_actions,
            "predicted_tier": result.category.value,
            "metadata": result.metadata,
            "analysis_level": getattr(result, "analysis_level", None),
        }

        if servicenow_integration and incident.sys_id:
            try:
                await servicenow_integration.add_ai_prediction(
                    sys_id=incident.sys_id,
                    predicted_tier=result.category.value,
                    confidence=result.confidence,
                    routing_reason=result.reasoning,
                )
                analysis_results["service_now_updated"] = True
            except ServiceNowError as e:
                analysis_results["service_now_updated"] = False
                analysis_results["update_error"] = str(e)

        return analysis_results

    except Exception as e:
        logger.error("AI analysis failed", sys_id=incident.sys_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"AI analysis failed: {e}")

# -------------------------------------------------------
# Webhook Handler
# -------------------------------------------------------
@router.post("/servicenow/incident-update")
async def handle_servicenow_incident_update(
    request: Request,
    servicenow_integration: ServiceNowConnector = Depends(get_servicenow_connector),
) -> Dict[str, Any]:
    webhook_record_id = None
    incident_id = sys_id = None
    try:
        payload = await request.json()
        result = payload.get("result", {}) if isinstance(payload, dict) else {}
        incident_id = result.get("number") or payload.get("incident_id")
        sys_id = result.get("sys_id") or payload.get("sys_id")
        if not sys_id:
            raise HTTPException(status_code=400, detail="Missing sys_id in payload")

        # Map enums and add derived level
        incident_data = map_servicenow_enums(result)
        action_type = payload.get("action_type", "update")

        webhook_record_id = await upsert_webhook_event(
            incident_id=incident_id,
            sys_id=sys_id,
            action_type=action_type,
            payload=payload,
            incident_data=incident_data,
            status="received",
        )

        # Build model object for classifier (ServiceNowIncident)
        # ensure sys_id present
        incident_data["sys_id"] = sys_id
        incident = ServiceNowIncident(**incident_data)

        if action_type in ["create", "update", "reopen"]:
            await execute_query(
                "UPDATE webhook_events SET status='processing' WHERE id=$1::uuid",
                webhook_record_id,
            )

            analysis_results = await trigger_ai_analysis(incident, servicenow_integration)

            # Ensure analysis_level exists (if classifier provided it, use that; else derive)
            analysis_level = analysis_results.get("analysis_level")
            if not analysis_level:
                # derive from severity and suggested_priority
                sev = analysis_results.get("severity", "medium")
                pr = analysis_results.get("suggested_priority", 3)
                if str(sev) in ("critical", "high") or pr in (1, 2):
                    analysis_level = "L1"
                elif str(sev) in ("medium",) or pr == 3:
                    analysis_level = "L2"
                else:
                    analysis_level = "L3"
                analysis_results["analysis_level"] = analysis_level

            # persist analysis (store_incident_analysis writes analysis_level into DB)
            await store_analysis_record(webhook_record_id, incident_id, sys_id, analysis_results)

            await execute_query(
                "UPDATE webhook_events SET status='completed', ai_processed=true, ai_analysis_results=$2::jsonb WHERE id=$1::uuid",
                webhook_record_id, json.dumps(analysis_results)
            )
        else:
            await execute_query(
                "UPDATE webhook_events SET status='skipped' WHERE id=$1::uuid",
                webhook_record_id,
            )

        return {"success": True, "incident_id": incident_id, "sys_id": sys_id}

    except Exception as e:
        logger.error("Webhook processing failed", sys_id=sys_id, error=str(e))
        if webhook_record_id:
            await execute_query(
                "UPDATE webhook_events SET status='error', error_message=$2 WHERE id=$1::uuid",
                webhook_record_id, str(e)
            )
        raise HTTPException(status_code=500, detail=f"Webhook error: {e}")
    
# -------------------------------------------------------
# Health Check Endpoint
# -------------------------------------------------------
@router.get("/servicenow/webhook/health")
async def webhook_health_check() -> Dict[str, Any]:
    health = {
        "status": "healthy",
        "service": "servicenow_webhook_handlers",
        "timestamp": datetime.utcnow().isoformat(),
        "components": {"database": "unknown", "ai_classifier": "unknown"},
    }
    try:
        await execute_query("SELECT 1")
        health["components"]["database"] = "healthy"
    except Exception as e:
        health["components"]["database"] = f"unhealthy: {e}"
        health["status"] = "degraded"

    try:
        classifier = create_incident_classifier()
        cls_health = await classifier.health_check()
        health["components"]["ai_classifier"] = cls_health["status"]
    except Exception as e:
        health["components"]["ai_classifier"] = f"unhealthy: {e}"
        health["status"] = "degraded"

    return health

# -------------------------------------------------------
# Incident Listing Endpoint (Enhanced with AI Sync + Payload)
# -------------------------------------------------------
@router.get("/servicenow/incidents")
async def list_incidents(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=200),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
) -> Dict[str, Any]:
    """
    List webhook incidents with full payload info,
    automatically marking 'ai_processed = true' if their
    incident_id exists in the incident_analysis table.
    """
    try:
        offset = (page - 1) * page_size
        params, where_clauses = [], []

        # Optional date filters
        if start_date:
            where_clauses.append(f"created_at >= ${len(params) + 1}")
            params.append(f"{start_date} 00:00:00")

        if end_date:
            where_clauses.append(f"created_at <= ${len(params) + 1}")
            params.append(f"{end_date} 23:59:59")

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        # --- Count total records ---
        total_query = f"SELECT COUNT(*) AS total FROM webhook_events {where_sql}"
        total_row = await fetch_one(total_query, *params)
        total_count = int(total_row["total"]) if total_row else 0

        # --- Fetch paginated data ---
        params += [page_size, offset]
        data_query = f"""
            SELECT id::text AS id,
                   incident_id,
                   sys_id,
                   action_type,
                   status,
                   ai_processed,
                   payload,                -- ✅ Added full payload field
                   created_at,
                   processing_completed_at,
                   error_message
            FROM webhook_events
            {where_sql}
            ORDER BY created_at DESC
            LIMIT ${len(params) - 1} OFFSET ${len(params)}
        """
        rows = await fetch_many(data_query, *params)

        # --- ✅ Fetch analyzed incident IDs for AI processed marking ---
        analyzed_query = "SELECT DISTINCT incident_id FROM incident_analysis"
        analyzed_rows = await fetch_many(analyzed_query)
        analyzed_ids = {r["incident_id"] for r in analyzed_rows or []}

        # --- Process each record ---
        incidents = []
        for r in rows or []:
            row = dict(r)
            # Auto-mark as AI processed if found in analysis table
            if row.get("incident_id") in analyzed_ids:
                row["ai_processed"] = True

            # Convert datetime fields to ISO strings
            for field in ["created_at", "processing_completed_at"]:
                if hasattr(row.get(field), "isoformat"):
                    row[field] = row[field].isoformat()

            # Parse payload JSON safely
            if isinstance(row.get("payload"), str):
                try:
                    row["payload"] = json.loads(row["payload"])
                except Exception:
                    pass

            incidents.append(row)

        return {
            "page": page,
            "page_size": page_size,
            "total_records": total_count,
            "total_pages": (total_count + page_size - 1) // page_size,
            "filters_applied": {"start_date": start_date, "end_date": end_date},
            "data": incidents,
        }

    except Exception as e:
        logger.error("Incident list retrieval failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to retrieve incidents: {e}")

# -------------------------------------------------------
# AI Analysis Listing and Specific Lookup Endpoint
# -------------------------------------------------------

@router.get("/servicenow/analysis")
async def list_analysis(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=200),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    sys_id: Optional[str] = Query(None),
    incident_id: Optional[str] = Query(None),
) -> Dict[str, Any]:
    """
    Retrieve paginated AI analysis records with optional filters.
    Uses the `incident_analysis` table.
    """
    try:
        offset = (page - 1) * page_size
        params, where_clauses = [], []

        # Apply filters dynamically
        if start_date:
            where_clauses.append(f"created_at >= ${len(params) + 1}")
            params.append(f"{start_date} 00:00:00")

        if end_date:
            where_clauses.append(f"created_at <= ${len(params) + 1}")
            params.append(f"{end_date} 23:59:59")

        if sys_id:
            where_clauses.append(f"sys_id = ${len(params) + 1}")
            params.append(sys_id.strip())

        if incident_id:
            where_clauses.append(f"incident_id = ${len(params) + 1}")
            params.append(incident_id.strip())

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        # --- Count total records ---
        total_query = f"SELECT COUNT(*) AS total FROM incident_analysis {where_sql}"
        total_row = await fetch_one(total_query, *params)
        total_count = int(total_row["total"]) if total_row else 0

        # --- Fetch paginated data ---
        params += [page_size, offset]
        data_query = f"""
            SELECT id::text, webhook_event_id::text, incident_id, sys_id,
                   category, severity, confidence, reasoning,
                   supporting_evidence, suggested_priority,
                   recommended_actions, related_incidents, metadata,
                   ai_model_used, analysis_level, processing_time_ms, created_at, updated_at
            FROM incident_analysis
            {where_sql}
            ORDER BY created_at DESC
            LIMIT ${len(params) - 1} OFFSET ${len(params)}
        """

        rows = await fetch_many(data_query, *params)

        # --- Format result ---
        data = []
        for r in rows or []:
            row = dict(r)
            for field in ["created_at", "updated_at"]:
                if hasattr(row.get(field), "isoformat"):
                    row[field] = row[field].isoformat()
            data.append(row)

        return {
            "page": page,
            "page_size": page_size,
            "total_records": total_count,
            "total_pages": (total_count + page_size - 1) // page_size,
            "filters_applied": {
                "start_date": start_date,
                "end_date": end_date,
                "sys_id": sys_id,
                "incident_id": incident_id,
            },
            "data": data,
        }

    except Exception as e:
        logger.error("Analysis list retrieval failed", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to retrieve analysis data: {e}")


# -------------------------------------------------------
# Get Specific Analysis for an Incident
# -------------------------------------------------------
@router.get("/servicenow/analysis/{incident_id}")
async def get_analysis_by_incident(incident_id: str) -> Dict[str, Any]:
    """
    Retrieve AI analysis record(s) for a specific incident_id.
    Uses the `incident_analysis` table.
    """
    try:
        query = """
            SELECT id::text, webhook_event_id::text, incident_id, sys_id,
                   category, severity, confidence, reasoning,
                   supporting_evidence, suggested_priority,
                   recommended_actions, related_incidents, metadata,
                   ai_model_used, analysis_level, processing_time_ms, created_at, updated_at
            FROM incident_analysis
            WHERE incident_id = $1
            ORDER BY created_at DESC
        """
        rows = await fetch_many(query, incident_id.strip())

        if not rows:
            raise HTTPException(status_code=404, detail=f"No analysis found for incident {incident_id}")

        data = []
        for r in rows:
            row = dict(r)
            for field in ["created_at", "updated_at"]:
                if hasattr(row.get(field), "isoformat"):
                    row[field] = row[field].isoformat()
            data.append(row)

        return {
            "incident_id": incident_id,
            "record_count": len(data),
            "data": data,
        }

    except Exception as e:
        logger.error("Analysis fetch by incident failed", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch analysis for {incident_id}: {e}")

# -------------------------------------------------------
# Endpoint: Update specific incident fields in ServiceNow
# -------------------------------------------------------
@router.patch("/servicenow/incident/{sys_id}/update-fields", summary="Update selected fields for a ServiceNow incident")
async def update_servicenow_incident_fields(
    sys_id: str = Path(..., description="ServiceNow sys_id of the incident"),
    fields: ServiceNowIncidentUpdateRequest = ...,
    servicenow_integration: ServiceNowConnector = Depends(get_servicenow_connector),
) -> Dict[str, Any]:
    """
    Update one or more fields for an existing ServiceNow incident.
    
    ✅ Allowed fields:
    - short_description
    - category
    - assignment_group
    - assigned_to
    - work_notes
    - urgency
    - impact
    """

    updates = fields.dict(exclude_none=True)

    if not updates:
        raise HTTPException(status_code=400, detail="No fields provided for update")

    # Allow up to 7 fields (previously limited to 5)
    if len(updates) > 7:
        raise HTTPException(status_code=400, detail="Too many fields provided. Maximum allowed is 7.")

    try:
        logger.info("Updating ServiceNow incident", sys_id=sys_id, updates=updates)

        # Perform update via connector
        response = await servicenow_integration.update_incident_fields(sys_id=sys_id, updates=updates)

        logger.info("Incident updated successfully", sys_id=sys_id, response=response)
        return {
            "success": True,
            "sys_id": sys_id,
            "updated_fields": updates,
            "servicenow_response": response,
        }

    except ServiceNowError as e:
        logger.error("ServiceNow update failed", sys_id=sys_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"ServiceNow update failed: {e}")

    except Exception as e:
        logger.error("Unexpected error during incident update", sys_id=sys_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Error updating incident {sys_id}: {e}")