"""Incident processing endpoints."""
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from typing import Dict, Any, Optional
import structlog
from datetime import datetime

from app.models.incident import (
    IncidentProcessRequest,
    IncidentProcessResponse,
    IncidentSummary
)
from app.services.incident_processor import IncidentProcessor
from app.exceptions.servicenow import ServiceNowNotFoundError, ServiceNowError

logger = structlog.get_logger(__name__)
router = APIRouter()


def get_incident_processor() -> IncidentProcessor:
    """Dependency to get incident processor instance."""
    return IncidentProcessor()


@router.post("/process/{sys_id}", response_model=IncidentProcessResponse)
async def process_incident(
    sys_id: str,
    request: Optional[IncidentProcessRequest] = None,
    processor: IncidentProcessor = Depends(get_incident_processor)
) -> IncidentProcessResponse:
    """
    Process a ServiceNow incident with AI analysis and compliance filtering.
    
    Args:
        sys_id: ServiceNow incident sys_id
        request: Optional processing parameters
        
    Returns:
        Processed incident with AI analysis and compliance information
    """
    start_time = datetime.now()
    
    # Use provided request or create default
    if not request:
        request = IncidentProcessRequest(sys_id=sys_id)
    else:
        request.sys_id = sys_id  # Ensure sys_id matches path parameter
    
    logger.info("Processing incident request", 
               sys_id=sys_id,
               analysis_type=request.analysis_type,
               compliance_level=request.compliance_level)
    
    try:
        # Process the incident
        result = await processor.process_incident(request)
        
        processing_time = (datetime.now() - start_time).total_seconds()
        
        response = IncidentProcessResponse(
            success=True,
            incident=result.get('incident'),
            ai_analysis=result.get('ai_analysis'),
            compliance_info=result.get('compliance_info'),
            processing_time=processing_time,
            message="Incident processed successfully"
        )
        
        logger.info("Incident processing completed", 
                   sys_id=sys_id,
                   processing_time=processing_time)
        
        return response
        
    except ServiceNowNotFoundError:
        logger.warning("Incident not found", sys_id=sys_id)
        raise HTTPException(
            status_code=404,
            detail=f"Incident with sys_id '{sys_id}' not found"
        )
    
    except ServiceNowError as e:
        logger.error("ServiceNow error processing incident", 
                    sys_id=sys_id, error=str(e))
        raise HTTPException(
            status_code=502,
            detail=f"ServiceNow error: {str(e)}"
        )
    
    except Exception as e:
        processing_time = (datetime.now() - start_time).total_seconds()
        logger.error("Error processing incident", 
                    sys_id=sys_id, 
                    error=str(e),
                    processing_time=processing_time)
        
        return IncidentProcessResponse(
            success=False,
            processing_time=processing_time,
            message="Failed to process incident",
            errors=[str(e)]
        )


@router.get("/{sys_id}/summary", response_model=IncidentSummary)
async def get_incident_summary(
    sys_id: str,
    processor: IncidentProcessor = Depends(get_incident_processor)
) -> IncidentSummary:
    """
    Get a summary of a ServiceNow incident.
    
    Args:
        sys_id: ServiceNow incident sys_id
        
    Returns:
        Incident summary information
    """
    logger.info("Getting incident summary", sys_id=sys_id)
    
    try:
        summary = await processor.get_incident_summary(sys_id)
        
        logger.info("Incident summary retrieved", sys_id=sys_id)
        return summary
        
    except ServiceNowNotFoundError:
        logger.warning("Incident not found for summary", sys_id=sys_id)
        raise HTTPException(
            status_code=404,
            detail=f"Incident with sys_id '{sys_id}' not found"
        )
    
    except Exception as e:
        logger.error("Error getting incident summary", 
                    sys_id=sys_id, error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get incident summary: {str(e)}"
        )


@router.post("/{sys_id}/analyze")
async def analyze_incident(
    sys_id: str,
    analysis_type: str = "general",
    processor: IncidentProcessor = Depends(get_incident_processor)
) -> Dict[str, Any]:
    """
    Analyze a ServiceNow incident with AI.
    
    Args:
        sys_id: ServiceNow incident sys_id
        analysis_type: Type of analysis to perform
        
    Returns:
        AI analysis results
    """
    logger.info("Analyzing incident", sys_id=sys_id, analysis_type=analysis_type)
    
    try:
        analysis = await processor.analyze_incident_only(sys_id, analysis_type)
        
        logger.info("Incident analysis completed", sys_id=sys_id)
        return {
            "success": True,
            "sys_id": sys_id,
            "analysis_type": analysis_type,
            "analysis": analysis
        }
        
    except ServiceNowNotFoundError:
        logger.warning("Incident not found for analysis", sys_id=sys_id)
        raise HTTPException(
            status_code=404,
            detail=f"Incident with sys_id '{sys_id}' not found"
        )
    
    except Exception as e:
        logger.error("Error analyzing incident", 
                    sys_id=sys_id, error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to analyze incident: {str(e)}"
        )


@router.post("/{sys_id}/compliance-filter")
async def filter_incident_data(
    sys_id: str,
    compliance_level: str = "internal",
    processor: IncidentProcessor = Depends(get_incident_processor)
) -> Dict[str, Any]:
    """
    Apply compliance filtering to incident data.
    
    Args:
        sys_id: ServiceNow incident sys_id
        compliance_level: Target compliance level
        
    Returns:
        Filtered incident data with compliance information
    """
    logger.info("Filtering incident data", 
               sys_id=sys_id, 
               compliance_level=compliance_level)
    
    try:
        filtered_data = await processor.filter_incident_data_only(
            sys_id, compliance_level
        )
        
        logger.info("Incident data filtering completed", sys_id=sys_id)
        return {
            "success": True,
            "sys_id": sys_id,
            "compliance_level": compliance_level,
            "filtered_data": filtered_data
        }
        
    except ServiceNowNotFoundError:
        logger.warning("Incident not found for filtering", sys_id=sys_id)
        raise HTTPException(
            status_code=404,
            detail=f"Incident with sys_id '{sys_id}' not found"
        )
    
    except Exception as e:
        logger.error("Error filtering incident data", 
                    sys_id=sys_id, error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to filter incident data: {str(e)}"
        )


@router.get("/{sys_id}/history")
async def get_incident_history(
    sys_id: str,
    processor: IncidentProcessor = Depends(get_incident_processor)
) -> Dict[str, Any]:
    """
    Get incident history/audit trail.
    
    Args:
        sys_id: ServiceNow incident sys_id
        
    Returns:
        Incident history data
    """
    logger.info("Getting incident history", sys_id=sys_id)
    
    try:
        history = await processor.get_incident_history(sys_id)
        
        logger.info("Incident history retrieved", 
                   sys_id=sys_id, 
                   history_count=len(history))
        
        return {
            "success": True,
            "sys_id": sys_id,
            "history": history,
            "count": len(history)
        }
        
    except ServiceNowNotFoundError:
        logger.warning("Incident not found for history", sys_id=sys_id)
        raise HTTPException(
            status_code=404,
            detail=f"Incident with sys_id '{sys_id}' not found"
        )
    
    except Exception as e:
        logger.error("Error getting incident history", 
                    sys_id=sys_id, error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get incident history: {str(e)}"
        )
