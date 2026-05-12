"""
models/benchmark.py — Pydantic domain models for the Benchmark Bridge System.
Single source of truth for all benchmark-related data shapes across API,
execution engine, and database layer.
"""
from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field, ConfigDict


# ── Input ─────────────────────────────────────────────────────────────────────

class BenchmarkContext(BaseModel):
    """Payload the UI sends to initiate a benchmark run."""
    model_config = ConfigDict(protected_namespaces=())
    model_id:   str
    dataset_id: str
    task:       str
    framework:  str
    hardware:   str = "cpu"
    precision:  str = "FP32"
    batch_size: int = Field(1, ge=1, le=512)
    # Task-specific overrides
    max_tokens:      int | None = 512
    sequence_length: int | None = 512
    img_size:        int | None = 640
    vid_stride:      int | None = 1
    stream:          bool | None = False
    input_source:    str | None = "dataset"
    video_path:      str | None = None
    rtsp_url:        str | None = None
    # Object Detection live preview data
    detections:      list[dict[str, Any]] = Field(default_factory=list)


# ── Validation ────────────────────────────────────────────────────────────────

class ValidationCheck(BaseModel):
    """Result of a single compatibility gate."""
    name:       str
    passed:     bool
    detail:     str
    suggestion: str | None = None


class ValidationReport(BaseModel):
    """Aggregated result of all compatibility checks for a model+dataset pair."""
    model_config = ConfigDict(protected_namespaces=())
    model_id:   str
    dataset_id: str
    passed:     bool                          # True only if ALL checks pass
    checks:     list[ValidationCheck]
    errors:     list[str]                     # details from failed checks
    warnings:   list[str] = Field(default_factory=list)


# ── Metrics ───────────────────────────────────────────────────────────────────

class BenchmarkMetrics(BaseModel):
    """Task-specific + hardware performance metrics from a completed run."""
    # Detection / Segmentation
    mAP:             float | None = None
    mAP_50:          float | None = None
    mAP_50_95:       float | None = None
    # Classification
    accuracy:        float | None = None
    top1:            float | None = None
    top5:            float | None = None
    # Segmentation
    iou_mean:        float | None = None
    # NLP / Generation
    rouge_l:         float | None = None
    bleu:            float | None = None
    perplexity:      float | None = None
    tokens_per_sec:  float | None = None
    # Throughput & Latency
    fps:             float | None = None
    latency_mean_ms: float | None = None
    latency_p95_ms:  float | None = None
    latency_p99_ms:  float | None = None
    # Memory
    vram_peak_gb:    float | None = None
    vram_avg_gb:     float | None = None
    # Dataset info
    total_images:    int | None = None
    total_tokens:    int | None = None
    batch_size:      int | None = None

    class Config:
        extra = "allow"


# ── Telemetry ─────────────────────────────────────────────────────────────────

class TelemetrySample(BaseModel):
    """Single hardware reading captured during benchmark execution."""
    timestamp:     float          # Unix epoch seconds
    gpu_util_pct:  float = 0.0   # 0–100
    vram_used_gb:  float = 0.0
    vram_total_gb: float = 0.0
    temp_c:        float = 0.0
    power_w:       float = 0.0
    batch_idx:     int   = 0
    progress:      float = 0.0   # 0.0–1.0
    # Optional task-specific live data (e.g. BBoxes for detection)
    live_data:     dict[str, Any] = Field(default_factory=dict)
    detections:    list[dict[str, Any]] = Field(default_factory=list)


class LayerBreakdown(BaseModel):
    """Single layer entry in a bottleneck analysis."""
    name:    str
    time_ms: float
    percent: float


class TelemetrySummary(BaseModel):
    """Aggregated telemetry statistics over the full benchmark run."""
    gpu_util_avg:   float = 0.0
    gpu_util_peak:  float = 0.0
    vram_avg_gb:    float = 0.0
    vram_peak_gb:   float = 0.0
    temp_avg_c:     float = 0.0
    temp_peak_c:    float = 0.0
    power_avg_w:    float = 0.0
    power_peak_w:   float = 0.0
    layer_breakdown: list[LayerBreakdown] = Field(default_factory=list)


# ── Job & Result ──────────────────────────────────────────────────────────────

class BenchmarkJob(BaseModel):
    id:         str
    model_config = ConfigDict(protected_namespaces=())
    model_id:   str
    dataset_id: str
    task:       str
    framework:  str
    hardware:   str
    precision:  str
    batch_size: int
    config:     dict = Field(default_factory=dict)
    status:     str  = "queued"   # queued|running|completed|failed
    progress:   float = 0.0
    logs:       list[str] = Field(default_factory=list)
    created_at: str | None = None
    updated_at: str | None = None
    started_at: str | None = None
    ended_at:   str | None = None
    last_telemetry: TelemetrySample | None = None


class BenchmarkResult(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    id:                str
    job_id:            str
    metrics:           BenchmarkMetrics
    telemetry_summary: TelemetrySummary
    created_at:        str | None = None
    # Denormalized from Job for UI efficiency
    model_id:          str | None = None
    dataset_id:        str | None = None
    task:              str | None = None
    framework:         str | None = None
    hardware:          str | None = None
    precision:         str | None = None


# ── API Responses ─────────────────────────────────────────────────────────────

class BenchmarkRunResponse(BaseModel):
    job_id:  str
    status:  str
    message: str


# ── DB Row helpers ────────────────────────────────────────────────────────────

def row_to_job(row: Any) -> BenchmarkJob:
    d = dict(row)
    cfg = json.loads(d.get("config") or "{}")
    return BenchmarkJob(
        id         = d["id"],
        model_id   = d["model_id"],
        dataset_id = d["dataset_id"],
        task       = d["task"],
        framework  = d["framework"],
        hardware   = d["hardware"],
        precision  = d["precision"],
        batch_size = d["batch_size"],
        config     = cfg,
        status     = d["status"],
        progress   = float(d.get("progress", 0.0)),
        logs       = json.loads(d.get("logs") or "[]"),
        error      = d.get("error"),
        created_at = d.get("created_at"),
        updated_at = d.get("updated_at"),
        started_at = d.get("started_at"),
        ended_at   = d.get("ended_at"),
        last_telemetry = TelemetrySample(**json.loads(d.get("last_telemetry") or "{}")) if d.get("last_telemetry") else None,
    )


def row_to_result(row: Any) -> BenchmarkResult:
    d = dict(row)
    metrics_raw   = json.loads(d.get("metrics") or "{}")
    telemetry_raw = json.loads(d.get("telemetry_summary") or "{}")
    return BenchmarkResult(
        id                = d["id"],
        job_id            = d["job_id"],
        metrics           = BenchmarkMetrics(**metrics_raw),
        telemetry_summary = TelemetrySummary(**telemetry_raw),
        created_at        = d.get("created_at"),
        model_id          = d.get("model_id"),
        dataset_id        = d.get("dataset_id"),
        task              = d.get("task"),
        framework         = d.get("framework"),
        hardware          = d.get("hardware"),
        precision         = d.get("precision"),
    )
