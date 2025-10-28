# app/api/v1/endpoints/log_analyzer.py

from __future__ import annotations
import re
import os
import uuid
import json
import logging
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
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ValidationError
import aiofiles

logger = logging.getLogger(__name__)
router = APIRouter(tags=["log-analyzer"])

UPLOAD_DIR = Path(os.environ.get("LOG_UPLOAD_DIR", "data/uploads"))
PERSIST_DIR = Path(os.environ.get("LOG_ANALYSIS_PERSIST_DIR", "data/analysis_store"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
PERSIST_DIR.mkdir(parents=True, exist_ok=True)

upload_progress: Dict[str, Dict[str, Any]] = {}
analysis_tasks: Dict[str, Dict[str, Any]] = {}
analysis_results: Dict[str, Dict[str, Any]] = {}

_log_service_instance = None


# ==========================================================
# Singleton Loader
# ==========================================================

def get_log_service():
    """Return a singleton instance of LogAnalyzerService."""
    global _log_service_instance
    if _log_service_instance is None:
        from app.services.log_services import LogAnalyzerService  # type: ignore
        _log_service_instance = LogAnalyzerService()
    return _log_service_instance


# ==========================================================
# Models
# ==========================================================

class DateRangeFilter(BaseModel):
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    time_period: Optional[int] = Field(None, description="Time period in hours")


# ==========================================================
# Helpers
# ==========================================================

def persist_result_to_file(analysis_id: str, result: Dict[str, Any]):
    """Persist analysis result to disk as JSON."""
    try:
        path = PERSIST_DIR / f"{analysis_id}.json"
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(result, fh, default=str, indent=2)
        logger.info(f"✅ Result persisted to {path}")
    except Exception:
        logger.exception(f"❌ Failed to persist analysis result: {analysis_id}")


async def safe_write_file(path: Path, upload: UploadFile) -> int:
    """Save uploaded file asynchronously."""
    size = 0
    chunk_size = 1024 * 1024
    async with aiofiles.open(path, "wb") as f:
        while chunk := await upload.read(chunk_size):
            await f.write(chunk)
            size += len(chunk)
    return size


def format_validation_error(err: ValidationError) -> str:
    """Return concise, readable Pydantic validation errors."""
    messages = []
    for e in err.errors():
        loc = ".".join(str(x) for x in e.get("loc", []))
        msg = e.get("msg", "")
        messages.append(f"❌ Field `{loc}`: {msg}")
    return "\n".join(messages)


def ensure_log_analysis_shape(result: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize service output to conform to LogAnalysis schema."""
    if not isinstance(result, dict):
        result = jsonable_encoder(result)

    result.pop("file_name", None)
    result.pop("analysis_id", None)

    summary = result.get("summary", "")
    # 🩹 FIX: convert escaped newlines into actual newlines
    if isinstance(summary, str):
        summary = re.sub(r"\\n", "\n", summary).strip()

    return {
        "summary": summary,
        "observations": result.get("observations", []),
        "planning": result.get("planning", []),
        "events": result.get("events", []),
        "traffic_patterns": result.get("traffic_patterns", []),
        "highest_severity": result.get("highest_severity"),
        "requires_immediate_attention": result.get("requires_immediate_attention", False),
    }


# ==========================================================
# Background Workers
# ==========================================================

async def background_analysis_worker(
    analysis_id: str,
    file_path: str,
    date_filter: Optional[DateRangeFilter] = None
):
    """Run single-file analysis in background."""
    logger.info(f"🟡 Background worker started | analysis_id={analysis_id}")
    task = analysis_tasks.setdefault(analysis_id, {})
    try:
        task.update({"status": "processing", "progress": 10, "message": "Parsing logs"})
        service = get_log_service()

        # Perform the actual analysis
        results = await service.analyze_log_file(analysis_id, file_path, date_filter)

        if hasattr(results, "dict"):
            results = results.dict()
        elif not isinstance(results, dict):
            results = jsonable_encoder(results)

        results = ensure_log_analysis_shape(results)

        # Persist and update task
        task.update({
            "status": "completed",
            "progress": 100,
            "message": "Analysis completed",
            "results": results,
            "completed_at": datetime.utcnow().isoformat(),
        })
        analysis_results[analysis_id] = results
        persist_result_to_file(analysis_id, results)

        # Optional: Try report generation
        try:
            from app.services.report_generator import LogReportGenerator
            reporter = LogReportGenerator(output_dir=str(PERSIST_DIR))
            reporter.generate_reports(analysis_id, results)
        except Exception:
            logger.warning("Report generation failed for %s", analysis_id, exc_info=True)

        logger.info(f"✅ Background worker finished | analysis_id={analysis_id}")
    except ValidationError as ve:
        formatted = format_validation_error(ve)
        task.update({"status": "failed", "message": formatted, "progress": 0})
        logger.error(f"Validation failed for analysis {analysis_id}:\n{formatted}")
    except Exception as e:
        logger.exception("❌ Background analysis failed | analysis_id=%s", analysis_id)
        task.update({"status": "failed", "message": str(e), "progress": 0})


# ==========================================================
# Single File Analysis
# ==========================================================

@router.post("/analyze/{upload_id}")
async def analyze_log_file(
    upload_id: str,
    background_tasks: BackgroundTasks,
    date_filter: Optional[DateRangeFilter] = None,
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
    task = analysis_tasks.get(analysis_id)
    if not task or task.get("status") != "completed":
        raise HTTPException(status_code=400, detail="Analysis not completed yet")

    results = task.get("results") or analysis_results.get(analysis_id)
    if not results:
        path = PERSIST_DIR / f"{analysis_id}.json"
        if path.exists():
            with open(path, "r", encoding="utf-8") as fh:
                results = json.load(fh)
    return JSONResponse(results or {})


# ==========================================================
# Multi-File Analysis
# ==========================================================

@router.post("/analyze-multiple")
async def analyze_multiple_logs(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    provider: Optional[str] = Query(None),
):
    if not files:
        raise HTTPException(status_code=400, detail="No log files uploaded")

    request_id = str(uuid.uuid4())
    batch_folder_name = datetime.utcnow().strftime("%Y-%m-%d_%H-%M-%S")
    batch_folder = UPLOAD_DIR / batch_folder_name
    batch_folder.mkdir(parents=True, exist_ok=True)

    saved_paths = []
    for upload in files:
        dest = batch_folder / f"{request_id}_{upload.filename}"
        await safe_write_file(dest, upload)
        saved_paths.append(str(dest))

        upload_progress[str(uuid.uuid4())] = {
            "status": "completed",
            "progress": 100,
            "filename": upload.filename,
            "file_path": str(dest),
            "started_at": datetime.utcnow().isoformat(),
            "completed_at": datetime.utcnow().isoformat(),
        }

    # Initialize batch task
    analysis_tasks[request_id] = {
        "status": "queued",
        "progress": 0,
        "message": "queued",
        "files": [Path(p).name for p in saved_paths],
        "results": {},
        "started_at": datetime.utcnow().isoformat(),
    }

    async def _multi_worker(req_id: str, paths: List[str]):
        task = analysis_tasks[req_id]
        task.update({"status": "processing", "progress": 5, "message": "Analyzing files"})
        results = {}
        try:
            service = get_log_service()
            for idx, file_path in enumerate(paths):
                try:
                    file_result = await service.analyze_log_file(f"{req_id}_{idx}", file_path)
                    if hasattr(file_result, "dict"):
                        file_result = file_result.dict()
                    elif not isinstance(file_result, dict):
                        file_result = jsonable_encoder(file_result)

                    # ✅ Normalize to match LogAnalysis structure
                    file_result = ensure_log_analysis_shape(file_result)
                    results[Path(file_path).name] = file_result
                except ValidationError as ve:
                    results[Path(file_path).name] = {"error": format_validation_error(ve)}
                except Exception as ex:
                    results[Path(file_path).name] = {"error": str(ex)}

                task["progress"] = int((idx + 1) / len(paths) * 100)
                task["results"] = results

            task.update({
                "status": "completed",
                "progress": 100,
                "message": "All files analyzed",
                "results": results,
                "completed_at": datetime.utcnow().isoformat(),
            })
            analysis_results[req_id] = results
            persist_result_to_file(req_id, results)
        except Exception as ex:
            logger.exception("❌ Multi-file analysis failed | request_id=%s", req_id)
            task.update({"status": "failed", "message": str(ex), "progress": 0})

    background_tasks.add_task(_multi_worker, request_id, saved_paths)
    return JSONResponse({"request_id": request_id, "message": "multi-file analysis queued"})


@router.get("/analyze/multi-results/{request_id}")
async def get_multi_analysis_results(request_id: str) -> JSONResponse:
    task = analysis_tasks.get(request_id)
    if not task:
        path = PERSIST_DIR / f"{request_id}.json"
        if path.exists():
            with open(path, "r", encoding="utf-8") as fh:
                results = json.load(fh)
            return JSONResponse({
                "request_id": request_id,
                "status": "completed",
                "results": results
            })
        raise HTTPException(status_code=404, detail="Analysis not found")

    return JSONResponse(content=jsonable_encoder({
        "request_id": request_id,
        "status": task.get("status"),
        "message": task.get("message"),
        "progress": task.get("progress", 0),
        "files": task.get("files", []),
        "results": task.get("results", {}),
        "started_at": task.get("started_at"),
        "completed_at": task.get("completed_at"),
    }))
