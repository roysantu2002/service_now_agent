# webhooks_eus.py

"""
ServiceNow Webhook Handlers

This module provides webhook endpoints for receiving and processing ServiceNow incident updates.
It handles incident data synchronization, AI analysis triggering, and logging for audit purposes.
"""

import json
from fastapi import APIRouter, HTTPException, Request, Depends
from typing import Dict, Any, Optional
import structlog
from datetime import datetime

from app.services.servicenow import ServiceNowConnector
from app.exceptions.servicenow import ServiceNowError
from app.services.incident_classifier import (
    IncidentClassifierService,
    IncidentClassifierError,
    create_incident_classifier,
)
from app.models.incident import ServiceNowIncident
from app.utils.db_utils import execute_query, fetch_many, fetch_one, initialize_database, initialize_tables

# -------------------------------------------------------
# Structured logger setup
# -------------------------------------------------------
logger = structlog.get_logger(__name__)
router = APIRouter()

print(">>> webhooks_eus.py LOADED")

# -------------------------------------------------------
# Initialize database and ensure tables exist
# -------------------------------------------------------
# This runs once when the module is first imported
async def _init_db_once():
    try:
        await initialize_database()
        await initialize_tables()
        logger.info("✅ Database initialized and tables verified (webhook_events, incident_analysis)")
    except Exception as e:
        logger.error("❌ Database initialization failed", error=str(e))

# FastAPI startup event registration
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
# Database utility functions
# -------------------------------------------------------
async def store_webhook_event(incident_id, sys_id, action_type, payload, incident_data) -> str:
    try:
        payload_json = json.dumps(payload, ensure_ascii=False)
        incident_data_json = json.dumps(incident_data, ensure_ascii=False)

        result = await execute_query(
            """
            INSERT INTO webhook_events 
            (incident_id, sys_id, action_type, payload, incident_data, status)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING id
            """,
            incident_id, sys_id, action_type, payload_json, incident_data_json, "received",
        )

        # ✅ Handle possible return types safely
        if isinstance(result, (list, tuple)) and result:
            record_id = str(result[0])
        elif isinstance(result, dict) and "id" in result:
            record_id = str(result["id"])
        elif isinstance(result, str):
            record_id = result.strip("()")
        else:
            record_id = "unknown"

        logger.info("Webhook stored in DB", incident_id=incident_id, sys_id=sys_id, record_id=record_id)
        return record_id

    except Exception as e:
        logger.error("DB insert failed", incident_id=incident_id, sys_id=sys_id, error=str(e))
        raise IncidentClassifierError(f"DB storage failed: {str(e)}")



async def update_webhook_processing(record_id, status, ai_processed=False, ai_analysis_results=None, error_message=None):
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
            record_id, status, ai_processed, ai_analysis_results, error_message,
        )
        logger.info("Webhook status updated", record_id=record_id, status=status)
    except Exception as e:
        logger.error("Webhook update failed", record_id=record_id, error=str(e))


