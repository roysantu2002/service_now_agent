"""Incident processing endpoints with lazy dependency injection to avoid circular imports."""

import os
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Dict, Any, Optional
import structlog
from datetime import datetime
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse, JSONResponse

from app.models.incident import (
    IncidentProcessRequest,
    IncidentProcessResponse,
    IncidentSummary
)
from app.exceptions.servicenow import ServiceNowError, ServiceNowNotFoundError
from app.utils.db_utils import fetch_incident_resolutions, store_incident_resolution

logger = structlog.get_logger(__name__)
router = APIRouter()

from fastapi import Body


# -------------------------
# Lazy dependency
# -------------------------
def get_incident_processor(provider: Optional[str] = Query(None)):
    """
    Lazily import IncidentProcessor to avoid circular imports.
    Optionally allow switching AI provider at runtime.
    """
    from app.services.incident_processor import IncidentProcessor
    return IncidentProcessor(provider_name=provider)



# -------------------------
# Create Incident
# -------------------------
@router.post("/create", summary="Create a new ServiceNow incident")
async def create_incident(
    payload: Dict[str, Any] = Body(..., example={
        "short_description": "first_test_api",
        "description": "this is the first incident created via API",
        "work_notes": "Initial creation"
    }),
    provider: Optional[str] = Query(None),
    processor=Depends(get_incident_processor)
):
    """
    Create a new incident in ServiceNow using short_description, description, and work_notes.
    """
    try:
        result = await processor.servicenow.create_incident(payload)
        return {
            "success": True,
            "message": "Incident created successfully",
            "incident_sys_id": result.get("sys_id"),
            "number": result.get("number"),
            "data": result
        }
    except ServiceNowError as e:
        logger.error("Error creating incident", error=str(e))
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        logger.error("Unexpected error creating incident", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# -------------------------
# Update Incident
# -------------------------
@router.put("/{sys_id}/update", summary="Update an existing ServiceNow incident")
async def update_incident(
    sys_id: str,
    payload: Dict[str, Any] = Body(..., example={
        "short_description": "Updated short desc",
        "description": "Updated description",
        "work_notes": "Updated via API"
    }),
    provider: Optional[str] = Query(None),
    processor=Depends(get_incident_processor)
):
    """
    Update an existing incident in ServiceNow identified by sys_id.
    """
    try:
        result = await processor.servicenow.update_incident(sys_id, payload)
        return {
            "success": True,
            "message": f"Incident {sys_id} updated successfully",
            "updated_fields": payload,
            "data": result
        }
    except ServiceNowNotFoundError:
        raise HTTPException(status_code=404, detail=f"Incident {sys_id} not found")
    except ServiceNowError as e:
        logger.error("Error updating incident", sys_id=sys_id, error=str(e))
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        logger.error("Unexpected error updating incident", sys_id=sys_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# -------------------------
# Endpoints
# -------------------------
@router.post("/process/{sys_id}", response_model=IncidentProcessResponse)
async def process_incident(
    sys_id: str,
    request: Optional[IncidentProcessRequest] = None,
    provider: Optional[str] = Query(None),
    processor=Depends(get_incident_processor)
) -> IncidentProcessResponse:
    if not request:
        request = IncidentProcessRequest(sys_id=sys_id)
    else:
        request.sys_id = sys_id

    start_time = datetime.utcnow()
    try:
        result = await processor.process_incident(request)
        processing_time = (datetime.utcnow() - start_time).total_seconds()
        return IncidentProcessResponse(
            success=True,
            incident=result.get("incident"),
            ai_analysis=result.get("ai_analysis"),
            compliance_info=result.get("compliance_info"),
            processing_time=processing_time,
            message="Incident processed successfully"
        )
    except ServiceNowNotFoundError:
        raise HTTPException(status_code=404, detail=f"Incident {sys_id} not found")
    except ServiceNowError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        processing_time = (datetime.utcnow() - start_time).total_seconds()
        logger.error("Error processing incident", sys_id=sys_id, error=str(e))
        return IncidentProcessResponse(
            success=False,
            processing_time=processing_time,
            message="Failed to process incident",
            errors=[str(e)]
        )


router = APIRouter()

def parse_datetime_safe(value):
    """Gracefully parse ServiceNow datetime strings to datetime objects."""
    if not value:
        return datetime.utcnow()
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return datetime.utcnow()


@router.get("/{sys_id}/summary", response_model=IncidentSummary)
async def get_incident_summary(
    sys_id: str,
    processor=Depends(get_incident_processor)
):
    """
    Retrieve a full summary of an incident by sys_id using IncidentProcessor.
    Includes all available ServiceNow and derived fields.
    """
    try:
        # Fetch incident from ServiceNow through processor
        record = await processor.get_incident(sys_id)

        if not record:
            raise ServiceNowNotFoundError(f"Incident {sys_id} not found")

        # Convert record to dict if it's a Pydantic model
        if not isinstance(record, dict):
            record = record.dict() if hasattr(record, "dict") else record.model_dump()

        # Build complete IncidentSummary response
        data = {
            "sys_id": record.get("sys_id", sys_id),
            "number": record.get("number", f"INC-{sys_id[:6]}"),
            "title": record.get("short_description", "Untitled Incident"),
            "status": record.get("state", "New"),
            "priority": record.get("priority", "low"),
            "urgency": record.get("urgency"),
            "impact": record.get("impact"),
            "category": record.get("category"),
            "subcategory": record.get("subcategory"),
            "assigned_to": record.get("assigned_to"),
            "assignment_group": record.get("assignment_group"),
            "caller_id": record.get("caller_id"),
            "created": parse_datetime_safe(record.get("sys_created_on")),
            "updated": parse_datetime_safe(record.get("sys_updated_on")),
            "resolved_at": parse_datetime_safe(record.get("resolved_at")),
            "short_description": record.get("short_description"),
            "description": record.get("description"),
            "work_notes": record.get("work_notes"),
            "summary": record.get("summary"),
            "additional_fields": record,  # include full SNOW record for reference
        }

        # Return fully validated Pydantic model
        return IncidentSummary(**data)

    except ServiceNowNotFoundError:
        raise HTTPException(status_code=404, detail=f"Incident {sys_id} not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@router.get("/{sys_id}/details")
async def get_incident_details(
    sys_id: str,
    processor=Depends(get_incident_processor)
) -> Dict[str, Any]:
    try:
        incident_data = await processor.get_incident(sys_id)
        return {"success": True, "sys_id": sys_id, "incident": incident_data.model_dump()}
    except ServiceNowNotFoundError:
        raise HTTPException(status_code=404, detail=f"Incident {sys_id} not found")
    except ServiceNowError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# @router.post("/{sys_id}/analyze")
# async def analyze_incident(
#     sys_id: str,
#     analysis_type: str = "general",
#     provider: Optional[str] = Query(None),
#     processor=Depends(get_incident_processor)
# ):
#     try:
#         analysis = await processor.analyze_incident_only(sys_id, analysis_type)
#         safe_response = jsonable_encoder(analysis)
#         return JSONResponse(content=safe_response)
#     except ServiceNowNotFoundError:
#         raise HTTPException(status_code=404, detail=f"Incident {sys_id} not found")
#     except Exception as e:
#         logger.error("Exception during /analyze", sys_id=sys_id, error=str(e))
#         raise HTTPException(status_code=500, detail=str(e))
    
@router.post("/{sys_id}/analyze")
async def analyze_incident(
    sys_id: str,
    analysis_type: str = "general",
    provider: Optional[str] = Query(None),
    processor=Depends(get_incident_processor)
):
    try:
        # 1) Run analysis
        analysis = await processor.analyze_incident_only(sys_id, analysis_type)

        # 2) Convert models to JSON-safe primitives
        safe_response = jsonable_encoder(analysis)

        # 3) Persist into incident_resolution BEFORE returning
        try:
            record_id = await store_incident_resolution(safe_response)
            safe_response["_stored_resolution_id"] = record_id
        except Exception as e:
            logger.error(f"Failed to store incident resolution for sys_id={sys_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to store analysis: {e}")

        # 4) Return response
        return JSONResponse(content=safe_response)

    except ServiceNowNotFoundError:
        raise HTTPException(status_code=404, detail=f"Incident {sys_id} not found")
    except Exception as e:
        logger.error("Exception during /analyze", sys_id=sys_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/resolution/analysis")
async def get_resolution_analysis(limit: int = 100, offset: int = 0, sys_id: Optional[str] = None):
    try:
        data = await fetch_incident_resolutions(limit, offset, sys_id)
        return JSONResponse(content=jsonable_encoder(data))
    except Exception as e:
        logger.error(f"Failed to fetch incident resolution: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch analysis data")
    
@router.get("/download/pdf")
async def download_pdf(file_path: str):
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    filename = os.path.basename(file_path)
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="application/pdf"
    )
    
@router.post("/{sys_id}/compliance-filter")
async def filter_incident_data(
    sys_id: str,
    compliance_level: str = "internal",
    provider: Optional[str] = Query(None),
    processor=Depends(get_incident_processor)
):
    try:
        filtered = await processor.filter_incident_data_only(sys_id, compliance_level)
        return {
            "success": True,
            "sys_id": sys_id,
            "compliance_level": compliance_level,
            "filtered_data": filtered
        }
    except ServiceNowNotFoundError:
        raise HTTPException(status_code=404, detail=f"Incident {sys_id} not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{sys_id}/insights")
async def get_incident_insights(
    sys_id: str,
    analysis_type: str = "general",
    provider: Optional[str] = Query(None),
    processor=Depends(get_incident_processor)
):
    try:
        insights = await processor.analyze_incident_only(sys_id, analysis_type)
        return {"success": True, "sys_id": sys_id, "analysis_type": analysis_type, "insights": insights}
    except ServiceNowNotFoundError:
        raise HTTPException(status_code=404, detail=f"Incident {sys_id} not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{sys_id}/history")
async def get_incident_history(
    sys_id: str,
    provider: Optional[str] = Query(None),
    processor=Depends(get_incident_processor)
):
    try:
        history = await processor.get_incident_history(sys_id)
        return {"success": True, "sys_id": sys_id, "history": history, "count": len(history)}
    except ServiceNowNotFoundError:
        raise HTTPException(status_code=404, detail=f"Incident {sys_id} not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# -------------------------
# Debug print for routes
# -------------------------
print(f"[DEBUG] Final incidents router routes count: {len(router.routes)}")
for r in router.routes:
    print(f"[DEBUG] Route: {r.path} -> {r.methods}")
