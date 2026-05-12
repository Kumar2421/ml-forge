"""
api/routes/datasets.py — Dataset Manager REST API.

Routes:
  GET  /datasets                   — list/search datasets
  GET  /datasets/{id}              — dataset detail
  POST /datasets/search/roboflow   — search Roboflow Universe (real-time)
  POST /datasets/sync/roboflow     — sync workspace datasets to local DB
  POST /datasets/{id}/import       — initiate dataset import job
  GET  /datasets/{id}/images       — paginated viewer (images + annotations)
  GET  /datasets/{id}/image/{img}  — serve raw image bytes
  GET  /datasets/jobs              — list import jobs
  GET  /datasets/jobs/{job_id}     — single job status
  POST /datasets/{id}/star         — toggle starred
  DELETE /datasets/{id}            — delete dataset record (+ local files)
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, Response

from adapters.roboflow_adapter import RoboflowAdapter
from datasets import registry as ds_reg
from datasets.import_service import start_import
from datasets.viewer_service import get_universal_viewer_page, get_viewer_page, resolve_image_path
from models.dataset import (
    Dataset, DatasetJob, DatasetSummary, DatasetSource, DatasetTask,
    DatasetFormat, DatasetStatus, ImportRequest, ImportResponse,
    RoboflowSearchRequest, ViewerPage, UniversalViewerPage, row_to_dataset,
)
from observability.logger import audit, get_logger

log = get_logger("datasets_route")

router = APIRouter(prefix="/datasets", tags=["datasets"])


# ── List / Search datasets ────────────────────────────────────────────────────

@router.get("", response_model=list[DatasetSummary])
async def list_datasets(
    task:    Optional[str]  = Query(None),
    format:  Optional[str]  = Query(None),
    source:  Optional[str]  = Query(None),
    status:  Optional[str]  = Query(None),
    search:  Optional[str]  = Query(None),
    starred: Optional[bool] = Query(None),
    limit:   int            = Query(100, ge=1, le=1000),
    offset:  int            = Query(0,   ge=0),
):
    try:
        datasets = await ds_reg.get_all_datasets(
            task=task, format=format, source=source,
            status=status, search=search, starred=starred,
            limit=limit, offset=offset,
        )
        return [_to_summary(d) for d in datasets]
    except Exception as exc:
        log.exception("list_datasets_error")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/jobs", response_model=list[DatasetJob])
async def list_jobs(limit: int = Query(50, ge=1, le=500)):
    return await ds_reg.get_all_jobs(limit=limit)


@router.get("/jobs/{job_id}", response_model=DatasetJob)
async def get_job(job_id: str):
    job = await ds_reg.get_job(job_id)
    if not job:
        raise HTTPException(404, f"Job {job_id!r} not found")
    return job


@router.post("/jobs/{job_id}/stop")
async def stop_job(job_id: str):
    """Cancel a running import job."""
    # Logic to cancel the asyncio task would go here
    # For now, we update the status in the DB
    await ds_reg.update_job(job_id, status="failed", error="Cancelled by user", ended_at=datetime.utcnow().isoformat())
    return {"status": "success", "message": "Job stop requested"}


@router.post("/jobs/{job_id}/pause")
async def pause_job(job_id: str):
    """Pause a running import job."""
    await ds_reg.update_job(job_id, status="paused")
    return {"status": "success", "message": "Job pause requested"}


@router.post("/jobs/{job_id}/resume")
async def resume_job(job_id: str):
    """Resume a paused import job."""
    await ds_reg.update_job(job_id, status="running")
    return {"status": "success", "message": "Job resume requested"}


# ── Roboflow Search & Sync ────────────────────────────────────────────────────

@router.post("/search/roboflow", response_model=list[DatasetSummary])
async def search_roboflow(req: RoboflowSearchRequest):
    """
    Live search Roboflow Universe. Results are cached for 1 hour.
    Also upserts results into local DB so they appear in /datasets.
    """
    try:
        datasets = await RoboflowAdapter.search_datasets(
            api_key   = req.api_key,
            query     = req.query,
            workspace = req.workspace,
            page      = req.page,
            page_size = req.page_size,
        )
    except Exception as exc:
        log.error("roboflow_search_error", error=str(exc))
        raise HTTPException(502, f"Roboflow API error: {exc}")

    # Upsert to local DB
    await ds_reg.bulk_upsert_datasets(datasets)
    await audit("roboflow_search", {"query": req.query, "count": len(datasets)})
    return [_to_summary(d) for d in datasets]


@router.post("/sync/roboflow", response_model=dict)
async def sync_roboflow_workspace(
    api_key: str = Query(..., description="Roboflow API key"),
    workspace: str = Query(..., description="Workspace slug"),
):
    """Sync all datasets from a Roboflow workspace into local DB."""
    try:
        datasets = await RoboflowAdapter.list_workspace_datasets(api_key, workspace)
    except Exception as exc:
        raise HTTPException(502, f"Roboflow API error: {exc}")
    count = await ds_reg.bulk_upsert_datasets(datasets)
    return {"synced": count, "workspace": workspace}


# ── Dataset detail ────────────────────────────────────────────────────────────

@router.get("/{dataset_id}", response_model=Dataset)
async def get_dataset(dataset_id: str):
    ds = await ds_reg.get_dataset(dataset_id)
    if not ds:
        raise HTTPException(404, f"Dataset {dataset_id!r} not found")
    return ds


# ── Import ────────────────────────────────────────────────────────────────────

@router.post("/{dataset_id}/import", response_model=ImportResponse)
async def import_dataset(dataset_id: str, req: ImportRequest):
    """
    Initiate a background import job for a dataset.
    Supports sources: roboflow | roboflow_curl | huggingface | local
    """
    req.dataset_id = dataset_id   # enforce consistency

    # Sources that are discovered outside the registry must be auto-registered.
    auto_register_sources = {DatasetSource.huggingface, DatasetSource.roboflow_curl, DatasetSource.local}
    if req.source in auto_register_sources:
        ds = await ds_reg.get_dataset(dataset_id)
        if not ds:
            # Determine human-readable name
            if req.source == DatasetSource.huggingface and req.hf_dataset_id:
                name = req.hf_dataset_id
                roboflow_ref = req.hf_dataset_id
                fmt = DatasetFormat.json
                src = DatasetSource.huggingface

            elif req.source == DatasetSource.local:
                # local: use provided name or folder name from path
                # Try req.local_path first, then req.name, then fallback to dataset_id
                path_to_use = req.local_path or req.name or ""
                name = req.name or (Path(path_to_use).name if path_to_use else dataset_id)
                roboflow_ref = None
                fmt = DatasetFormat.custom
                src = DatasetSource.local
            else:
                # roboflow_curl: use provided dataset_name or fall back to dataset_id
                name = req.dataset_name or dataset_id
                roboflow_ref = None
                fmt = _curl_format_to_enum(req.curl_format)
                src = DatasetSource.roboflow_curl

            stub = Dataset(
                id=dataset_id,
                name=name,
                task=DatasetTask.detection,
                format=fmt,
                source=src,
                status=DatasetStatus.available,
                roboflow_id=roboflow_ref,
                created_at=datetime.utcnow().isoformat(),
            )
            await ds_reg.upsert_dataset(stub)
            log.info("dataset_auto_registered", dataset_id=dataset_id, source=str(req.source))
    else:
        ds = await ds_reg.get_dataset(dataset_id)
        if not ds:
            raise HTTPException(404, f"Dataset {dataset_id!r} not found in registry. "
                                "Run /datasets/sync/roboflow first.")

    try:
        job_id = await start_import(req)
    except ValueError as exc:
        raise HTTPException(400, str(exc))

    await audit("dataset_import_requested", {"dataset_id": dataset_id, "source": str(req.source)})
    return ImportResponse(
        job_id     = job_id,
        dataset_id = dataset_id,
        status     = "queued",
        message    = "Import job created successfully",
    )


def _curl_format_to_enum(curl_format: str | None) -> DatasetFormat:
    """Map Roboflow export format string from cURL to DatasetFormat enum."""
    if not curl_format:
        return DatasetFormat.yolo
    fmt = curl_format.lower()
    if "yolo" in fmt:
        return DatasetFormat.yolo
    if "coco" in fmt:
        return DatasetFormat.coco
    if "voc" in fmt or "pascal" in fmt:
        return DatasetFormat.voc
    if "tfrecord" in fmt:
        return DatasetFormat.tfrecord
    if "csv" in fmt:
        return DatasetFormat.csv
    if "json" in fmt or "createml" in fmt:
        return DatasetFormat.json
    return DatasetFormat.yolo


# ── Viewer ────────────────────────────────────────────────────────────────────

@router.get("/{dataset_id}/universal", response_model=UniversalViewerPage)
async def get_universal_items(
    dataset_id: str,
    page:      int           = Query(0, ge=0),
    page_size: int           = Query(20, ge=1, le=100),
    split:     Optional[str] = Query(None, regex="^(train|val|test)$"),
    class_label: Optional[str] = Query(None),
):
    """
    Polymorphic dataset item viewer (UDV).
    Supports Vision, NLP, and Tabular data via the Universal Dataset Item schema.
    """
    ds = await ds_reg.get_dataset(dataset_id)
    if not ds:
        raise HTTPException(404, f"Dataset {dataset_id!r} not found")
    
    # Allow viewing even if not fully imported for NLP/Tabular if files exist,
    # but for Vision we usually need the index.
    return await get_universal_viewer_page(dataset_id, page, page_size, split, class_label)


@router.get("/{dataset_id}/images", response_model=ViewerPage)
async def get_images(
    dataset_id: str,
    page:      int           = Query(0, ge=0),
    page_size: int           = Query(20, ge=1, le=100),
    split:     Optional[str] = Query(None, regex="^(train|val|test)$"),
    class_label: Optional[str] = Query(None),
):
    """
    Paginated image + annotation data for the viewer.
    Annotations are returned in normalised [0–1] coordinates.
    Supports filtering by split and class label.
    """
    ds = await ds_reg.get_dataset(dataset_id)
    if not ds:
        raise HTTPException(404, f"Dataset {dataset_id!r} not found")
    if ds.status != "imported":
        raise HTTPException(409, f"Dataset is not imported yet (status: {ds.status})")

    return await get_viewer_page(dataset_id, page, page_size, split, class_label)


@router.get("/{dataset_id}/stats", response_model=dict)
async def get_dataset_stats(dataset_id: str):
    """Return pre-computed class distributions and split statistics."""
    ds = await ds_reg.get_dataset(dataset_id)
    if not ds:
        raise HTTPException(404, f"Dataset {dataset_id!r} not found")
    
    return await ds_reg.get_dataset_stats(dataset_id)


@router.get("/{dataset_id}/image/{image_id}")
async def serve_image(dataset_id: str, image_id: str):
    """Serve raw image bytes for the viewer (cached by browser)."""
    path = await resolve_image_path(dataset_id, image_id)
    if path is None:
        raise HTTPException(404, "Image not found or dataset not imported")

    suffix = path.suffix.lower()
    media_types = {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".png": "image/png",  ".bmp": "image/bmp",
        ".webp": "image/webp",
    }
    media_type = media_types.get(suffix, "application/octet-stream")
    return FileResponse(
        path        = str(path),
        media_type  = media_type,
        headers     = {"Cache-Control": "public, max-age=86400"},
    )


@router.get("/{dataset_id}/annotations", response_model=dict)
async def get_annotations_summary(dataset_id: str):
    """Return class distribution summary from the annotations index."""
    from database.connection import get_db
    db = await get_db()
    async with db.execute(
        """SELECT label, COUNT(*) as count
           FROM dataset_annotations
           WHERE dataset_id=?
           GROUP BY label
           ORDER BY count DESC""",
        (dataset_id,),
    ) as cur:
        rows = await cur.fetchall()
    return {
        "dataset_id": dataset_id,
        "class_distribution": [{"label": r["label"], "count": r["count"]} for r in rows],
        "total_annotations": sum(r["count"] for r in rows),
    }


# ── Star / Delete ─────────────────────────────────────────────────────────────

@router.post("/{dataset_id}/star", response_model=dict)
async def toggle_star(dataset_id: str):
    new_val = await ds_reg.toggle_starred(dataset_id)
    return {"dataset_id": dataset_id, "starred": new_val}


@router.delete("/{dataset_id}", response_model=dict)
async def delete_dataset(
    dataset_id: str,
    delete_files: bool = Query(False, description="Also remove local files from disk"),
):
    ds = await ds_reg.get_dataset(dataset_id)
    if not ds:
        raise HTTPException(404, f"Dataset {dataset_id!r} not found")

    if delete_files and ds.local_path:
        import shutil
        local = Path(ds.local_path)
        if local.exists() and local.is_dir():
            shutil.rmtree(str(local), ignore_errors=True)
            log.info("dataset_files_deleted", path=str(local))

    deleted = await ds_reg.delete_dataset(dataset_id)
    await audit("dataset_deleted", {"dataset_id": dataset_id, "files_deleted": delete_files})
    return {"deleted": deleted, "dataset_id": dataset_id}


# ── Helper ────────────────────────────────────────────────────────────────────

def _to_summary(d: Dataset) -> DatasetSummary:
    # Use 0.0 as default health_score if stats is missing or health_score is not present
    health_score = 0.0
    try:
        if hasattr(d, 'stats') and d.stats:
            health_score = getattr(d.stats, 'health_score', 0.0)
    except Exception:
        pass

    return DatasetSummary(
        id              = d.id,
        name            = d.name,
        task            = str(d.task),
        format          = str(d.format),
        source          = str(d.source),
        status          = str(d.status),
        images          = d.images,
        classes         = d.classes,
        size_label      = d.size_label,
        tags            = d.tags,
        starred         = d.starred,
        import_progress = d.import_progress,
        health_score    = health_score,
        created_at      = d.created_at,
        updated_at      = d.updated_at,
    )
