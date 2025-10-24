"""
Log Analyzer API Endpoints
--------------------------
Handles:
- File uploads with progress tracking
- Async log analysis with progress
- AI-powered log insights (errors, patterns, security)
- Natural-language search and compliance reporting
"""

from fastapi import (
    APIRouter,
    UploadFile,
    File,
    HTTPException,
    BackgroundTasks,
    Query,
)
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from pathlib import Path
import aiofiles
import asyncio
import uuid
import os
import logging

# --- Local imports ---
from app.services.log_analyzer_service import LogAnalyzerService
from app.models.log_analyzer_models import (
    SearchRequest,
    AIAnalysisRequest,
)

# ---------------------------------------------------------------------------
# Router and globals
# ---------------------------------------------------------------------------

router = APIRouter(tags=["log-analyzer"])
logger = logging.getLogger(__name__)

UPLOAD_DIR = Path("data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

upload_progress: dict[str, dict] = {}
analysis_tasks: dict[str, dict] = {}

log_analyzer_service = LogAnalyzerService()
analysis_results: dict[str, dict] = {}

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class DateRangeFilter(BaseModel):
    start_date: datetime
    end_date: datetime
    time_period: Optional[int] = Field(None, description="Time period in hours (6, 12, 24)")


# ---------------------------------------------------------------------------
# Upload Endpoints
# ---------------------------------------------------------------------------

@router.post("/upload")
async def upload_log_file(file: UploadFile = File(...)):
    """
    Upload a log file with progress tracking.
    Returns a unique upload_id.
    """
    upload_id = str(uuid.uuid4())
    file_path = UPLOAD_DIR / f"{upload_id}_{file.filename}"

    upload_progress[upload_id] = {
        "status": "uploading",
        "progress": 0,
        "filename": file.filename,
        "file_path": str(file_path),
        "started_at": datetime.utcnow().isoformat(),
    }

    try:
        size = 0
        async with aiofiles.open(file_path, "wb") as f:
            chunk_size = 1024 * 1024  # 1MB
            while chunk := await file.read(chunk_size):
                await f.write(chunk)
                size += len(chunk)
                upload_progress[upload_id]["progress"] = min(95, size // 1_000_000)  # Approximation

        upload_progress[upload_id].update({
            "status": "completed",
            "progress": 100,
            "message": "Upload completed successfully",
            "completed_at": datetime.utcnow().isoformat(),
        })
        return JSONResponse({
            "upload_id": upload_id,
            "filename": file.filename,
            "message": "File uploaded successfully"
        })

    except Exception as e:
        logger.exception("Upload failed")
        upload_progress[upload_id].update({
            "status": "failed",
            "message": str(e),
        })
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.get("/upload/progress/{upload_id}")
async def get_upload_progress(upload_id: str):
    """
    Get upload progress by ID
    """
    info = upload_progress.get(upload_id)
    if not info:
        raise HTTPException(status_code=404, detail="Upload not found")
    return JSONResponse(info)


# ---------------------------------------------------------------------------
# Analysis Endpoints
# ---------------------------------------------------------------------------

@router.post("/analyze/{upload_id}")
async def analyze_log_file(
    upload_id: str,
    date_filter: Optional[DateRangeFilter] = None,
):
    """
    Start async log analysis for uploaded file.
    Returns analysis_id immediately so frontend can poll progress.
    """
    if upload_id not in upload_progress:
        raise HTTPException(status_code=404, detail="Upload not found")

    info = upload_progress[upload_id]
    if info["status"] != "completed":
        raise HTTPException(status_code=400, detail="Upload not completed")

    file_path = info["file_path"]
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Log file not found")

    analysis_id = str(uuid.uuid4())
    analysis_tasks[analysis_id] = {
        "status": "queued",
        "progress": 0,
        "message": "Analysis queued...",
        "upload_id": upload_id,
        "started_at": datetime.utcnow().isoformat(),
    }

    async def run_analysis():
        try:
            analysis_tasks[analysis_id].update({
                "status": "processing",
                "message": "Analyzing logs..."
            })
            results = await log_analyzer_service.analyze_log_file(
                analysis_id, file_path, date_filter, analysis_tasks
            )
            analysis_tasks[analysis_id].update({
                "status": "completed",
                "progress": 100,
                "message": "Analysis completed successfully",
                "results": results,
                "completed_at": datetime.utcnow().isoformat(),
            })
        except Exception as e:
            logger.exception("Analysis failed")
            analysis_tasks[analysis_id].update({
                "status": "failed",
                "message": str(e),
            })

    asyncio.create_task(run_analysis())

    return JSONResponse({
        "analysis_id": analysis_id,
        "upload_id": upload_id,
        "message": "Analysis started successfully"
    })


@router.get("/analyze/progress/{analysis_id}")
async def get_analysis_progress(analysis_id: str):
    """
    Get current analysis progress
    """
    task = analysis_tasks.get(analysis_id)
    if not task:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return JSONResponse(task)


async def run_analysis(analysis_id: str, file_path: str, date_filter: Optional[DateRangeFilter]):
    """Run log analysis in background."""
    try:
        analysis_tasks[analysis_id].update({
            "status": "processing",
            "message": "Analyzing logs...",
            "progress": 10,
        })

        # Read and parse log file
        async with aiofiles.open(file_path, "r") as f:
            content = await f.read()

        # Parse logs
        logs = parse_logs(content)

        # Filter by date range if provided
        if date_filter and date_filter.start_date and date_filter.end_date:
            start = datetime.fromisoformat(date_filter.start_date)
            end = datetime.fromisoformat(date_filter.end_date)
            logs = [log for log in logs if start <= log.get("timestamp", datetime.min) <= end]

        analysis_tasks[analysis_id]["progress"] = 50

        # Analyze logs
        results = analyze_logs(logs)

        analysis_tasks[analysis_id].update({
            "status": "completed",
            "progress": 100,
            "message": "Analysis completed successfully",
            "results": results,
            "completed_at": datetime.utcnow().isoformat(),
        })

        # Store results separately for easy retrieval
        analysis_results[analysis_id] = results

    except Exception as e:
        logger.exception("Analysis failed")
        analysis_tasks[analysis_id].update({
            "status": "failed",
            "message": str(e),
        })


def parse_logs(content: str) -> list[dict]:
    """Parse log file content into structured logs."""
    logs = []
    lines = content.split("\n")

    # Regex patterns for common log formats
    iso_pattern = r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})"
    level_pattern = r"\b(DEBUG|INFO|WARNING|ERROR|CRITICAL)\b"

    for line_num, line in enumerate(lines, 1):
        if not line.strip():
            continue

        log_entry = {
            "line_number": line_num,
            "message": line,
            "level": "INFO",
            "category": "General",
            "severity_score": 1,
        }

        # Extract timestamp
        timestamp_match = re.search(iso_pattern, line)
        if timestamp_match:
            try:
                log_entry["timestamp"] = datetime.fromisoformat(timestamp_match.group(1))
            except:
                log_entry["timestamp"] = datetime.now()

        # Extract log level
        level_match = re.search(level_pattern, line)
        if level_match:
            log_entry["level"] = level_match.group(1)
            severity_map = {"DEBUG": 1, "INFO": 1, "WARNING": 2, "ERROR": 3, "CRITICAL": 4}
            log_entry["severity_score"] = severity_map.get(log_entry["level"], 1)

        # Categorize log
        if "database" in line.lower() or "db" in line.lower():
            log_entry["category"] = "Database"
        elif "auth" in line.lower() or "login" in line.lower():
            log_entry["category"] = "Authentication"
        elif "api" in line.lower() or "request" in line.lower():
            log_entry["category"] = "API"
        elif "error" in line.lower() or "exception" in line.lower():
            log_entry["category"] = "Error"

        logs.append(log_entry)

    return logs


