"""
observability/logger.py — Structured JSON logging & audit trail.
Every module imports get_logger(); every API call writes to audit_log.
"""
from __future__ import annotations

import logging
import sys
import traceback
import random
import asyncio
from datetime import datetime, timezone
from typing import Any

import structlog
from structlog.types import EventDict, WrappedLogger

from config import settings


# ── Processors ────────────────────────────────────────────────────────────────

def _add_timestamp(
    _logger: WrappedLogger, _method: str, event_dict: EventDict
) -> EventDict:
    event_dict["timestamp"] = datetime.now(timezone.utc).isoformat()
    return event_dict


def _add_service(
    _logger: WrappedLogger, _method: str, event_dict: EventDict
) -> EventDict:
    event_dict["service"] = "mlforge-backend"
    event_dict["version"] = settings.version
    return event_dict


# ── Bootstrap ─────────────────────────────────────────────────────────────────

def configure_logging() -> None:
    """Call once at startup before any log is emitted."""
    settings.ensure_dirs()

    shared_processors: list[Any] = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        _add_timestamp,
        _add_service,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    # File handler — JSON
    file_handler = logging.FileHandler(
        settings.logs_dir / "backend.log", encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)

    # Console handler — pretty in dev, JSON in prod
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG if settings.debug else logging.INFO)

    logging.basicConfig(
        level=logging.DEBUG,
        handlers=[file_handler, console_handler],
        format="%(message)s",
    )

    structlog.configure(
        processors=shared_processors
        + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Attach JSON renderer to handlers
    renderer = structlog.processors.JSONRenderer()
    formatter = structlog.stdlib.ProcessorFormatter(
        processor=renderer,
        foreign_pre_chain=shared_processors,
    )
    for handler in logging.getLogger().handlers:
        handler.setFormatter(formatter)


# ── Global System Log Queue (for Unified Dashboard) ──────────────────────────

_sys_log_queue: asyncio.Queue = asyncio.Queue(maxsize=1000)
_sys_log_subs: list[asyncio.Queue] = []

def log_system_event(
    level: str,
    message: str,
    source: str = "system",
    payload: dict[str, Any] | None = None
) -> None:
    """Push a structured log into the global system queue."""
    import time
    
    event = {
        "id": f"sys-{time.time()}-{random.random()}",
        "ts": time.strftime("%H:%M:%S"),
        "timestamp": int(time.time() * 1000),
        "level": level.upper(),
        "source": source,
        "message": message,
        "metrics": payload,
        "source_type": "system"
    }
    
    # Broadcast to all active SSE subscribers
    dead = []
    for q in _sys_log_subs:
        try:
            if q.qsize() >= 100: q.get_nowait()
            q.put_nowait(event)
        except Exception:
            dead.append(q)
    for d in dead:
        if d in _sys_log_subs:
            _sys_log_subs.remove(d)


def get_logger(name: str = "mlforge") -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)


async def audit(
    event_type: str,
    payload: dict[str, Any] | None = None,
    model_id: str | None = None,
    job_id: str | None = None,
    level: str = "info",
) -> None:
    """Write a structured audit record to the audit_log table."""
    import json
    from database.connection import get_db

    db = await get_db()
    await db.execute(
        """INSERT INTO audit_log (event_type, model_id, job_id, payload, level)
           VALUES (?, ?, ?, ?, ?)""",
        (event_type, model_id, job_id, json.dumps(payload or {}), level),
    )
    await db.commit()
