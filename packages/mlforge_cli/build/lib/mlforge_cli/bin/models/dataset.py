"""
models/dataset.py — Pydantic domain models for the Dataset Manager.
Single source of truth for all dataset-related data shapes.
"""
from __future__ import annotations

import json
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, ConfigDict


# ── Universal Dataset Viewer (UDV) Models ──────────────────────────────────

class DatasetContentType(str, Enum):
    image = "image"
    text = "text"
    audio = "audio"
    tabular = "tabular"

class UniversalAnnotationType(str, Enum):
    detection = "detection"
    segmentation = "segmentation"
    keypoints = "keypoints"
    classification = "classification"
    span = "span"

class UniversalAnnotation(BaseModel):
    label: str
    type: UniversalAnnotationType
    bbox: Optional[list[float]] = None  # [x, y, w, h] normalized
    segmentation: Optional[list[list[float]]] = None # [[x1, y1, x2, y2, ...], ...]
    keypoints: Optional[list[float]] = None # [x1, y1, v1, ...]
    confidence: Optional[float] = None
    metadata: Optional[dict[str, Any]] = None

class UniversalDatasetItem(BaseModel):
    id: str
    content_type: DatasetContentType
    content_url: Optional[str] = None
    content_body: Optional[str] = None  # For text or raw json
    filename: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    annotations: list[UniversalAnnotation] = Field(default_factory=list)

class UniversalViewerPage(BaseModel):
    dataset_id: str
    page: int
    page_size: int
    total: int
    total_pages: int
    items: list[UniversalDatasetItem]


# ── Enumerations ──────────────────────────────────────────────────────────────

class DatasetTask(str, Enum):
    detection      = "detection"
    classification = "classification"
    segmentation   = "segmentation"
    nlp            = "nlp"
    generation     = "generation"
    keypoints      = "keypoints"


class DatasetFormat(str, Enum):
    yolo    = "yolo"
    coco    = "coco"
    voc     = "voc"
    csv     = "csv"
    json    = "json"
    tfrecord = "tfrecord"
    custom  = "custom"


class DatasetSource(str, Enum):
    roboflow      = "roboflow"
    roboflow_curl = "roboflow_curl"   # direct cURL / pre-signed URL download
    local         = "local"
    huggingface   = "huggingface"


class DatasetStatus(str, Enum):
    available  = "available"
    queued     = "queued"
    importing  = "importing"
    extracting = "extracting"
    validating = "validating"
    imported   = "imported"
    failed     = "failed"


class JobType(str, Enum):
    import_  = "import"
    extract  = "extract"
    validate = "validate"
    analyze  = "analyze"
    delete   = "delete"


class JobStatus(str, Enum):
    queued    = "queued"
    running   = "running"
    completed = "completed"
    failed    = "failed"
    cancelled = "cancelled"


class AnnotationType(str, Enum):
    detection      = "detection"
    segmentation   = "segmentation"
    classification = "classification"


# ── Sub-models ────────────────────────────────────────────────────────────────

class DatasetSplit(BaseModel):
    train: int = 0
    val:   int = 0
    test:  int = 0

    @property
    def total(self) -> int:
        return self.train + self.val + self.test


class DatasetVersion(BaseModel):
    version:   str
    date:      str = ""
    changes:   str = ""
    images:    int = 0
    format:    str = ""


class DatasetStats(BaseModel):
    """Aggregate statistics computed during import/analysis."""
    image_count:      int   = 0
    annotation_count: int   = 0
    class_count:      int   = 0
    avg_objects:      float = 0.0
    missing_labels:   int   = 0
    empty_images:     int   = 0
    duplicate_count:  int   = 0
    health_score:     float = 0.0
    split:            DatasetSplit = Field(default_factory=DatasetSplit)


# ── Core Domain Models ────────────────────────────────────────────────────────

class Dataset(BaseModel):
    model_config = ConfigDict(protected_namespaces=(), use_enum_values=True)
    id:             str
    name:           str
    description:    str = ""
    task:           DatasetTask
    format:         DatasetFormat
    source:         DatasetSource
    status:         DatasetStatus = DatasetStatus.available
    images:         int = 0
    classes:        int = 0
    class_names:    list[str] = Field(default_factory=list)
    size_bytes:     int = 0
    size_label:     str = "0 B"
    local_path:     str | None = None
    import_progress: float = 0.0       # 0.0–1.0
    tags:           list[str] = Field(default_factory=list)
    versions:       list[DatasetVersion] = Field(default_factory=list)
    active_version: str = "v1"
    stats:          DatasetStats = Field(default_factory=DatasetStats)
    starred:        bool = False
    roboflow_id:    str | None = None  # workspace/project slug
    created_at:     str | None = None
    updated_at:     str | None = None


