"""
api/routes/sync.py — /sync endpoint: fetch fresh models from all adapters.
"""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks

from adapters.hf_adapter import HFAdapter
from adapters.onnx_adapter import ONNXAdapter
from observability.logger import audit, get_logger
from registry.registry import bulk_upsert, count_models

log = get_logger("api.sync")
router = APIRouter(tags=["sync"])


async def _run_full_sync() -> None:
    log.info("sync_start")
    total = 0

    async with HFAdapter() as hf:
        hf_models = await hf.fetch_models()
    await bulk_upsert(hf_models)
    total += len(hf_models)
    log.info("sync_hf_done", count=len(hf_models))

    # Prune any HF models outside the allowed task set (e.g. legacy NLP entries)
    allowed_tasks = {"detection", "classification", "segmentation", "generation", "embedding"}
    from database.connection import get_db

    db = await get_db()
    placeholders = ",".join(["?"] * len(allowed_tasks))
    await db.execute(
        f"DELETE FROM models WHERE source = 'hf' AND task NOT IN ({placeholders})",
        tuple(sorted(allowed_tasks)),
    )
    # Prune non-vision generation/embedding HF models. We rely on the adapter
    # adding the pipeline_tag as a normalised tag (e.g. text_to_image).
    await db.execute(
        """
        DELETE FROM models
        WHERE source = 'hf'
          AND task IN ('generation','embedding')
          AND (
            tags NOT LIKE '%text_to_image%'
            AND tags NOT LIKE '%image_to_image%'
            AND tags NOT LIKE '%image_feature_extraction%'
          )
        """,
    )
    await db.commit()

    onnx = ONNXAdapter()
    onnx_models = await onnx.fetch_models()
    await bulk_upsert(onnx_models)
    total += len(onnx_models)
    log.info("sync_onnx_done", count=len(onnx_models))

    log.info("sync_complete", total=total)
    await audit("sync_complete", payload={"total": total})


@router.post("/sync", status_code=202)
async def trigger_sync(background_tasks: BackgroundTasks) -> dict:
    """
    Kick off a background sync that fetches models from all sources.
    Returns immediately; progress visible via /models count.
    """
    background_tasks.add_task(_run_full_sync)
    current = await count_models()
    log.info("sync_triggered", current_model_count=current)
    await audit("sync_triggered", payload={"current": current})
    return {"message": "Sync started", "current_model_count": current}
