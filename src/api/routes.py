"""
API routes for research management.
"""
from __future__ import annotations

import asyncio
import html
import json
import re
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import (
    APIRouter,
    BackgroundTasks,
    HTTPException,
    Query,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import PlainTextResponse, StreamingResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from src.config import get_settings
from src.memory.history import get_run_history
from src.models.api import (
    HealthResponse,
    JobListResponse,
    JobResult,
    JobStatus,
    ResearchRequest,
    ResearchResponse,
)
from src.models.memory import RunRecord
from src.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


# ── Input Validation Middleware ──────────────────────────────────────

# Default maximum sizes (can be overridden by config)
DEFAULT_MAX_REQUEST_BODY_SIZE = 1024 * 1024  # 1 MB
DEFAULT_MAX_QUERY_PARAM_LENGTH = 2000
DEFAULT_MAX_JSON_DEPTH = 10


def _get_validation_limits(settings) -> tuple[int, int, int]:
    """Get validation limits from settings or use defaults."""
    max_body = getattr(settings.security, "max_request_body_size", DEFAULT_MAX_REQUEST_BODY_SIZE)
    return max_body, DEFAULT_MAX_QUERY_PARAM_LENGTH, DEFAULT_MAX_JSON_DEPTH

# Patterns for injection detection
SQL_INJECTION_PATTERNS = [
    r"(?i)(\bunion\b.*\bselect\b|\bselect\b.*\bfrom\b|\binsert\b.*\binto\b|\bupdate\b.*\bset\b|\bdelete\b.*\bfrom\b|\bdrop\b.*\btable\b|\balter\b.*\btable\b|\bcreate\b.*\btable\b|\bexec\b|\bexecute\b)",
    r"(?i)(\bor\b\s+\d+\s*=\s*\d+|\band\b\s+\d+\s*=\s*\d+|'|\\'|;|--) ",
    r"(?i)(xp_cmdshell|sp_executesql|exec\s*\()",
]

XSS_PATTERNS = [
    r"(?i)(<script|<iframe|<object|<embed|<applet|<meta|<link|onload=|onerror=|onclick=|onmouseover=|onfocus=|onblur=|onchange=|onsubmit=)",
    r"(?i)(javascript:|vbscript:|data:text/html|expression\()",
    r"(?i)(<img|<svg|<body|<input|<textarea|<select|<option)",
]

PATH_TRAVERSAL_PATTERNS = [
    r"(\.\./|\.\.\\|%2e%2e%2f|%2e%2e%5c|%252e%252e%252f|%252e%252e%255c)",
    r"(/etc/passwd|/etc/shadow|/proc/|\\windows\\system32|\\windows\\win.ini)",
]

COMMAND_INJECTION_PATTERNS = [
    r"(?i)(;|&&|\|\||`|\$\(|\${|>\s*/dev/|<\s*/dev/)",
    r"(?i)(wget|curl|nc|netcat|bash|sh|zsh|powershell|cmd\.exe)\s",
]


def _sanitize_string(value: str) -> str:
    """Sanitize a string value by escaping HTML and removing control characters."""
    if not isinstance(value, str):
        return value
    # Remove control characters except newline, tab, carriage return
    value = "".join(ch for ch in value if ch == "\n" or ch == "\t" or ch == "\r" or ord(ch) >= 32)
    # HTML escape
    return html.escape(value)


def _check_injection_patterns(value: str, patterns: list[str], context: str) -> bool:
    """Check if value contains injection patterns."""
    for pattern in patterns:
        if re.search(pattern, value):
            logger.warning(f"{context} injection attempt detected", pattern=pattern, value=value[:100])
            return True
    return False


def _validate_json_depth(obj: Any, current_depth: int = 0, max_depth: int = DEFAULT_MAX_JSON_DEPTH) -> bool:
    """Validate JSON nesting depth."""
    if current_depth > max_depth:
        return False
    if isinstance(obj, dict):
        return all(_validate_json_depth(v, current_depth + 1, max_depth) for v in obj.values())
    if isinstance(obj, list):
        return all(_validate_json_depth(item, current_depth + 1, max_depth) for item in obj)
    return True


def _sanitize_json(obj: Any) -> Any:
    """Recursively sanitize JSON values."""
    if isinstance(obj, str):
        return _sanitize_string(obj)
    if isinstance(obj, dict):
        return {k: _sanitize_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_json(item) for item in obj]
    return obj


class InputValidationMiddleware(BaseHTTPMiddleware):
    """Middleware for input validation and sanitization."""

    async def dispatch(self, request: Request, call_next):
        settings = get_settings()

        # Skip validation if disabled
        if not getattr(settings.security, "input_validation_enabled", True):
            return await call_next(request)

        # Get validation limits from config
        max_body_size, max_query_param_len, max_json_depth = _get_validation_limits(settings)

        # Skip for health check and docs
        path = request.url.path
        if path in {"/api/v1/health", "/api/v1/metrics", "/docs", "/redoc", "/openapi.json"}:
            return await call_next(request)

        # Check content length
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > max_body_size:
            return JSONResponse(
                status_code=413,
                content={"error": "Payload Too Large", "detail": f"Request body exceeds {max_body_size} bytes"},
            )

        # Validate query parameters
        for key, value in request.query_params.multi_items():
            if len(value) > max_query_param_len:
                return JSONResponse(
                    status_code=400,
                    content={"error": "Bad Request", "detail": f"Query parameter '{key}' exceeds maximum length"},
                )
            # Check for injection patterns in query params
            if _check_injection_patterns(value, SQL_INJECTION_PATTERNS, "SQL"):
                return JSONResponse(status_code=400, content={"error": "Bad Request", "detail": "Invalid query parameter"})
            if _check_injection_patterns(value, XSS_PATTERNS, "XSS"):
                return JSONResponse(status_code=400, content={"error": "Bad Request", "detail": "Invalid query parameter"})
            if _check_injection_patterns(value, PATH_TRAVERSAL_PATTERNS, "Path Traversal"):
                return JSONResponse(status_code=400, content={"error": "Bad Request", "detail": "Invalid query parameter"})
            if _check_injection_patterns(value, COMMAND_INJECTION_PATTERNS, "Command Injection"):
                return JSONResponse(status_code=400, content={"error": "Bad Request", "detail": "Invalid query parameter"})

        # For JSON body requests, validate and sanitize
        if request.method in {"POST", "PUT", "PATCH"} and request.headers.get("content-type", "").startswith("application/json"):
            try:
                body = await request.body()
                if body:
                    import orjson
                    try:
                        json_data = orjson.loads(body)
                    except orjson.JSONDecodeError:
                        return JSONResponse(status_code=400, content={"error": "Bad Request", "detail": "Invalid JSON"})

                    # Validate JSON depth
                    if not _validate_json_depth(json_data, max_json_depth):
                        return JSONResponse(status_code=400, content={"error": "Bad Request", "detail": "JSON nesting too deep"})

                    # Check for injection patterns in string values
                    def check_values(obj: Any) -> bool:
                        if isinstance(obj, str):
                            if _check_injection_patterns(obj, SQL_INJECTION_PATTERNS, "SQL"):
                                return True
                            if _check_injection_patterns(obj, XSS_PATTERNS, "XSS"):
                                return True
                            if _check_injection_patterns(obj, PATH_TRAVERSAL_PATTERNS, "Path Traversal"):
                                return True
                            if _check_injection_patterns(obj, COMMAND_INJECTION_PATTERNS, "Command Injection"):
                                return True
                        elif isinstance(obj, dict):
                            return any(check_values(v) for v in obj.values())
                        elif isinstance(obj, list):
                            return any(check_values(item) for item in obj)
                        return False

                    if check_values(json_data):
                        return JSONResponse(status_code=400, content={"error": "Bad Request", "detail": "Invalid input detected"})

                    # Sanitize and store for downstream use
                    sanitized = _sanitize_json(json_data)
                    request.state.sanitized_body = sanitized
            except Exception as e:
                logger.warning(f"Input validation error: {e}")
                return JSONResponse(status_code=400, content={"error": "Bad Request", "detail": "Input validation failed"})

        response = await call_next(request)
        return response


# ── Runtime job store (in-memory status + SQLite persistence) ──────

def _get_jobs(request: Request) -> dict[str, Any]:
    return request.app.state.jobs


def _get_tasks(request: Request) -> dict[str, asyncio.Task]:
    return request.app.state.active_tasks


def _get_start_time(request: Request) -> datetime:
    return request.app.state.start_time


def _persist_job(job_id: str, updates: dict[str, Any]):
    """Persist job status to SQLite."""
    try:
        history = get_run_history()
        history.update_run(job_id, updates)
    except Exception as e:
        logger.warning(f"Failed to persist job {job_id}: {e}")


# ── Background worker ───────────────────────────────────────────────

async def _run_research_job(job_id: str, req: ResearchRequest, request: Request):
    """Execute research in background, updating job status and broadcasting."""
    from src.api.websocket_manager import get_connection_manager
    ws = get_connection_manager()
    jobs = _get_jobs(request)
    tasks = _get_tasks(request)

    try:
        from src.flows.research_flow import run_research

        jobs[job_id]["status"] = "planning"
        jobs[job_id]["updated_at"] = datetime.now(UTC)
        _persist_job(job_id, {"status": "planning", "updated_at": datetime.now(UTC)})
        await ws.broadcast_status(job_id, "planning")

        state = await asyncio.to_thread(
            run_research,
            question=req.question,
            max_iterations=req.max_iterations,
            quality_threshold=req.quality_threshold,
            tags=req.tags,
        )

        final_status = state.current_step if state.current_step != "completed" else "completed"
        jobs[job_id]["status"] = final_status
        jobs[job_id]["iteration"] = state.iteration
        jobs[job_id]["max_iterations"] = state.max_iterations
        jobs[job_id]["updated_at"] = datetime.now(UTC)
        jobs[job_id]["completed_at"] = datetime.now(UTC)

        persist_updates = {
            "status": final_status,
            "iterations": state.iteration,
            "updated_at": datetime.now(UTC),
            "completed_at": datetime.now(UTC),
        }

        if state.quality_score:
            from src.evaluation.metrics import score_to_dict
            score = score_to_dict(state.quality_score)
            jobs[job_id]["quality_score"] = score
            persist_updates["quality_score"] = score

        findings = state.get_all_findings() if hasattr(state, 'get_all_findings') else []
        jobs[job_id]["findings_count"] = len(findings)

        report_path = get_settings().storage.output_dir / f"{state.run_id}.md"
        if report_path.exists():
            jobs[job_id]["report_path"] = str(report_path)
            persist_updates["final_report_id"] = state.run_id

        _persist_job(job_id, persist_updates)

        if state.quality_score:
            await ws.broadcast_quality(job_id, score, state.iteration)
        await ws.broadcast_complete(job_id, str(report_path) if report_path.exists() else None)

    except asyncio.CancelledError:
        logger.info(f"Job {job_id} cancelled via asyncio")
        jobs[job_id]["status"] = "cancelled"
        jobs[job_id]["error"] = "Job cancelled by user"
        jobs[job_id]["updated_at"] = datetime.now(UTC)
        _persist_job(job_id, {"status": "cancelled", "error": "Job cancelled by user"})
        await ws.broadcast_status(job_id, "cancelled")

    except Exception as e:
        logger.error(f"Job {job_id} failed: {e}")
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["error"] = str(e)
        jobs[job_id]["updated_at"] = datetime.now(UTC)
        _persist_job(job_id, {"status": "failed", "error": str(e)})
        await ws.broadcast_error(job_id, str(e))

    finally:
        tasks.pop(job_id, None)


# ── REST Endpoints ──────────────────────────────────────────────────

@router.post("/research", response_model=ResearchResponse, status_code=202)
async def start_research(req: ResearchRequest, background_tasks: BackgroundTasks, request: Request):
    """Start a new research job."""
    job_id = f"job_{str(uuid4())[:8]}"
    jobs = _get_jobs(request)

    jobs[job_id] = {
        "job_id": job_id,
        "question": req.question,
        "status": "queued",
        "iteration": 0,
        "max_iterations": req.max_iterations or 3,
        "started_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
        "tags": req.tags,
    }

    # Persist to SQLite
    try:
        history = get_run_history()
        history.create_run(RunRecord(
            id=job_id,
            question=req.question,
            status="queued",
            tags=req.tags,
        ))
    except Exception as e:
        logger.warning(f"Failed to persist new job: {e}")

    # Schedule as asyncio task (cancellable)
    loop = asyncio.get_event_loop()
    task = loop.create_task(_run_research_job(job_id, req, request))
    _get_tasks(request)[job_id] = task

    logger.info(f"Research job {job_id} queued: {req.question[:60]}...")

    return ResearchResponse(
        job_id=job_id,
        status="queued",
        message=f"Research job {job_id} queued",
    )


@router.get("/research/{job_id}", response_model=JobStatus)
async def get_job_status(job_id: str, request: Request):
    """Get the status of a research job."""
    # Check in-memory first (live data)
    jobs = _get_jobs(request)
    job = jobs.get(job_id)

    # Fall back to SQLite
    if not job:
        try:
            history = get_run_history()
            record = history.get_run(job_id)
            if record:
                job = {
                    "job_id": record.id,
                    "question": record.question,
                    "status": record.status,
                    "iteration": record.iterations,
                    "max_iterations": 3,
                    "quality_score": record.quality_score,
                    "error": record.error,
                    "started_at": record.created_at,
                    "updated_at": record.created_at,
                    "completed_at": record.completed_at,
                    "tags": record.tags,
                }
        except Exception as e:
            logger.warning(f"SQLite history lookup failed for {job_id}: {e}")

    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    tu = job.get("token_usage", {})
    return JobStatus(
        job_id=job["job_id"],
        question=job["question"],
        status=job["status"],
        current_step=job["status"],
        iteration=job.get("iteration", 0),
        max_iterations=job.get("max_iterations", 3),
        quality_score=job.get("quality_score"),
        error=job.get("error"),
        started_at=job["started_at"],
        updated_at=job.get("updated_at", job["started_at"]),
        completed_at=job.get("completed_at"),
        tags=job.get("tags", []),
        token_usage=tu if isinstance(tu, dict) else {},
        cost_estimate=tu.get("cost_estimate", 0) if isinstance(tu, dict) else 0,
    )


@router.get("/research/{job_id}/result", response_model=JobResult)
async def get_job_result(job_id: str, request: Request):
    """Get the final result of a completed job."""
    jobs = _get_jobs(request)
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    if job["status"] not in ("completed", "failed"):
        raise HTTPException(status_code=400, detail=f"Job {job_id} is {job['status']}, not completed")

    # Get markdown report
    report_markdown = None
    report_path = job.get("report_path")
    if report_path and Path(report_path).exists():
        report_markdown = Path(report_path).read_text(encoding="utf-8")

    # Get structured report data from JSON file
    structured_data = {
        "key_takeaways": [],
        "references": [],
        "sections": [],
        "executive_summary": "",
    }
    json_path = Path(report_path).with_suffix('.json') if report_path else None
    if json_path and Path(json_path).exists():
        try:
            structured_data = json.loads(json_path.read_text(encoding="utf-8"))
        except Exception:
            logger.debug(f"Failed to parse JSON at {json_path}")

    return JobResult(
        job_id=job_id,
        question=job["question"],
        report_markdown=report_markdown,
        report=structured_data,
        quality_score=job.get("quality_score"),
        token_usage=job.get("token_usage", {}),
        duration_seconds=(job.get("completed_at", datetime.now(UTC)) - job["started_at"]).total_seconds(),
        iterations=job.get("iteration", 0),
        created_at=job["started_at"],
        completed_at=job.get("completed_at", datetime.now(UTC)),
        key_takeaways=structured_data.get("key_takeaways", []),
        references=structured_data.get("references", []),
        sections=structured_data.get("sections", []),
        executive_summary=structured_data.get("executive_summary", ""),
    )


@router.get("/research/{job_id}/report", response_class=PlainTextResponse)
async def get_report_markdown(job_id: str, request: Request):
    """Get the markdown report for a completed job."""
    jobs = _get_jobs(request)
    job = jobs.get(job_id)

    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    report_path = job.get("report_path")
    if not report_path or not Path(report_path).exists():
        raise HTTPException(status_code=404, detail="Report not found")

    return Path(report_path).read_text(encoding="utf-8")


@router.get("/research", response_model=JobListResponse)
async def list_jobs(
    request: Request,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    status: str | None = Query(default=None),
):
    """List all research jobs (in-memory + SQLite)."""
    jobs = _get_jobs(request)
    all_jobs = list(jobs.values())

    # Fall back to SQLite for persisted jobs not in memory
    try:
        history = get_run_history()
        limit_sql = max(limit, 50)
        db_runs = history.list_runs(status=status, limit=limit_sql, offset=0)
        db_ids = {j.get("job_id") for j in all_jobs}
        for run in db_runs:
            if run.id not in db_ids:
                all_jobs.append({
                    "job_id": run.id,
                    "question": run.question,
                    "status": run.status,
                    "iteration": run.iterations,
                    "max_iterations": 3,
                    "quality_score": run.quality_score,
                    "error": run.error,
                    "started_at": run.created_at,
                    "updated_at": run.created_at,
                    "completed_at": run.completed_at,
                    "tags": run.tags,
                })
    except Exception as e:
        logger.warning(f"SQLite history enumeration failed: {e}")

    if status:
        all_jobs = [j for j in all_jobs if j["status"] == status]

    all_jobs.sort(key=lambda j: j["started_at"], reverse=True)
    page = all_jobs[offset:offset + limit]

    return JobListResponse(
        jobs=[JobStatus(
            job_id=j["job_id"],
            question=j["question"],
            status=j["status"],
            current_step=j["status"],
            iteration=j.get("iteration", 0),
            max_iterations=j.get("max_iterations", 3),
            quality_score=j.get("quality_score"),
            error=j.get("error"),
            started_at=j["started_at"],
            updated_at=j.get("updated_at", j["started_at"]),
            completed_at=j.get("completed_at"),
            tags=j.get("tags", []),
            token_usage=j.get("token_usage", {}),
            cost_estimate=j.get("token_usage", {}).get("cost_estimate", 0) if isinstance(j.get("token_usage"), dict) else 0,
        ) for j in page],
        total=len(all_jobs),
        page=(offset // limit) + 1 if limit else 1,
        page_size=limit,
    )


def _check_sqlite() -> str:
    try:
        from src.memory.history import get_run_history
        get_run_history().get_stats()
        return "healthy"
    except Exception:
        return "unhealthy"


def _check_chromadb() -> str:
    try:
        from chromadb import HttpClient

        from src.config import get_settings
        settings = get_settings()
        if settings.storage.chroma_host:
            client = HttpClient(host=settings.storage.chroma_host, port=settings.storage.chroma_port or 8000)
            client.heartbeat()
            return "healthy"
        return "unhealthy"
    except Exception:
        return "unhealthy"


def _check_neo4j() -> str:
    try:
        from neo4j import GraphDatabase

        from src.config import get_settings
        settings = get_settings()
        if settings.storage.neo4j_uri:
            driver = GraphDatabase.driver(
                settings.storage.neo4j_uri,
                auth=(settings.storage.neo4j_user or "neo4j", settings.storage.neo4j_password or ""),
                connection_timeout=2,
            )
            driver.verify_connectivity()
            driver.close()
            return "healthy"
        return "unhealthy"
    except Exception:
        return "unhealthy"


def _check_redis() -> str:
    try:
        from redis import Redis
        from urllib.parse import urlparse

        from src.config import get_settings
        settings = get_settings()
        url = getattr(settings, "celery_broker_url", None)
        if url:
            parsed = urlparse(url)
            host = parsed.hostname or "localhost"
            port = parsed.port or 6379
            r = Redis(host=host, port=port, socket_connect_timeout=2)
            r.ping()
            r.close()
            return "healthy"
        return "unhealthy"
    except Exception as e:
        logger.warning(f"Redis health check failed: {e}")
        return "unhealthy"


@router.get("/health", response_model=HealthResponse)
async def health_check(request: Request):
    """Health check endpoint with backend service status."""
    start_time = _get_start_time(request)
    uptime = (datetime.now(UTC) - start_time).total_seconds()
    from src.api.websocket_manager import get_connection_manager
    ws_count = get_connection_manager().connected_count()

    async def _safe_check(check_fn, timeout=3):
        try:
            return await asyncio.wait_for(asyncio.to_thread(check_fn), timeout=timeout)
        except (TimeoutError, Exception):
            return "unhealthy"

    sqlite_status = await _safe_check(_check_sqlite, 3)
    chroma_status = await _safe_check(_check_chromadb, 3)
    neo4j_status = await _safe_check(_check_neo4j, 3)
    redis_status = await _safe_check(_check_redis, 3)

    services = {
        "websocket": "healthy",
        "sqlite": sqlite_status,
        "chromadb": chroma_status,
        "neo4j": neo4j_status,
        "redis": redis_status,
    }
    status = "healthy" if all(v == "healthy" for v in services.values()) else "degraded"
    return HealthResponse(
        status=status,
        uptime_seconds=uptime,
        services=services,
    )


@router.delete("/research/{job_id}")
async def cancel_job(job_id: str, request: Request):
    """Cancel a running research job."""
    jobs = _get_jobs(request)
    tasks = _get_tasks(request)

    if job_id not in jobs:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    if jobs[job_id]["status"] in ("completed", "failed", "cancelled"):
        raise HTTPException(
            status_code=400,
            detail=f"Job {job_id} already {jobs[job_id]['status']}",
        )

    # Cancel the asyncio task if running
    task = tasks.get(job_id)
    if task and not task.done():
        task.cancel()
        logger.info(f"Cancelled asyncio task for job {job_id}")

    jobs[job_id]["status"] = "cancelled"
    jobs[job_id]["error"] = "Cancelled by user"
    jobs[job_id]["updated_at"] = datetime.now(UTC)
    _persist_job(job_id, {"status": "cancelled", "error": "Cancelled by user"})

    # Broadcast cancellation
    from src.api.websocket_manager import get_connection_manager
    await get_connection_manager().broadcast_status(job_id, "cancelled")

    return {"message": f"Job {job_id} cancelled"}


# ── WebSocket Endpoint ──────────────────────────────────────────────

@router.websocket("/ws/research/{job_id}")
async def websocket_research(websocket: WebSocket, job_id: str):
    """WebSocket endpoint for real-time job updates."""
    from src.api.websocket_manager import get_connection_manager
    ws = get_connection_manager()
    await ws.connect(websocket, job_id)
    try:
        while True:
            # Keep connection alive, handle client pings
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text(json.dumps({"event": "pong", "job_id": job_id}))
    except WebSocketDisconnect:
        await ws.disconnect(websocket, job_id)
    except Exception:
        await ws.disconnect(websocket, job_id)


# ── SSE Streaming Endpoint ──────────────────────────────────────────

@router.get("/research/{job_id}/stream")
async def stream_research(job_id: str, request: Request):
    """Server-Sent Events stream for job updates."""

    async def event_generator() -> AsyncGenerator[str, None]:
        from src.api.websocket_manager import get_connection_manager
        ws = get_connection_manager()
        last_status = None

        while True:
            await asyncio.sleep(1)
            jobs = _get_jobs(request)
            job = jobs.get(job_id)
            if not job:
                yield f"event: error\ndata: {json.dumps({'message': 'Job not found'})}\n\n"
                break

            current_status = job.get("status")
            if current_status != last_status:
                last_status = current_status
                data = {
                    "status": current_status,
                    "iteration": job.get("iteration", 0),
                    "quality_score": job.get("quality_score"),
                    "error": job.get("error"),
                }
                yield f"event: {current_status}\ndata: {json.dumps(data)}\n\n"

            if current_status in ("completed", "failed", "cancelled"):
                yield f"event: done\ndata: {json.dumps(data)}\n\n"
                break

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