class DatasetSummary(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    """Lightweight projection for list endpoints."""
    id:             str
    name:           str
    task:           str
    format:         str
    source:         str
    status:         str
    images:         int
    classes:        int
    size_label:     str
    tags:           list[str]
    starred:        bool
    import_progress: float
    health_score:   float = 0.0
    created_at:     str | None = None
    updated_at:     str | None = None


# ── Annotation Models ─────────────────────────────────────────────────────────

class BoundingBox(BaseModel):
    x:      float   # top-left x (pixels or normalised)
    y:      float   # top-left y
    width:  float
    height: float
    normalised: bool = True   # True → 0–1 range, False → pixel coords


class Annotation(BaseModel):
    """Unified annotation record (format-agnostic)."""
    label:       str
    bbox:        BoundingBox | None = None
    segmentation: list[list[float]] | None = None   # polygon points
    keypoints:    list[float] | None = None         # [x, y, v, ...]
    metadata:     dict[str, Any] | None = None
    confidence:  float | None = None
    area:        float | None = None
    type:        AnnotationType = AnnotationType.detection


class ImageRecord(BaseModel):
    """Image + its parsed annotations — returned by viewer endpoints."""
    image_id:    str
    filename:    str
    width:       int = 0
    height:      int = 0
    path:        str                    # relative to dataset root
    annotations: list[Annotation] = Field(default_factory=list)
    split:       str = "train"          # train|val|test


class ViewerPage(BaseModel):
    """Paginated viewer response."""
    dataset_id:  str
    page:        int
    page_size:   int
    total:       int
    total_pages: int
    images:      list[ImageRecord]


# ── Job Models ────────────────────────────────────────────────────────────────

class DatasetJob(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    id:          str
    type:        str
    status:      str
    dataset_id:  str
    dataset_name: str
    progress:    float = 0.0            # 0.0–1.0
    message:     str = ""
    error:       str | None = None
    created_at:  str | None = None
    updated_at:  str | None = None
    started_at:  str | None = None
    ended_at:    str | None = None


# ── Request/Response Schemas ─────────────────────────────────────────────────

class ImportRequest(BaseModel):
    dataset_id:   str
    source:       DatasetSource
    roboflow_key: str | None = None   # required when source=roboflow
    roboflow_workspace: str | None = None
    roboflow_project:   str | None = None
    roboflow_version:   int = 1
    hf_dataset_id: str | None = None  # required when source=huggingface (e.g. "microsoft/coco")
    format:       DatasetFormat = DatasetFormat.yolo
    local_path:   str | None = None   # required when source=local
    # cURL / direct download (source=roboflow_curl)
    download_url:  str | None = None  # pre-signed or direct download URL
    headers:       dict[str, str] = Field(default_factory=dict)  # Custom headers for download
    dataset_name:  str | None = None  # human-readable name override
    name:          str | None = None  # alias for dataset_name (used in local folder import)
    curl_format:   str | None = None  # export format label from Roboflow cURL (e.g. "yolov8")


class ImportResponse(BaseModel):
    job_id:     str
    dataset_id: str
    status:     str
    message:    str


class RoboflowSearchRequest(BaseModel):
    query:       str = ""
    api_key:     str
    workspace:   str | None = None
    page:        int = 0
    page_size:   int = 50


# ── DB Row helpers ────────────────────────────────────────────────────────────

def row_to_dataset(row: Any) -> Dataset:
    """
    Robustly convert a DB row (sqlite3.Row or dict) to a Dataset model.
    Handles:
    1. Enum string cleaning (stripping prefixes like 'DatasetStatus.')
    2. JSON parsing for nested fields (tags, class_names, versions)
    3. Missing 'stats' object initialization
    """
    import logging
    logger = logging.getLogger("models.dataset")
    
    try:
        d = dict(row) if not isinstance(row, dict) else row.copy()
        
        def clean_enum(val: Any) -> Any:
            if isinstance(val, str) and "." in val:
                return val.split(".")[-1]
            return val

        # Clean enum fields
        for field in ["status", "task", "format", "source"]:
            if field in d:
                d[field] = clean_enum(d[field])

        # Parse JSON fields with safety
        for field in ["class_names", "tags", "versions"]:
            raw = d.get(field)
            if isinstance(raw, str):
                try:
                    d[field] = json.loads(raw)
                except Exception:
                    d[field] = []
            elif raw is None:
                d[field] = []

        # Handle 'stats' - it might be a JSON string or missing in DB
        stats_obj = DatasetStats()
        stats_raw = d.get("stats")
        if isinstance(stats_raw, str):
            try:
                stats_data = json.loads(stats_raw)
                stats_obj = DatasetStats(**stats_data)
            except Exception:
                pass
        elif isinstance(stats_raw, dict):
            try:
                stats_obj = DatasetStats(**stats_raw)
            except Exception:
                pass
        
        # Ensure other numeric/boolean fields have defaults
        d["images"] = d.get("images", 0)
        d["classes"] = d.get("classes", 0)
        d["starred"] = bool(d.get("starred", 0))
        d["import_progress"] = float(d.get("import_progress", 0.0))
        d["size_bytes"] = d.get("size_bytes", 0)

        # Build clean dict for Pydantic
        clean_data = {
            "id": d["id"],
            "name": d["name"],
            "description": d.get("description", ""),
            "task": d["task"],
            "format": d["format"],
            "source": d["source"],
            "status": d.get("status", "available"),
            "images": d["images"],
            "classes": d["classes"],
            "class_names": d["class_names"],
            "size_bytes": d["size_bytes"],
            "size_label": d.get("size_label", "0 B"),
            "local_path": d.get("local_path"),
            "import_progress": d["import_progress"],
            "tags": d["tags"],
            "versions": d["versions"],
            "active_version": d.get("active_version", "v1"),
            "stats": stats_obj,
            "starred": d["starred"],
            "roboflow_id": d.get("roboflow_id"),
            "created_at": d.get("created_at"),
            "updated_at": d.get("updated_at")
        }

        return Dataset(**clean_data)
        
    except Exception as e:
        logger.error(f"Pydantic instantiation error: {e}, row keys: {list(row.keys()) if hasattr(row, 'keys') else 'N/A'}")
        raise


def row_to_job(row: Any) -> DatasetJob:
    d = dict(row)
    return DatasetJob(
        id           = d["id"],
        type         = d["type"],
        status       = d["status"],
        dataset_id   = d.get("dataset_id", ""),
        dataset_name = d.get("dataset_name", ""),
        progress     = float(d.get("progress", 0.0)),
        message      = d.get("message", ""),
        error        = d.get("error"),
        created_at   = d.get("created_at"),
        updated_at   = d.get("updated_at"),
        started_at   = d.get("started_at"),
        ended_at     = d.get("ended_at"),
    )
