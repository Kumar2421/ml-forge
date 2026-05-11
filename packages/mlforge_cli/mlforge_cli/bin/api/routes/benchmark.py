"""
api/routes/benchmark.py — Benchmark Bridge REST + WebSocket API.

Routes:
  POST /benchmark/validate          — compatibility check (no job created)
  POST /benchmark/run               — validate + create + enqueue (202)
  GET  /benchmark/jobs              — list jobs (filterable)
  GET  /benchmark/results/all       — list all results
  GET  /benchmark/{job_id}          — single job status + logs
  GET  /benchmark/{job_id}/result   — metrics + telemetry for completed job
  WS   /benchmark/live/{job_id}     — real-time progress stream
"""
from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect

import benchmark.orchestrator as orchestrator
import benchmark.registry as bench_reg
from models.benchmark import (
    BenchmarkContext,
    BenchmarkJob,
    BenchmarkResult,
    BenchmarkRunResponse,
    ValidationReport,
)
from observability.logger import get_logger

log = get_logger("api.benchmark")

router = APIRouter(prefix="/benchmark", tags=["benchmark"])


# ── POST /benchmark/validate ──────────────────────────────────────────────────

@router.post(
    "/validate",
    response_model = ValidationReport,
    summary        = "Validate model ↔ dataset compatibility",
    description    = (
        "Runs all 5 compatibility gates (task, format, framework×hardware, "
        "VRAM, precision) and returns a structured report. "
        "Does NOT create a benchmark job."
    ),
)
async def validate_benchmark(ctx: BenchmarkContext) -> ValidationReport:
    try:
        return await orchestrator.validate_context(ctx)
    except HTTPException:
        raise
    except Exception as exc:
        log.exception("validate_error")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ── POST /benchmark/run ───────────────────────────────────────────────────────

@router.post(
    "/run",
    response_model = BenchmarkRunResponse,
    status_code    = 202,
    summary        = "Start a benchmark run",
    description    = (
        "Validates compatibility, creates a benchmark job, and starts async "
        "execution. Returns job_id immediately — poll GET /benchmark/{job_id} "
        "or connect to WS /benchmark/live/{job_id} for progress."
    ),
)
async def run_benchmark(ctx: BenchmarkContext) -> BenchmarkRunResponse:
    try:
        job = await orchestrator.create_and_run(ctx)
        return BenchmarkRunResponse(
            job_id  = job.id,
            status  = job.status,
            message = f"Benchmark job {job.id} queued — connect to /benchmark/live/{job.id} for live telemetry",
        )
    except HTTPException:
        raise
    except Exception as exc:
        log.exception("run_benchmark_error")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ── POST /benchmark/sync ──────────────────────────────────────────────────────────

@router.post(
    "/sync",
    summary     = "Sync benchmarks from active project folder",
    description = "Scans the active project's 'benchmarks' folder and ensures all JSON records are indexed in SQLite.",
)
async def sync_benchmarks() -> dict[str, Any]:
    try:
        count = await orchestrator.sync_project_benchmarks()
        return {"status": "success", "count": count}
    except Exception as exc:
        log.exception("sync_error")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ── GET /benchmark/jobs ───────────────────────────────────────────────────────

@router.get(
    "/jobs",
    response_model = list[BenchmarkJob],
    summary        = "List benchmark jobs",
)
async def list_jobs(
    status:   str | None = Query(None, description="Filter by status (queued|running|completed|failed)"),
    model_id: str | None = Query(None, description="Filter by model_id"),
    limit:    int        = Query(100, ge=1, le=500),
) -> list[BenchmarkJob]:
    return await bench_reg.list_jobs(status=status, model_id=model_id, limit=limit)


# ── GET /benchmark/results/all ────────────────────────────────────────────────
# Must be declared BEFORE /{job_id} to avoid "results" being treated as a job_id

@router.get(
    "/results/all",
    response_model = list[BenchmarkResult],
    summary        = "List all benchmark results (leaderboard feed)",
)
async def list_results(
    limit: int = Query(100, ge=1, le=500),
) -> list[BenchmarkResult]:
    return await bench_reg.list_results(limit=limit)


# ── GET /benchmark/{job_id} ───────────────────────────────────────────────────

@router.get(
    "/{job_id}",
    response_model = BenchmarkJob,
    summary        = "Get benchmark job status + logs",
)
async def get_job(job_id: str) -> BenchmarkJob:
    job = await bench_reg.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    return job


# ── GET /benchmark/{job_id}/result ───────────────────────────────────────────

@router.get(
    "/{job_id}/result",
    response_model = BenchmarkResult,
    summary        = "Get final metrics + telemetry for a completed job",
)
async def get_result(job_id: str) -> BenchmarkResult:
    result = await bench_reg.get_result(job_id)
    if not result:
        raise HTTPException(
            status_code = 404,
            detail      = f"No result for job '{job_id}' — job may still be running",
        )
    return result


# ── WS /benchmark/live/{job_id} ───────────────────────────────────────────────

@router.websocket("/live/{job_id}")
async def live_telemetry(websocket: WebSocket, job_id: str) -> None:
    """
    WebSocket stream for real-time benchmark progress.
    Streams incremental logs and high-frequency telemetry.
    """
    await websocket.accept()
    log.info("ws_connected", job_id=job_id)

    last_log_idx = 0

    try:
        while True:
            job = await bench_reg.get_job(job_id)

            if not job:
                await websocket.send_json(
                    {"error": f"Job '{job_id}' not found", "job_id": job_id}
                )
                break

            # Only send new logs
            new_logs = job.logs[last_log_idx:]
            last_log_idx = len(job.logs)

            payload: dict[str, Any] = {
                "job_id":   job.id,
                "status":   job.status,
                "progress": round(job.progress, 4),
                "logs":     new_logs,
                "telemetry": job.last_telemetry.model_dump() if job.last_telemetry else None,
            }
            # Explicitly include detections for the UI visualizer if they exist
            if job.last_telemetry and hasattr(job.last_telemetry, "detections"):
                payload["detections"] = job.last_telemetry.detections
            
            await websocket.send_json(payload)

            if job.status == "completed":
                result = await bench_reg.get_result(job_id)
                if result:
                    await websocket.send_json(
                        {
                            "job_id":   job_id,
                            "status":   "completed",
                            "result":   result.model_dump(),
                        }
                    )
                break

            if job.status == "failed":
                await websocket.send_json(
                    {
                        "job_id": job_id,
                        "status": "failed",
                        "error":  job.error or "Unknown error",
                    }
                )
                break

            await asyncio.sleep(0.5)   # poll at 2 Hz

    except WebSocketDisconnect:
        log.info("ws_disconnected", job_id=job_id)
    except Exception as exc:
        log.exception("ws_error", job_id=job_id)
        try:
            await websocket.send_json({"error": str(exc), "job_id": job_id})
        except Exception:
            pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
