"""models/project.py — Pydantic domain model for workspace projects."""

from __future__ import annotations

from pydantic import BaseModel


class Project(BaseModel):
    id: str
    name: str
    path: str
    created_at: str
    last_opened: str
    status: str = "idle"

