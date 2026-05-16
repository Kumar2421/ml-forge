"""
models/inference.py — Pydantic models for the Inference Engine.
Covers request, response, session history, and pipeline stage telemetry.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Literal
from pydantic import BaseModel, Field
import time
import uuid


class AdapterType(str, Enum):
    YOLO        = "yolo"
    TRANSFORMERS = "transformers"
    ONNX        = "onnx"
    CUSTOM      = "custom"


class InferencePrecision(str, Enum):
    FP32 = "FP32"
    FP16 = "FP16"
    INT8 = "INT8"


class YOLOConfig(BaseModel):
    confidence:    float = Field(0.25, ge=0.0, le=1.0)
    iou_threshold: float = Field(0.45, ge=0.1, le=0.9)
    class_filter:  list[str] = Field(default_factory=list)
    max_detections: int = Field(300, ge=1, le=1000)


class TransformersConfig(BaseModel):
    max_new_tokens: int  = Field(256, ge=1, le=4096)
    temperature:    float = Field(0.7, ge=0.0, le=2.0)
    top_p:          float = Field(0.9, ge=0.0, le=1.0)
    top_k:          int   = Field(50, ge=0, le=200)
    beam_width:     int   = Field(1, ge=1, le=8)
    do_sample:      bool  = True


class ONNXConfig(BaseModel):
    execution_provider: Literal["CUDAExecutionProvider", "CPUExecutionProvider"] = "CUDAExecutionProvider"
    input_size:  int = Field(640, ge=32, le=1280)
    normalize:   bool = True


class CustomConfig(BaseModel):
    preprocess_script:  str = ""
    postprocess_script: str = ""


class InferenceRequest(BaseModel):
    model_id:    str
    adapter_type: AdapterType
    precision:   InferencePrecision = InferencePrecision.FP16

    # Input — one of these must be set
    image_base64: str | None = None   # base64-encoded image
    text_input:   str | None = None   # text/prompt

    # Per-adapter config
    yolo_config:         YOLOConfig | None         = None
    transformers_config: TransformersConfig | None = None
    onnx_config:         ONNXConfig | None         = None
    custom_config:       CustomConfig | None       = None

    # Execution
    run_mode: Literal["single", "stream"] = "single"


class PipelineStage(BaseModel):
    name:        str
    status:      Literal["pending", "running", "done", "error"] = "pending"
    latency_ms:  float | None = None
    detail:      str | None   = None


class Detection(BaseModel):
    x1:         float
    y1:         float
    x2:         float
    y2:         float
    confidence: float
    class_id:   int
    class_name: str


class InferenceResult(BaseModel):
    # Identity
    request_id:  str = Field(default_factory=lambda: str(uuid.uuid4()))
    model_id:    str
    adapter_type: AdapterType
    timestamp:   float = Field(default_factory=time.time)

    # Timing
    preprocess_ms:  float = 0.0
    inference_ms:   float = 0.0
    postprocess_ms: float = 0.0
    total_ms:       float = 0.0

    # Output — adapter-specific, all optional
    detections:    list[Detection] = Field(default_factory=list)
    text_output:   str | None      = None
    class_label:   str | None      = None
    confidence:    float | None    = None
    embeddings:    list[float] | None = None
    raw_output:    Any             = None          # raw JSON for inspector

    # Pipeline trace
    pipeline:      list[PipelineStage] = Field(default_factory=list)

    # Quality score (0–5) derived from confidence mean
    quality_score: float | None = None

    # Error
    error:         str | None = None
    status:        Literal["ok", "error"] = "ok"


class InferenceHistoryEntry(BaseModel):
    id:           str = Field(default_factory=lambda: str(uuid.uuid4()))
    model_id:     str
    model_name:   str
    adapter_type: AdapterType
    timestamp:    float = Field(default_factory=time.time)
    total_ms:     float
    quality_score: float | None
    status:       Literal["ok", "error"]
    # Compact snapshot of result for re-run
    request_snapshot: dict[str, Any] = Field(default_factory=dict)


class SystemVitals(BaseModel):
    ts:           float
    latency_ms:   float
    fps:          float
    vram_used_gb: float
    vram_total_gb: float
    gpu_temp_c:   float | None = None
    cpu_pct:      float        = 0.0
