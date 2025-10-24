"""
Log Analyzer API Endpoints
- File upload + progress
- Async analysis (BackgroundTasks)
- Progress & results retrieval
- Query-based log analysis (AI-assisted)
- Optional persistence and AI reasoning
"""

from __future__ import annotations

import os
import re
import uuid
import json
import logging
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

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
import aiofiles

# Local service imports
from app.services.log_services import LogAnalyzerService
from app.models.log_analyzer_models import SearchRequest, AIAnalysisRequest

logger = logging.getLogger(__name__)
router = APIRouter(tags=["log-analyzer"])

# --- Config ---
UPLOAD_DIR = Path(os.environ.get("LOG_UPLOAD_DIR", "data/uploads"))
PERSIST_DIR = Path(os.environ.get("LOG_ANALYSIS_PERSIST_DIR", "data/analysis_store"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
PERSIST_DIR.mkdir(parents=True, exist_ok=True)

# --- In-memory state ---
upload_progress: Dict[str, Dict[str, Any]] = {}
analysis_tasks: Dict[str, Dict[str, Any]] = {}
analysis_results: Dict[str, Dict[str, Any]] = {}

# Service instance
log_analyzer_service = LogAnalyzerService()

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class DateRangeFilter(BaseModel):
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    time_period: Optional[int] = Field(None, description="Time period in hours")

class AIQuestionRequest(BaseModel):
    """User-driven analysis question."""
    question: str = Field(..., example="Why are there so many authentication errors after midnight?")
    context_size: int = Field(100, description="Number of related log entries to consider")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def persist_result_to_file(analysis_id: str, result: Dict[str, Any]) -> None:
    try:
        path = PERSIST_DIR / f"{analysis_id}.json"
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(result, fh, default=str)
    except Exception:
        logger.exception("Failed to persist analysis result to disk")

async def safe_write_file(path: Path, upload: UploadFile) -> int:
    size = 0
    chunk_size = 1024 * 1024
    async with aiofiles.open(path, "wb") as f:
        while chunk := await upload.read(chunk_size):
            await f.write(chunk)
            size += len(chunk)
    return size

# ---------------------------------------------------------------------------
# Upload & Analysis
# ---------------------------------------------------------------------------

@router.post("/upload")
async def upload_log_file(file: UploadFile = File(...)) -> JSONResponse:
    upload_id = str(uuid.uuid4())
    filename = file.filename or "upload.log"
    dest = UPLOAD_DIR / f"{upload_id}_{filename}"

    upload_progress[upload_id] = {
        "status": "uploading",
        "progress": 0,
        "filename": filename,
        "file_path": str(dest),
        "started_at": datetime.utcnow().isoformat(),
    }

    try:
        size = await safe_write_file(dest, file)
        upload_progress[upload_id].update({
            "status": "completed",
            "progress": 100,
            "message": "Upload completed",
            "size_bytes": size,
            "completed_at": datetime.utcnow().isoformat(),
        })
        return JSONResponse({"upload_id": upload_id, "filename": filename, "message": "uploaded"})
    except Exception as e:
        logger.exception("Upload failed")
        upload_progress[upload_id].update({"status": "failed", "message": str(e)})
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/upload/progress/{upload_id}")
async def get_upload_progress(upload_id: str) -> JSONResponse:
    info = upload_progress.get(upload_id)
    if not info:
        raise HTTPException(status_code=404, detail="Upload not found")
    return JSONResponse(info)


# ---------------------------------------------------------------------------
# Background Worker
# ---------------------------------------------------------------------------
async def background_analysis_worker(analysis_id: str, file_path: str, date_filter: Optional[DateRangeFilter]):
    print(f"[DEBUG] 🟡 Background worker started for analysis_id={analysis_id}, file_path={file_path}")
    task = analysis_tasks[analysis_id]
    try:
        task.update({"status": "processing", "progress": 10, "message": "Parsing logs"})

        # Run actual analysis
        results = await log_analyzer_service.analyze_log_file(analysis_id, file_path, date_filter, task)

        # Save results in-memory & persist
        task.update({
            "status": "completed",
            "progress": 100,
            "message": "Analysis completed",
            "results": results,
            "completed_at": datetime.utcnow().isoformat()
        })
        analysis_results[analysis_id] = results
        persist_result_to_file(analysis_id, results)

        print(f"[DEBUG] ✅ Background worker finished for {analysis_id} with status=completed")
    except Exception as e:
        print(f"[ERROR] ❌ Background analysis failed for {analysis_id}: {e}")
        task.update({
            "status": "failed",
            "message": str(e),
            "progress": 0
        })
        logger.exception("Background analysis failed for %s: %s", analysis_id, e)
        
@router.post("/analyze/{upload_id}")
async def analyze_log_file(
    upload_id: str,
    background_tasks: BackgroundTasks,
    date_filter: Optional[DateRangeFilter] = None
) -> JSONResponse:
    upload = upload_progress.get(upload_id)
    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found")
    if upload.get("status") != "completed":
        raise HTTPException(status_code=400, detail="Upload not completed")

    file_path = upload.get("file_path")
    if not file_path or not Path(file_path).exists():
        raise HTTPException(status_code=404, detail="Uploaded file missing")

    analysis_id = str(uuid.uuid4())
    analysis_tasks[analysis_id] = {
        "status": "queued",
        "progress": 0,
        "message": "queued",
        "upload_id": upload_id,
        "started_at": datetime.utcnow().isoformat(),
    }

    background_tasks.add_task(background_analysis_worker, analysis_id, file_path, date_filter)
    return JSONResponse({"analysis_id": analysis_id, "message": "analysis started"})

@router.get("/analyze/progress/{analysis_id}")
async def get_analysis_progress(analysis_id: str) -> JSONResponse:
    task = analysis_tasks.get(analysis_id)
    if not task:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return JSONResponse(task)

@router.get("/analyze/results/{analysis_id}")
async def get_analysis_results(analysis_id: str) -> JSONResponse:
    print(f"[DEBUG] Fetching results for {analysis_id}")
    task = analysis_tasks.get(analysis_id)
    print(f"[DEBUG] Task found: {task}")
    if not task:
        raise HTTPException(status_code=404, detail="Analysis not found")
    if task.get("status") != "completed":
        print(f"[DEBUG] Task not completed yet (status={task.get('status')})")
        raise HTTPException(status_code=400, detail="Analysis not completed yet")

    results = task.get("results") or analysis_results.get(analysis_id)
    if not results:
        path = PERSIST_DIR / f"{analysis_id}.json"
        if path.exists():
            with open(path, "r", encoding="utf-8") as fh:
                results = json.load(fh)
                print(f"[DEBUG] Loaded persisted results for {analysis_id}")
    print(f"[DEBUG] Returning results for {analysis_id}")
    return JSONResponse(results or {})
# ---------------------------------------------------------------------------
# AI Question Endpoint (NEW)
# ---------------------------------------------------------------------------
@router.post("/ai/question/{analysis_id}", summary="Ask AI about a specific log analysis",
             response_description="AI-generated answer and related logs")
async def ai_question_analysis(analysis_id: str, request: AIQuestionRequest) -> JSONResponse:
    """
    Perform AI-based analysis for a user question regarding previously analyzed logs.

    - **analysis_id**: ID of the completed log analysis
    - **question**: The AI query about the logs
    - **context_size**: Number of log entries to consider for AI context

    Returns:
    - answer: AI-generated insights
    - related_logs: Relevant log entries
    - confidence: Confidence score from AI (if available)
    - timestamp: Response generation time
    """
    task = analysis_tasks.get(analysis_id)
    if not task:
        raise HTTPException(status_code=404, detail="Analysis not found")
    if task.get("status") != "completed":
        raise HTTPException(status_code=400, detail="Analysis not yet completed")

    try:
        logger.info("Performing AI question analysis for %s: %s", analysis_id, request.question)
        result = await log_analyzer_service.ai_natural_query(
            analysis_id,
            request.question,
            context_size=request.context_size
        )

        return JSONResponse({
            "analysis_id": analysis_id,
            "question": request.question,
            "answer": result.get("answer", "No insights found."),
            "related_logs": result.get("context", []),
            "confidence": result.get("confidence", None),
            "timestamp": datetime.utcnow().isoformat(),
        })
    except Exception as e:
        logger.exception("AI question analysis failed for %s: %s", analysis_id, e)
        raise HTTPException(status_code=500, detail=f"AI question analysis failed: {str(e)}")

# ---------------------------------------------------------------------------
# Cleanup & Misc
# ---------------------------------------------------------------------------

@router.delete("/cleanup/{upload_id}")
async def cleanup_upload(upload_id: str) -> JSONResponse:
    info = upload_progress.pop(upload_id, None)
    if not info:
        raise HTTPException(status_code=404, detail="Upload not found")

    file_path = info.get("file_path")
    if file_path and Path(file_path).exists():
        try:
            Path(file_path).unlink()
        except Exception:
            logger.exception("Failed to remove uploaded file %s", file_path)

    to_rm = [aid for aid, v in analysis_tasks.items() if v.get("upload_id") == upload_id]
    for aid in to_rm:
        analysis_tasks.pop(aid, None)
        analysis_results.pop(aid, None)
        p = PERSIST_DIR / f"{aid}.json"
        if p.exists():
            try:
                p.unlink()
            except Exception:
                logger.exception("Failed to remove persisted result %s", p)

    return JSONResponse({"message": "Cleanup completed"})
