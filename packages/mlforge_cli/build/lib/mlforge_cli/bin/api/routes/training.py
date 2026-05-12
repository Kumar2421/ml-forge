"""
api/routes/training.py — Training Engine REST + SSE endpoints.

POST /train/start                    — create and launch a training run
POST /train/stop                     — cancel a running run
POST /train/pause                    — pause a running run
POST /train/resume                   — resume a paused run
GET  /train/status                   — run status + progress snapshot
GET  /train/runs                     — list all runs
GET  /train/runs/{run_id}            — single run detail
GET  /train/schema                   — UI schema for task/model/dataset combo
GET  /train/checkpoints              — checkpoints for a run  (stub)
POST /train/checkpoints/{id}/export  — export a checkpoint   (stub)
GET  /train/metrics/stream           — SSE: real-time metrics ticks
GET  /train/logs/stream              — SSE: real-time log entries
GET  /train/resources/stream         — SSE: real-time resource ticks
"""
from __future__ import annotations

import asyncio
import json
import time
import os

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from observability.logger import get_logger
from training import run_manager
from training.schema_engine import generate_schema
from training.schemas import (
    CheckpointOut,
    PauseTrainRequest,
    ResumeTrainRequest,
    StartTrainRequest,
    StartTrainResponse,
    StopTrainRequest,
    TrainRunOut,
    TrainStatusResponse,
    TrainingSchemaResponse,
)

log = get_logger("api.training")
router = APIRouter(prefix="/train", tags=["training"])

# ── Helpers ────────────────────────────────────────────────────────────────────

def _format_duration(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h}h {m}m {s}s"


def _run_to_out(run: run_manager.TrainRun) -> TrainRunOut:
    elapsed = (run.completed_at or time.time()) - run.created_at
    return TrainRunOut(
        id=run.run_id,
        run_number=run.run_number,
        model_id=run.model_id,
        model_name=run.model_name,
        dataset_id=run.dataset_id,
        dataset_name=run.dataset_name,
        task=run.task,
        status=run.status,
        epochs_done=run.epoch,
        total_epochs=run.total_epochs,
        best_metric=run.best_metric,
        final_loss=run.final_loss,
        duration=_format_duration(elapsed),
        created_at=run.created_at,
        completed_at=run.completed_at,
        hyperparams=run.hyperparams,
    )


# ── Control endpoints ─────────────────────────────────────────────────────────

@router.post("/start", response_model=StartTrainResponse)
async def start_training(body: StartTrainRequest) -> StartTrainResponse:
    """Create and immediately launch a training run."""
    # Resolve friendly names (fall back to ids if registries unavailable)
    model_name   = body.model_id
    dataset_name = body.dataset_id
    try:
        from registry.registry import get_model
        m = await get_model(body.model_id)
        if m:
            model_name = m.name
    except Exception:
        pass
    try:
        from datasets.registry import get_dataset
        d = await get_dataset(body.dataset_id)
        if d:
            dataset_name = d.get("name", body.dataset_id) if isinstance(d, dict) else getattr(d, "name", body.dataset_id)
    except Exception:
        pass

    run = run_manager.create_run(
        model_id=body.model_id,
        model_name=model_name,
        dataset_id=body.dataset_id,
        dataset_name=dataset_name,
        task=body.task,
        hyperparams=body.hyperparams,
        augmentation=body.augmentation,
        scheduler=body.scheduler,
        project_id=body.project_id
    )
    run_manager.start_run(run)

    log.info("training_started", run_id=run.run_id, model=body.model_id)
    return StartTrainResponse(
        run_id=run.run_id,
        status=run.status,
        message=f"Training run {run.run_id} started.",
    )


