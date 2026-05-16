"""api/routes/system.py — System metrics endpoints."""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from models.system import SystemMetrics
from system.metrics import sample_metrics

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/metrics", response_model=SystemMetrics)
async def get_metrics(gpu_index: int = Query(0, ge=0)) -> SystemMetrics:
    payload = sample_metrics(gpu_index=gpu_index)
    return SystemMetrics(
        ts=payload["ts"],
        cpu_pct=payload["cpu_pct"],
        cpu_model=payload.get("cpu_model"),
        cpu_freq_mhz=payload.get("cpu_freq_mhz"),
        cpu_count=payload.get("cpu_count"),
        ram_used_mb=payload["ram_used_mb"],
        ram_total_mb=payload["ram_total_mb"],
        gpu=payload.get("gpu"),
        disks=payload.get("disks", []),
        network=payload.get("network", []),
    )


@router.get("/metrics/stream")
async def stream_metrics(
    gpu_index: int = Query(0, ge=0),
    hz: float = Query(2.0, ge=0.2, le=20.0),
):
    """Server-Sent Events stream of system metrics."""

    interval = 1.0 / float(hz)

    async def gen():
        # Initial comment helps some proxies establish the stream
        yield ": connected\n\n"
        while True:
            try:
                payload = sample_metrics(gpu_index=gpu_index)
                # Ensure the payload is valid JSON and wrapped in data: format
                data = json.dumps(payload)
                yield f"data: {data}\n\n"
            except Exception as e:
                # Log error but keep stream alive
                print(f"Metrics streaming error: {e}")
            await asyncio.sleep(interval)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
            "Transfer-Encoding": "chunked",
        },
    )


@router.get("/logs/stream")
async def stream_system_logs():
    """SSE stream of global system and gateway logs."""
    from observability.logger import _sys_log_subs
    
    q: asyncio.Queue = asyncio.Queue()
    _sys_log_subs.append(q)

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
            if q in _sys_log_subs:
                _sys_log_subs.remove(q)

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
