"""
api/routes/inference.py — Inference Engine endpoints.

POST /inference/run       — single synchronous inference pass
POST /inference/stream    — SSE stream (stage-by-stage pipeline events)
GET  /inference/history   — session ledger
DELETE /inference/history — clear session ledger
GET  /inference/cache     — currently warm models in memory
DELETE /inference/cache/{model_id} — evict from cache
"""
from __future__ import annotations

import asyncio
import json
import time

from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import StreamingResponse

from inference.engine import InferenceEngine, evict_model, get_cache_status
from inference.session import clear_history, get_history, record
from models.inference import (
    InferenceHistoryEntry,
    InferenceRequest,
    InferenceResult,
)
from observability.logger import get_logger
from registry.registry import get_model

log = get_logger("api.inference")
router = APIRouter(prefix="/inference", tags=["inference"])

_engine = InferenceEngine()


# ── Single run ───────────────────────────────────────────────────────────────

@router.post("/run", response_model=InferenceResult)
async def run_inference(body: InferenceRequest) -> InferenceResult:
    """Execute one full inference pass and return the complete result."""
    model = await get_model(body.model_id)
    if not model:
        raise HTTPException(status_code=404, detail=f"Model '{body.model_id}' not found")

    result = await _engine.run(body, model)

    if result.status == "error":
        raise HTTPException(status_code=500, detail=result.error or "Inference failed")

    await record(body, result, model.name)
    return result


# ── SSE stream ───────────────────────────────────────────────────────────────

@router.post("/stream")
async def stream_inference(body: InferenceRequest) -> StreamingResponse:
    """
    Server-Sent Events stream.
    Emits one JSON event per pipeline stage as it completes, then a final
    'done' event with the full InferenceResult.

    Client usage:
        const es = new EventSource('/inference/stream');  // POST via fetch + EventSource polyfill
        es.onmessage = e => console.log(JSON.parse(e.data));
    """
    model = await get_model(body.model_id)
    if not model:
        raise HTTPException(status_code=404, detail=f"Model '{body.model_id}' not found")

    queue: asyncio.Queue[str | None] = asyncio.Queue()

    async def _producer() -> None:
        """Run inference while pushing SSE events into the queue."""
        try:
            # Patch engine to emit stage events
            result = await _engine_stream(body, model, queue)
            await record(body, result, model.name)
            # Final complete event
            await queue.put(
                f"event: done\ndata: {result.model_dump_json()}\n\n"
            )
        except Exception as exc:
            await queue.put(
                f"event: error\ndata: {json.dumps({'error': str(exc)})}\n\n"
            )
        finally:
            await queue.put(None)   # sentinel

    asyncio.create_task(_producer())

    async def _generator():
        while True:
            msg = await queue.get()
            if msg is None:
                break
            yield msg

    return StreamingResponse(
        _generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


async def _engine_stream(
    req: InferenceRequest,
    model,
    queue: asyncio.Queue,
) -> InferenceResult:
    """
    Run inference and push a 'stage' SSE event for each PipelineStage.
    Falls back to a simple full run if streaming is not distinguishable.
    """
    # Run full pipeline
    result = await _engine.run(req, model)

    # Emit one event per stage (replay after completion)
    for stage in result.pipeline:
        payload = json.dumps({
            "type": "stage",
            "stage": stage.model_dump(),
            "ts": time.time(),
        })
        await queue.put(f"data: {payload}\n\n")
        await asyncio.sleep(0)    # yield

    # Emit vitals snapshot
    vitals_payload = json.dumps({
        "type": "vitals",
        "latency_ms": result.inference_ms,
        "total_ms":   result.total_ms,
        "quality":    result.quality_score,
    })
    await queue.put(f"data: {vitals_payload}\n\n")

    return result


# ── History ──────────────────────────────────────────────────────────────────

@router.get("/history", response_model=list[InferenceHistoryEntry])
async def inference_history(limit: int = 50) -> list[InferenceHistoryEntry]:
    return await get_history(limit=min(limit, 200))


@router.delete("/history", status_code=204, response_model=None)
async def clear_inference_history():
    await clear_history()
    return Response(status_code=204)


# ── Model cache ──────────────────────────────────────────────────────────────

@router.get("/cache")
async def cache_status() -> dict[str, bool]:
    return get_cache_status()


@router.delete("/cache/{model_id}", status_code=204, response_model=None)
async def evict_from_cache(model_id: str):
    evicted = evict_model(model_id)
    if not evicted:
        raise HTTPException(status_code=404, detail="Model not in cache")
    return Response(status_code=204)