def analyze_logs(logs: list[dict]) -> dict:
    """Analyze parsed logs and generate statistics."""
    if not logs:
        return {
            "summary": {
                "total_entries": 0,
                "error_count": 0,
                "error_rate": 0,
                "critical_errors": 0,
                "average_severity": 0,
                "compliance_status": "UNKNOWN",
                "compliance_risk_score": 0,
            },
            "statistics": {
                "level_distribution": {},
                "category_distribution": {},
                "hourly_distribution": {},
            },
            "top_errors": [],
        }

    # Calculate statistics
    total_entries = len(logs)
    error_logs = [log for log in logs if log["level"] in ["ERROR", "CRITICAL"]]
    error_count = len(error_logs)
    error_rate = (error_count / total_entries * 100) if total_entries > 0 else 0
    critical_errors = len([log for log in logs if log["level"] == "CRITICAL"])
    average_severity = sum(log["severity_score"] for log in logs) / total_entries if total_entries > 0 else 0

    # Level distribution
    level_distribution = {}
    for log in logs:
        level = log["level"]
        level_distribution[level] = level_distribution.get(level, 0) + 1

    # Category distribution
    category_distribution = {}
    for log in logs:
        category = log["category"]
        category_distribution[category] = category_distribution.get(category, 0) + 1

    # Hourly distribution
    hourly_distribution = {}
    for log in logs:
        if "timestamp" in log:
            hour = log["timestamp"].hour
            hourly_distribution[str(hour)] = hourly_distribution.get(str(hour), 0) + 1

    # Top errors
    error_messages = {}
    for log in error_logs:
        msg = log["message"][:100]
        if msg not in error_messages:
            error_messages[msg] = {
                "message": msg,
                "category": log["category"],
                "severity": log["severity_score"],
                "count": 0,
                "first_occurrence": log["line_number"],
                "last_occurrence": log["line_number"],
            }
        error_messages[msg]["count"] += 1
        error_messages[msg]["last_occurrence"] = log["line_number"]

    top_errors = sorted(error_messages.values(), key=lambda x: x["count"], reverse=True)[:10]

    # Determine compliance status
    if error_rate > 10:
        compliance_status = "HIGH_RISK"
        compliance_risk_score = 75
    elif error_rate > 5:
        compliance_status = "MEDIUM_RISK"
        compliance_risk_score = 50
    else:
        compliance_status = "LOW_RISK"
        compliance_risk_score = 25

    return {
        "summary": {
            "total_entries": total_entries,
            "error_count": error_count,
            "error_rate": round(error_rate, 2),
            "critical_errors": critical_errors,
            "average_severity": round(average_severity, 2),
            "compliance_status": compliance_status,
            "compliance_risk_score": compliance_risk_score,
        },
        "statistics": {
            "level_distribution": level_distribution,
            "category_distribution": category_distribution,
            "hourly_distribution": hourly_distribution,
        },
        "top_errors": top_errors,
    }


