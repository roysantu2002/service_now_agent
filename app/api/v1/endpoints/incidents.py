"""Incident processing endpoints with lazy dependency injection to avoid circular imports."""

from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, Optional
import structlog
from datetime import datetime
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from app.models.incident import (
    IncidentProcessRequest,
    IncidentProcessResponse,
    IncidentSummary
)
from app.exceptions.servicenow import ServiceNowError, ServiceNowNotFoundError


logger = structlog.get_logger(__name__)
router = APIRouter()


# -------------------------
# Lazy dependency
# -------------------------
def get_incident_processor():
    """
    Lazily import IncidentProcessor to avoid circular imports.
    """
    from app.services.incident_processor import IncidentProcessor
    return IncidentProcessor()


# -------------------------
# Endpoints
# -------------------------
@router.post("/process/{sys_id}", response_model=IncidentProcessResponse)
async def process_incident(
    sys_id: str,
    request: Optional[IncidentProcessRequest] = None,
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


@router.get("/{sys_id}/summary", response_model=IncidentSummary)
async def get_incident_summary(
    sys_id: str,
    processor=Depends(get_incident_processor)
) -> IncidentSummary:
    try:
        summary = await processor.get_incident_summary(sys_id)
        return summary
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
        incident_data = await processor.servicenow.get_incident(sys_id)
        return {"success": True, "sys_id": sys_id, "incident": incident_data.model_dump()}
    except ServiceNowNotFoundError:
        raise HTTPException(status_code=404, detail=f"Incident {sys_id} not found")
    except ServiceNowError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    
@router.post("/{sys_id}/analyze")
async def analyze_incident(
    sys_id: str,
    analysis_type: str = "general",
    processor=Depends(get_incident_processor)
):
    try:
        analysis = await processor.analyze_incident_only(sys_id, analysis_type)
        
        # ⚡ Debug print of raw AI analysis
        print(f"[DEBUG] Raw analysis result: {analysis}")

        # ✅ Convert all non-JSON serializable objects (datetime, Pydantic models, etc.)
        safe_response = jsonable_encoder(analysis)

        return JSONResponse(content=safe_response)

    except ServiceNowNotFoundError:
        raise HTTPException(status_code=404, detail=f"Incident {sys_id} not found")
    except Exception as e:
        print(f"[DEBUG] Exception during /analyze: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
@router.post("/{sys_id}/compliance-filter")
async def filter_incident_data(
    sys_id: str,
    compliance_level: str = "internal",
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
