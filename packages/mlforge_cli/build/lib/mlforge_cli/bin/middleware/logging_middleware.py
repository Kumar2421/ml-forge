"""
middleware/logging_middleware.py — Structured request/response logging.
Attaches a trace_id to every request, logs timing, method, path, status.
"""
from __future__ import annotations

import time
import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from observability.logger import audit, get_logger, log_system_event

log = get_logger("http")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        trace_id = str(uuid.uuid4())[:8]
        request.state.trace_id = trace_id
        start = time.perf_counter()

        log_system_event(
            level="info",
            message=f"API Request: {request.method} {request.url.path}",
            source="gateway",
            payload={"trace_id": trace_id, "query": str(request.url.query)}
        )

        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000

        log_system_event(
            level="info" if response.status_code < 400 else "error",
            message=f"API Response: {response.status_code} ({duration_ms:.1f}ms)",
            source="gateway",
            payload={"trace_id": trace_id, "status": response.status_code, "latency_ms": round(duration_ms, 2)}
        )

        response.headers["X-Trace-Id"] = trace_id
        response.headers["X-Response-Time"] = f"{duration_ms:.1f}ms"

        # Audit slow requests
        if duration_ms > 200:
            await audit(
                "slow_request",
                payload={
                    "path": request.url.path,
                    "duration_ms": round(duration_ms, 2),
                    "trace_id": trace_id,
                },
                level="warning",
            )

        return response