@router.post("/stop", status_code=200)
async def stop_training(body: StopTrainRequest) -> dict:
    run = run_manager.get_run(body.run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run '{body.run_id}' not found")
    run_manager.stop_run(run)
    log.info("training_stopped", run_id=body.run_id)
    return {"run_id": body.run_id, "status": run.status}


@router.post("/pause", status_code=200)
async def pause_training(body: PauseTrainRequest) -> dict:
    run = run_manager.get_run(body.run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run '{body.run_id}' not found")
    run_manager.pause_run(run)
    return {"run_id": body.run_id, "status": run.status}


@router.post("/resume", status_code=200)
async def resume_training(body: ResumeTrainRequest) -> dict:
    run = run_manager.get_run(body.run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run '{body.run_id}' not found")
    run_manager.resume_run(run)
    return {"run_id": body.run_id, "status": run.status}


@router.get("/status", response_model=TrainStatusResponse)
async def get_train_status(run_id: str = Query(...)) -> TrainStatusResponse:
    run = run_manager.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    return TrainStatusResponse(
        run_id=run.run_id,
        status=run.status,
        epoch=run.epoch,
        total_epochs=run.total_epochs,
        step=run.step,
        total_steps=run.total_epochs * 100,
        eta_seconds=run.eta_seconds,
        elapsed_seconds=run.elapsed_seconds,
    )


# ── Run history ───────────────────────────────────────────────────────────────

@router.get("/runs", response_model=list[TrainRunOut])
async def list_runs() -> list[TrainRunOut]:
    return [_run_to_out(r) for r in reversed(run_manager.list_runs())]


@router.get("/runs/{run_id}", response_model=TrainRunOut)
async def get_run(run_id: str) -> TrainRunOut:
    run = run_manager.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    return _run_to_out(run)


# ── Schema Engine ─────────────────────────────────────────────────────────────

@router.get("/schema", response_model=TrainingSchemaResponse)
async def get_schema(
    model_id:   str = Query(""),
    dataset_id: str = Query(""),
    task:       str = Query("detection"),
) -> TrainingSchemaResponse:
    schema = generate_schema(task=task, model_id=model_id, dataset_id=dataset_id)
    return TrainingSchemaResponse(**schema)


# ── Checkpoints (stub — extend when artifact storage is wired) ────────────────

@router.get("/checkpoints", response_model=list[CheckpointOut])
async def list_checkpoints(run_id: str = Query(...)) -> list[CheckpointOut]:
    """Returns an empty list until checkpoint persistence is implemented."""
    run = run_manager.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    return []


@router.post("/checkpoints/{checkpoint_id}/export")
async def export_checkpoint(checkpoint_id: str, body: dict = {}) -> dict:
    raise HTTPException(status_code=501, detail="Checkpoint export not yet implemented")


# ── SSE: Metrics stream ────────────────────────────────────────────────────────

@router.get("/metrics/stream")
async def stream_metrics(run_id: str = Query(...)) -> StreamingResponse:
    """
    Server-Sent Events stream of TrainMetricsTick objects.
    Connects to the run's metrics queue and forwards each tick as SSE.
    Stream closes when the run finishes (sentinel None pushed by worker).
    """
    run = run_manager.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")

    q: asyncio.Queue = asyncio.Queue()
    run.metrics_subs.append(q)

    async def generator():
        yield ": connected\n\n"
        try:
            while True:
                try:
                    tick = await asyncio.wait_for(q.get(), timeout=30.0)
                except asyncio.TimeoutError:
                    # Heartbeat to keep connection alive
                    yield ": heartbeat\n\n"
                    continue
                if tick is None:
                    break
                yield f"data: {json.dumps(tick)}\n\n"
        finally:
            if q in run.metrics_subs:
                run.metrics_subs.remove(q)

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── SSE: Logs stream ──────────────────────────────────────────────────────────

@router.get("/logs/stream")
async def stream_logs(run_id: str = Query(...)) -> StreamingResponse:
    """Server-Sent Events stream of LogEntry objects."""
    run = run_manager.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")

    q: asyncio.Queue = asyncio.Queue()
    run.log_subs.append(q)

    async def generator():
        yield ": connected\n\n"
        try:
            while True:
                try:
                    entry = await asyncio.wait_for(q.get(), timeout=30.0)
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"
                    continue
                if entry is None:
                    break
                yield f"data: {json.dumps(entry)}\n\n"
        finally:
            if q in run.log_subs:
                run.log_subs.remove(q)

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/runs/{run_id}/history")
async def get_run_history(run_id: str) -> list[dict]:
    """Retrieves the full historical telemetry (metrics ticks) for a run."""
    run = run_manager.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    
    from training.persistence import TrainingPersistence
    run_dir = await TrainingPersistence.get_run_dir(run.project_id or "default", run_id)
    telemetry_path = os.path.join(run_dir, "telemetry.jsonl")
    
    history = []
    if os.path.exists(telemetry_path):
        try:
            with open(telemetry_path, "r") as f:
                for line in f:
                    if line.strip():
                        history.append(json.loads(line))
        except Exception as e:
            log.error("history_read_failed", run_id=run_id, error=str(e))
            raise HTTPException(status_code=500, detail="Failed to read telemetry history")
            
    return history

@router.get("/runs/{run_id}/artifacts")
async def list_run_artifacts(run_id: str) -> dict:
    """Lists available artifacts (images) for a specific run by scanning the directory."""
    run = run_manager.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    
    from training.persistence import TrainingPersistence
    run_dir = await TrainingPersistence.get_run_dir(run.project_id or "default", run_id)
    
    if not os.path.exists(run_dir):
        return {"artifacts": [], "batches": []}

    artifacts = []
    batches = []
    
    # Standard YOLO artifact mappings for better UI titles
    titles = {
        "confusion_matrix.png": "Confusion Matrix",
        "confusion_matrix_normalized.png": "Confusion Matrix (Norm)",
        "results.png": "Results Summary",
        "F1_curve.png": "F1 Curve",
        "PR_curve.png": "PR Curve",
        "P_curve.png": "Precision Curve",
        "R_curve.png": "Recall Curve",
        "BoxF1_curve.png": "Box F1 Curve",
        "BoxP_curve.png": "Box Precision Curve",
        "BoxPR_curve.png": "Box PR Curve",
        "BoxR_curve.png": "Box Recall Curve",
        "labels.jpg": "Labels Distribution",
        "labels_correlogram.jpg": "Labels Correlogram"
    }

    for f in os.listdir(run_dir):
        path = f"/train/runs/{run_id}/files/{f}"
        if f.endswith(('.png', '.jpg', '.jpeg')):
            item = {
                "title": titles.get(f, f.replace('_', ' ').title().split('.')[0]),
                "path": path,
                "type": "Analysis"
            }
            
            if "batch" in f.lower():
                item["type"] = "Batch Preview" if "val" in f.lower() else "Augmentation"
                batches.append(item)
            else:
                if "curve" in f.lower():
                    item["type"] = "Precision-Recall"
                elif "confusion" in f.lower():
                    item["type"] = "Analysis"
                elif "results" in f.lower():
                    item["type"] = "Overall"
                artifacts.append(item)

    return {
        "artifacts": sorted(artifacts, key=lambda x: x['title']),
        "batches": sorted(batches, key=lambda x: x['title'])
    }

@router.get("/runs/{run_id}/files/{filename}")
async def get_run_file(run_id: str, filename: str):
    """Serves a specific file from the run directory."""
    run = run_manager.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    
    # We need to find the project to get the run_dir
    # Since run_manager doesn't easily expose the full path in memory, 
    # we recalculate it using persistence
    from training.persistence import TrainingPersistence
    run_dir = await TrainingPersistence.get_run_dir(run.project_id or "default", run_id)
    file_path = os.path.join(run_dir, filename)
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
        
    from fastapi.responses import FileResponse
    return FileResponse(file_path)
# The frontend uses /system/metrics/stream for resources (already implemented).
# This alias exists for training-scoped resource monitoring.

@router.get("/resources/stream")
async def stream_resources(
    run_id:    str   = Query(...),
    gpu_index: int   = Query(0, ge=0),
    hz:        float = Query(1.0, ge=0.2, le=10.0),
) -> StreamingResponse:
    """
    SSE stream of ResourceTick objects for a specific training run.
    Forwards system metrics at the requested hz rate.
    """
    run = run_manager.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")

    q: asyncio.Queue = asyncio.Queue()
    run.resource_subs.append(q)

    interval = 1.0 / hz

    async def generator():
        yield ": connected\n\n"
        try:
            while True:
                try:
                    tick = await asyncio.wait_for(q.get(), timeout=30.0)
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"
                    continue
                if tick is None:
                    break
                yield f"data: {json.dumps(tick)}\n\n"
        finally:
            if q in run.resource_subs:
                run.resource_subs.remove(q)

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