@router.get("/api/v1/log-analyzer/analyze/results/{analysis_id}")
async def get_analysis_results(analysis_id: str):
    """Get full analysis results."""
    task = analysis_tasks.get(analysis_id)
    if not task:
        raise HTTPException(status_code=404, detail="Analysis not found")
    if task["status"] != "completed":
        raise HTTPException(status_code=400, detail="Analysis not completed yet")
    results = task.get("results", {})
    if not results:
        results = analysis_results.get(analysis_id, {})
    return JSONResponse(results)

# ---------------------------------------------------------------------------
# Search and AI Intelligence
# ---------------------------------------------------------------------------

@router.post("/search/{analysis_id}")
async def search_logs(analysis_id: str, request: SearchRequest):
    """
    Search within analyzed logs (RAG-powered)
    """
    task = analysis_tasks.get(analysis_id)
    if not task or task["status"] != "completed":
        raise HTTPException(status_code=404, detail="Completed analysis not found")

    try:
        results = await log_analyzer_service.search_logs(
            analysis_id, request.query, request.search_type, request.max_results
        )
        return JSONResponse(results)
    except Exception as e:
        logger.exception("Search failed")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.post("/ai/analyze-error/{analysis_id}")
async def ai_analyze_error(analysis_id: str, request: AIAnalysisRequest):
    """
    AI-powered error root cause analysis
    """
    if analysis_id not in analysis_tasks:
        raise HTTPException(status_code=404, detail="Analysis not found")
    try:
        result = await log_analyzer_service.ai_analyze_error(analysis_id, request.error_message)
        return JSONResponse(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI error analysis failed: {str(e)}")


@router.post("/ai/analyze-patterns/{analysis_id}")
async def ai_analyze_patterns(analysis_id: str):
    """
    AI pattern detection in logs
    """
    if analysis_id not in analysis_tasks:
        raise HTTPException(status_code=404, detail="Analysis not found")
    try:
        result = await log_analyzer_service.ai_analyze_patterns(analysis_id)
        return JSONResponse(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pattern analysis failed: {str(e)}")


@router.post("/ai/security-analysis/{analysis_id}")
async def ai_security_analysis(analysis_id: str):
    """
    AI security threat detection
    """
    if analysis_id not in analysis_tasks:
        raise HTTPException(status_code=404, detail="Analysis not found")
    try:
        result = await log_analyzer_service.ai_security_analysis(analysis_id)
        return JSONResponse(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Security analysis failed: {str(e)}")


@router.post("/ai/natural-query/{analysis_id}")
async def ai_natural_query(
    analysis_id: str,
    query: str = Query(..., description="Ask a natural language question about the logs"),
):
    """
    Natural language query over analyzed logs
    """
    if analysis_id not in analysis_tasks:
        raise HTTPException(status_code=404, detail="Analysis not found")
    try:
        result = await log_analyzer_service.ai_natural_query(analysis_id, query)
        return JSONResponse(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")


# ---------------------------------------------------------------------------
# Compliance & Cleanup
# ---------------------------------------------------------------------------

@router.get("/compliance/report/{analysis_id}")
async def get_compliance_report(analysis_id: str):
    """
    Generate AI-based compliance report
    """
    if analysis_id not in analysis_tasks:
        raise HTTPException(status_code=404, detail="Analysis not found")
    try:
        result = await log_analyzer_service.generate_compliance_report(analysis_id)
        return JSONResponse(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Report generation failed: {str(e)}")


@router.delete("/cleanup/{upload_id}")
async def cleanup_upload(upload_id: str):
    """
    Remove uploaded file and cached data
    """
    info = upload_progress.pop(upload_id, None)
    if not info:
        raise HTTPException(status_code=404, detail="Upload not found")

    file_path = info.get("file_path")
    if file_path and os.path.exists(file_path):
        os.remove(file_path)

    # Remove associated analysis tasks
    to_remove = [aid for aid, v in analysis_tasks.items() if v.get("upload_id") == upload_id]
    for aid in to_remove:
        del analysis_tasks[aid]

    return JSONResponse({"message": "Cleanup completed successfully"})
