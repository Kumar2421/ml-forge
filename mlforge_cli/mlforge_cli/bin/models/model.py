"""
models/model.py — Pydantic domain models (schema contract for API + internal).
Single source of truth for data shapes between all modules.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

# ── Enumerations ──────────────────────────────────────────────────────────────

ModelTask      = str   # detection|classification|segmentation|generation|embedding|nlp
ModelFramework = str   # pytorch|onnx|tensorflow|tflite|coreml
ModelSource    = str   # hf|onnx|local
ModelStatus    = str   # available|downloading|cached|error
HardwareTarget = str   # gpu|cpu|edge|tpu


# ── Sub-models ────────────────────────────────────────────────────────────────

class ModelMetrics(BaseModel):
    latency_ms: float | None = None
    mAP:        float | None = None
    accuracy:   float | None = None
    top1:       float | None = None
    vram_gb:    float | None = None
    fps:        float | None = None
    flops:      float | None = None

    class Config:
        extra = "allow"


class ModelVersion(BaseModel):
    version:     str
    label:       str = "Stable"    # Latest|Stable|Legacy|Nano|Small|Medium|Large|XLarge
    description: str | None = None
    releaseDate: str = ""
    changelog:   str | None = None


# ── Core Model ────────────────────────────────────────────────────────────────

class Model(BaseModel):
    id:          str
    name:        str
    variant:     str | None = None
    task:        ModelTask
    framework:   ModelFramework
    size:        int = 0        # bytes
    size_label:  str = "0 B"
    tags:        list[str] = Field(default_factory=list)
    source:      ModelSource = "hf"
    provider:    str = ""
    description: str = ""
    download_url: str | None = None  # explicit download source (HF repo URL, ONNX direct URL, etc.)
    local_path:  str | None = None
    project_id:  str | None = None
    downloaded:  bool = False
    status:      ModelStatus = "available"
    hardware:    list[HardwareTarget] = Field(default_factory=list)
    metrics:     ModelMetrics = Field(default_factory=ModelMetrics)
    versions:    list[ModelVersion] = Field(default_factory=list)
    active_version: str | None = None
    rating:      float | None = None
    downloads:   int | None = None
    liked:       bool = False
    created_at:  str | None = None
    updated_at:  str | None = None


class ModelSummary(BaseModel):
    """Lightweight projection returned in list endpoints."""
    id:         str
    name:       str
    task:       ModelTask
    framework:  ModelFramework
    source:     ModelSource
    provider:   str
    size_label: str
    status:     ModelStatus
    downloaded: bool
    downloads:  int | None = None
    rating:     float | None = None
    tags:       list[str]
    hardware:   list[HardwareTarget]
    metrics:    ModelMetrics


# ── DB Row → Model ────────────────────────────────────────────────────────────

def row_to_model(row: Any, versions: list[ModelVersion] | None = None) -> Model:
    """Convert an aiosqlite Row dict to a Model instance."""
    d = dict(row)
    metrics_raw = d.get("metrics") or "{}"
    # metrics may come from model_versions join or not exist on models row
    if isinstance(metrics_raw, str):
        metrics_raw = json.loads(metrics_raw)

    return Model(
        id          = d["id"],
        name        = d["name"],
        variant     = d.get("variant"),
        task        = d["task"],
        framework   = d["framework"],
        source      = d.get("source", "hf"),
        provider    = d.get("provider", ""),
        description = d.get("description", ""),
        download_url= d.get("download_url"),
        size        = d.get("size", 0),
        size_label  = d.get("size_label", "0 B"),
        tags        = json.loads(d.get("tags") or "[]"),
        hardware    = json.loads(d.get("hardware") or "[]"),
        status      = d.get("status", "available"),
        downloaded  = bool(d.get("downloaded", 0)),
        local_path  = d.get("local_path"),
        project_id  = d.get("project_id"),
        downloads   = d.get("downloads"),
        rating      = d.get("rating"),
        liked       = bool(d.get("liked", 0)),
        metrics     = ModelMetrics(**metrics_raw),
        versions    = versions or [],
        active_version = d.get("active_version"),
        created_at  = d.get("created_at"),
        updated_at  = d.get("updated_at"),
    )