async def store_incident_analysis(webhook_event_id, incident_id, sys_id, analysis_results, ai_model_used="unknown") -> str:
    try:
        result = await execute_query(
            """
            INSERT INTO incident_analysis 
            (webhook_event_id, incident_id, sys_id, category, severity, confidence, reasoning,
             supporting_evidence, suggested_priority, recommended_actions, related_incidents, metadata, ai_model_used)
            VALUES ($1::uuid, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
            RETURNING id::text
            """,
            webhook_event_id,
            incident_id,
            sys_id,
            analysis_results.get("category"),
            analysis_results.get("severity"),
            analysis_results.get("confidence"),
            analysis_results.get("reasoning"),
            analysis_results.get("supporting_evidence"),
            analysis_results.get("suggested_priority"),
            analysis_results.get("recommended_actions"),
            analysis_results.get("related_incidents", []),
            analysis_results.get("metadata", {}),
            ai_model_used,
        )
        analysis_id = result.split("(")[1].split("::")[0].strip("'")
        logger.info("Incident analysis stored", analysis_id=analysis_id, incident_id=incident_id)
        return analysis_id
    except Exception as e:
        logger.error("Analysis storage failed", incident_id=incident_id, sys_id=sys_id, error=str(e))
        raise IncidentClassifierError(f"Analysis storage failed: {str(e)}")


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
        result = await classifier.analyze_incident(text, context)

        log_ai_decision(
            sys_id=incident.sys_id,
            incident_id=incident.number,
            decision="tier_classification",
            confidence=result.confidence,
            reasoning=result.reasoning,
            tier=result.category.value,
        )

        analysis_results = {
            "category": result.category.value,
            "severity": result.severity.value,
            "confidence": result.confidence,
            "reasoning": result.reasoning,
            "supporting_evidence": result.supporting_evidence,
            "suggested_priority": result.suggested_priority,
            "recommended_actions": result.recommended_actions,
            "predicted_tier": result.category.value,
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
# Webhook Handler (Main Endpoint)
# -------------------------------------------------------
@router.post(
    "/servicenow/incident-update",
    response_model=None,  # 👈 disables Pydantic response model validation
)
async def handle_servicenow_incident_update(
    request: Request,
    servicenow_integration: ServiceNowConnector = Depends(get_servicenow_connector),
) -> Dict[str, Any]:
    """
    Handle ServiceNow webhook for incident updates (supports both native and custom payloads).
    """
    webhook_record_id = None
    incident_id = sys_id = None

    try:
        # ✅ Step 1: Parse JSON
        payload = await request.json()

        # ✅ Step 2: Log full payload in readable format
        timestamp = datetime.utcnow().isoformat()
        print("\n🚀 === ServiceNow Incident Webhook Received ===")
        print(f"🕒 Timestamp: {timestamp}")
        print("📦 Full JSON Payload:")
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        print("==============================================\n")

        # ✅ Step 3: Handle both payload formats
        incident_data = {}
        if "result" in payload:  # Native ServiceNow webhook format
            result = payload.get("result", {})
            incident_id = result.get("number")
            sys_id = result.get("sys_id")
            incident_data = result
            print("📥 Detected ServiceNow-native payload format")
        else:  # Custom format (from manual/API test)
            incident_id = payload.get("incident_id")
            sys_id = payload.get("sys_id")
            incident_data = payload.get("incident_data", {})
            print("📥 Detected custom payload format")

        if not sys_id:
            raise HTTPException(status_code=400, detail="Missing sys_id in payload")

        # ✅ Step 4: Optional summary extraction for console clarity
        def safe_get(obj, key):
            val = obj.get(key)
            if isinstance(val, dict):
                return val.get("value", None)
            return val

        key_info = {
            "number": safe_get(incident_data, "number"),
            "short_description": safe_get(incident_data, "short_description"),
            "priority": safe_get(incident_data, "priority"),
            "state": safe_get(incident_data, "state"),
            "assignment_group": safe_get(incident_data, "assignment_group"),
            "assigned_to": safe_get(incident_data, "assigned_to"),
        }

        print("📋 === Extracted Key Fields ===")
        for k, v in key_info.items():
            print(f"{k:20}: {v}")
        print("==============================================\n")

        # ✅ Step 5: Continue with existing logic (unchanged)
        action_type = payload.get("action_type", "update")

        webhook_record_id = await store_webhook_event(
            incident_id, sys_id, action_type, payload, incident_data
        )

        incident_data["sys_id"] = sys_id
        incident = ServiceNowIncident(**incident_data)

        # ✅ Step 6: AI processing (existing logic retained)
        if action_type in ["create", "update", "reopen"]:
            await update_webhook_processing(webhook_record_id, "processing")
            analysis_results = await trigger_ai_analysis(incident, servicenow_integration)
            await store_incident_analysis(webhook_record_id, incident_id, sys_id, analysis_results)
            await update_webhook_processing(
                webhook_record_id, "completed", True, analysis_results
            )
        else:
            await update_webhook_processing(
                webhook_record_id, "skipped", False,
                error_message=f"Action {action_type} skipped"
            )

        return {"success": True, "incident_id": incident_id, "sys_id": sys_id}

    except HTTPException:
        if webhook_record_id:
            await update_webhook_processing(webhook_record_id, "error", False)
        raise
    except Exception as e:
        logger.error("Webhook processing failed", sys_id=sys_id, error=str(e))
        if webhook_record_id:
            await update_webhook_processing(webhook_record_id, "error", False, error_message=str(e))
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
# Get Incident List (Paginated + Date Filter)
# -------------------------------------------------------
from fastapi import Query
from datetime import datetime
from typing import List
@router.get("/servicenow/incidents")
async def list_incidents(
    page: int = Query(1, ge=1, description="Page number (starts at 1)"),
    page_size: int = Query(10, ge=1, le=200, description="Number of incidents per page"),
    start_date: Optional[str] = Query(None, description="Filter by start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="Filter by end date (YYYY-MM-DD)"),
) -> Dict[str, Any]:
    """
    Retrieve paginated incidents from webhook_events table with optional date filters.
    Uses fetch_one / fetch_many to avoid confusion with execute_query return types.
    """

    try:
        offset = (page - 1) * page_size
        params = []
        where_clauses = []

        # Build date filters (use ISO-like strings)
        if start_date:
            where_clauses.append(f"created_at >= ${len(params) + 1}")
            params.append(f"{start_date} 00:00:00")
        if end_date:
            where_clauses.append(f"created_at <= ${len(params) + 1}")
            params.append(f"{end_date} 23:59:59")

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        # Total count using fetch_one
        total_query = f"SELECT COUNT(*) AS total FROM webhook_events {where_sql}"
        total_row = await fetch_one(total_query, *params)
        total_count = int(total_row["total"]) if total_row and "total" in total_row else 0

        # Data query — append offset/limit params
        params_for_data = params.copy()
        params_for_data.append(offset)
        params_for_data.append(page_size)

        # Since we added two params, placeholders must be numbered accordingly
        # OFFSET is ${len(params)+1} and LIMIT ${len(params)+2}
        data_query = f"""
            SELECT
                id::text AS id,
                incident_id,
                sys_id,
                action_type,
                status,
                ai_processed,
                created_at,
                processing_completed_at,
                error_message
            FROM webhook_events
            {where_sql}
            ORDER BY created_at DESC
            OFFSET ${len(params) + 1} LIMIT ${len(params) + 2}
        """

        rows = await fetch_many(data_query, *params_for_data)

        incidents = []
        for r in rows or []:
            # fetch_many returns dicts per our db_utils implementation; normalize
            if isinstance(r, dict):
                row = r
            else:
                # fallback: tuple/list
                row = {
                    "id": str(r[0]),
                    "incident_id": r[1],
                    "sys_id": r[2],
                    "action_type": r[3],
                    "status": r[4],
                    "ai_processed": r[5],
                    "created_at": r[6].isoformat() if getattr(r[6], "isoformat", None) else r[6],
                    "processing_completed_at": r[7].isoformat() if getattr(r[7], "isoformat", None) else r[7],
                    "error_message": r[8],
                }

            # ensure datetime serializable
            if isinstance(row.get("created_at"), (str,)):
                created_at = row["created_at"]
            else:
                created_at = row["created_at"].isoformat() if row.get("created_at") else None
            row["created_at"] = created_at

            if isinstance(row.get("processing_completed_at"), (str,)):
                proc_at = row["processing_completed_at"]
            else:
                proc_at = row["processing_completed_at"].isoformat() if row.get("processing_completed_at") else None
            row["processing_completed_at"] = proc_at

            incidents.append(row)

        return {
            "page": page,
            "page_size": page_size,
            "total_records": total_count,
            "total_pages": (total_count + page_size - 1) // page_size if total_count else 0,
            "filters_applied": {"start_date": start_date, "end_date": end_date},
            "data": incidents,
        }

    except Exception as e:
        logger.error("Incident list retrieval failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to retrieve incidents: {e}")