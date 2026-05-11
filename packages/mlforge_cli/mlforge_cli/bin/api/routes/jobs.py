"""
api/routes/jobs.py — /jobs & /download endpoints.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from download.manager import cancel_job, enqueue_download, get_job, list_jobs
from models.job import Job, JobCreate
from observability.logger import audit, get_logger
from registry.registry import get_model

log = get_logger("api.jobs")
router = APIRouter(tags=["jobs"])


@router.post("/download", response_model=Job, status_code=202)
async def trigger_download(body: JobCreate) -> Job:
    """Enqueue a model download. Returns the created job immediately."""
    model = await get_model(body.model_id)
    if not model:
        raise HTTPException(status_code=404, detail=f"Model '{body.model_id}' not found")
    if model.downloaded:
        raise HTTPException(status_code=409, detail="Model is already cached locally")

    job_id = await enqueue_download(
        model_id=body.model_id,
        model_name=body.model_name,
        version=body.version,
    )
    job = await get_job(job_id)
    if not job:
        raise HTTPException(status_code=500, detail="Job creation failed")

    await audit("api_download_trigger", model_id=body.model_id, job_id=job_id)
    return job


@router.get("/jobs", response_model=list[Job])
async def jobs_list(status: str | None = None, limit: int = 50) -> list[Job]:
    return await list_jobs(status=status, limit=limit)


@router.get("/jobs/{job_id}", response_model=Job)
async def job_detail(job_id: str) -> Job:
    job = await get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    return job


@router.delete("/jobs/{job_id}", status_code=204, response_model=None)
async def job_cancel(job_id: str) -> None:
    success = await cancel_job(job_id)
    if not success:
        raise HTTPException(status_code=409, detail="Job cannot be cancelled")
