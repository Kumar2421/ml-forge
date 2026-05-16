"""
models/job.py — Job domain models (download / benchmark / sync).
"""
from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field


class Job(BaseModel):
    model_config = {"protected_namespaces": ()}
    id:         str
    type:       str          # download|benchmark|sync
    status:     str          # queued|running|completed|failed|cancelled
    model_id:   str | None = None
    model_name: str | None = None
    progress:   float = 0.0  # 0.0–1.0
    error:      str | None = None
    meta:       dict[str, Any] = Field(default_factory=dict)
    created_at: str | None = None
    updated_at: str | None = None
    started_at: str | None = None
    ended_at:   str | None = None


class JobCreate(BaseModel):
    model_config = {"protected_namespaces": ()}
    model_id:   str
    model_name: str
    type:       str = "download"
    version:    str | None = None   # specific weight file / version to download


def row_to_job(row: Any) -> Job:
    d = dict(row)
    return Job(
        id         = d["id"],
        type       = d["type"],
        status     = d["status"],
        model_id   = d.get("model_id"),
        model_name = d.get("model_name"),
        progress   = float(d.get("progress", 0.0)),
        error      = d.get("error"),
        meta       = json.loads(d.get("meta") or "{}"),
        created_at = d.get("created_at"),
        updated_at = d.get("updated_at"),
        started_at = d.get("started_at"),
        ended_at   = d.get("ended_at"),
    )
