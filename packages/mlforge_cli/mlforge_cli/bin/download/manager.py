"""
download/manager.py — Async download manager.
Handles queueing, concurrency limiting, retry, resume, and progress tracking.
All state is persisted in the jobs table for crash recovery.
"""
from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiofiles
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from config import settings
from database.connection import get_db
from models.job import Job, row_to_job
from observability.logger import audit, get_logger
from registry.registry import get_model, update_model_status

log = get_logger("download_manager")

# ── Semaphore caps concurrent downloads ───────────────────────────────────────
_download_sem: asyncio.Semaphore | None = None


def _get_sem() -> asyncio.Semaphore:
    global _download_sem
    if _download_sem is None:
        _download_sem = asyncio.Semaphore(settings.max_concurrent_downloads)
    return _download_sem


# ── Job CRUD ──────────────────────────────────────────────────────────────────

async def _create_job(
    job_type: str,
    model_id: str,
    model_name: str,
    meta: dict | None = None,
) -> str:
    job_id = str(uuid.uuid4())
    db = await get_db()
    now = datetime.now(timezone.utc).isoformat()
    await db.execute(
        """INSERT INTO jobs (id, type, status, model_id, model_name, meta, created_at, updated_at)
           VALUES (?,?,?,?,?,?,?,?)""",
        (job_id, job_type, "queued", model_id, model_name,
         json.dumps(meta or {}), now, now),
    )
    await db.commit()
    log.info("job_created", job_id=job_id, type=job_type, model_id=model_id)
    await audit("job_created", model_id=model_id, job_id=job_id,
                payload={"type": job_type, "model_name": model_name})
    return job_id


def _is_shard_file(filename: str) -> bool:
    """Return True if the file is part of a sharded model (e.g. model-00001-of-00003.safetensors)."""
    import re
    return bool(re.search(r"-\d{5}-of-\d{5}\.", filename))


async def _get_active_version(model_id: str) -> str:
    """Return the active version string for a model, defaulting to 'v1'."""
    model = await get_model(model_id)
    if model and model.active_version:
        return model.active_version
    return "v1"


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=6),
    reraise=True,
)
async def _resolve_hf_download_url(repo_id: str) -> str:
    """Resolve a reliable download URL for a HF repo.

    Prefer safetensors over pytorch_model.bin; fall back to onnx if needed.
    """
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        resp = await client.get(f"{settings.hf_api_base}/models/{repo_id}")
        resp.raise_for_status()
        data = resp.json()

    siblings = data.get("siblings") or []
    filenames: list[str] = []
    for s in siblings:
        fn = s.get("rfilename") or s.get("filename")
        if fn:
            filenames.append(fn)

    preferred_exact = [
        "model.safetensors",
        "pytorch_model.bin",
        "model.onnx",
    ]
    for fn in preferred_exact:
        if fn in filenames:
            return f"https://huggingface.co/{repo_id}/resolve/main/{fn}"

    preferred_suffix = [".safetensors", ".bin", ".onnx", ".pt", ".pth"]
    for suffix in preferred_suffix:
        for fn in filenames:
            if fn.endswith(suffix) and not _is_shard_file(fn):
                return f"https://huggingface.co/{repo_id}/resolve/main/{fn}"

    # Accept sharded files as a fallback (first shard of safetensors)
    for fn in filenames:
        if _is_shard_file(fn):
            return f"https://huggingface.co/{repo_id}/resolve/main/{fn}"

    # Last resort: try the index file for sharded models
    if "model.safetensors.index.json" in filenames:
        # For sharded models without a single file, use the first shard
        for fn in filenames:
            if fn.startswith("model-") and fn.endswith(".safetensors"):
                return f"https://huggingface.co/{repo_id}/resolve/main/{fn}"

    return f"https://huggingface.co/{repo_id}/resolve/main/pytorch_model.bin"


async def _update_job(
    job_id: str,
    status: str | None = None,
    progress: float | None = None,
    error: str | None = None,
    started_at: str | None = None,
    ended_at: str | None = None,
) -> None:
    db = await get_db()
    now = datetime.now(timezone.utc).isoformat()
    parts: list[str] = ["updated_at = ?"]
    vals: list[Any] = [now]
    if status is not None:   parts.append("status = ?");    vals.append(status)
    if progress is not None: parts.append("progress = ?");  vals.append(progress)
    if error is not None:    parts.append("error = ?");     vals.append(error)
    if started_at:           parts.append("started_at = ?"); vals.append(started_at)
    if ended_at:             parts.append("ended_at = ?");   vals.append(ended_at)
    vals.append(job_id)
    await db.execute(f"UPDATE jobs SET {', '.join(parts)} WHERE id = ?", vals)
    await db.commit()


# ── Download worker ───────────────────────────────────────────────────────────

async def _execute_download(
    job_id: str,
    model_id: str,
    model_name: str,
    download_url: str,
    dest_path: Path,
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    await _update_job(job_id, status="running", started_at=now)

    dest_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = dest_path.with_suffix(".tmp")

    # Determine resume offset
    resume_offset = tmp_path.stat().st_size if tmp_path.exists() else 0

    headers: dict[str, str] = {}
    if resume_offset:
        headers["Range"] = f"bytes={resume_offset}-"
        log.info("download_resume", job_id=job_id, offset=resume_offset)

    try:
        async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
            async with client.stream("GET", download_url, headers=headers) as resp:
                resp.raise_for_status()
                total = int(resp.headers.get("content-length", 0)) + resume_offset
                downloaded = resume_offset

                async with aiofiles.open(tmp_path, "ab" if resume_offset else "wb") as fh:
                    async for chunk in resp.aiter_bytes(chunk_size=settings.download_chunk_size):
                        await fh.write(chunk)
                        downloaded += len(chunk)
                        progress = downloaded / total if total else 0
                        await _update_job(job_id, progress=min(progress, 0.99))

        # Rename tmp → final
        tmp_path.rename(dest_path)
        now_end = datetime.now(timezone.utc).isoformat()
        await _update_job(job_id, status="completed", progress=1.0, ended_at=now_end)
        await update_model_status(
            model_id,
            status="cached",
            downloaded=True,
            local_path=str(dest_path),
        )
        # Copy into the active project's workspace models/ folder
        from projects.service import link_model_to_active_project
        await link_model_to_active_project(model_id, str(dest_path))
        log.info("download_complete", job_id=job_id, model_id=model_id, path=str(dest_path))
        await audit("download_complete", model_id=model_id, job_id=job_id,
                    payload={"path": str(dest_path)})

    except Exception as exc:
        now_end = datetime.now(timezone.utc).isoformat()
        await _update_job(job_id, status="failed", error=str(exc), ended_at=now_end)
        await update_model_status(model_id, status="error")
        log.error("download_failed", job_id=job_id, error=str(exc))
        await audit("download_failed", model_id=model_id, job_id=job_id,
                    payload={"error": str(exc)}, level="error")
        raise


# ── Public API ────────────────────────────────────────────────────────────────

async def enqueue_download(
    model_id: str,
    model_name: str,
    download_url: str | None = None,
    version: str | None = None,
) -> str:
    """Create a download job and dispatch resolution+download in the background.

    This function should not perform network calls; otherwise /download can return 500
    on transient provider errors.
    """
    job_id = await _create_job("download", model_id, model_name)

    asyncio.create_task(
        _rate_limited_download_resolving(job_id, model_id, model_name, download_url, version)
    )
    return job_id


async def _rate_limited_download_resolving(
    job_id: str,
    model_id: str,
    model_name: str,
    download_url: str | None,
    version: str | None = None,
) -> None:
    async with _get_sem():
        try:
            resolved_url = await _resolve_download_url(model_id, download_url, version)
            # Version folder: use explicit version label, else active_version from DB
            folder = version or await _get_active_version(model_id)
            ext = Path(resolved_url.split("?")[0]).suffix or ".bin"
            dest_path = settings.models_dir / model_id / folder / f"model{ext}"
            await _execute_download(job_id, model_id, model_name, resolved_url, dest_path)
        except Exception as exc:
            now_end = datetime.now(timezone.utc).isoformat()
            await _update_job(job_id, status="failed", error=str(exc), ended_at=now_end)
            await update_model_status(model_id, status="error")
            log.error("download_failed", job_id=job_id, error=str(exc))
            await audit(
                "download_failed",
                model_id=model_id,
                job_id=job_id,
                payload={"error": str(exc)},
                level="error",
            )


async def _resolve_download_url(
    model_id: str,
    download_url: str | None,
    version: str | None = None,
) -> str:
    """Resolve the final download URL for a model.

    If `version` is provided and looks like a filename (e.g. 'yolov8n_pt'),
    it was generated by hf_adapter from a sibling rfilename. Restore the
    original filename (replace trailing _ext with .ext) and build a direct URL.
    """
    repo_id: str | None = None

    if download_url and "huggingface.co" in download_url:
        repo_id = download_url.replace("https://huggingface.co/", "").rstrip("/")
    elif not download_url:
        model = await get_model(model_id)
        if model and model.download_url:
            url = model.download_url
            if "huggingface.co" in url:
                repo_id = url.replace("https://huggingface.co/", "").rstrip("/")
            else:
                return url
        else:
            repo_id = model_id.replace("_", "/", 1)
    else:
        return download_url

    # If the caller specified a version that is a converted rfilename
    # (dots replaced with underscores by hf_adapter), reconstruct the filename.
    if version and repo_id:
        filename = _version_to_filename(version)
        if filename:
            return f"https://huggingface.co/{repo_id}/resolve/main/{filename}"

    return await _resolve_hf_download_url(repo_id)


def _version_to_filename(version: str) -> str | None:
    """Convert an hf_adapter version string back to a real filename.

    hf_adapter stores version as rfilename.replace('.', '_'), e.g.:
      'yolov8n_pt' → 'yolov8n.pt'
      'model_safetensors' → 'model.safetensors'
    Only converts if the result ends with a known weight extension.
    """
    weight_exts = (".pt", ".pth", ".safetensors", ".bin", ".onnx")
    # Try replacing the last underscore with a dot
    idx = version.rfind("_")
    if idx == -1:
        return None
    candidate = version[:idx] + "." + version[idx + 1:]
    if any(candidate.endswith(ext) for ext in weight_exts):
        return candidate
    return None


async def _rate_limited_download(
    job_id: str,
    model_id: str,
    model_name: str,
    download_url: str,
    dest_path: Path,
) -> None:
    async with _get_sem():
        try:
            await _execute_download(job_id, model_id, model_name, download_url, dest_path)
        except Exception:
            pass  # Already logged & stored in DB


async def get_job(job_id: str) -> Job | None:
    db = await get_db()
    async with db.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)) as cur:
        row = await cur.fetchone()
    return row_to_job(row) if row else None


async def list_jobs(
    status: str | None = None,
    limit: int = 50,
) -> list[Job]:
    db = await get_db()
    if status:
        sql = "SELECT * FROM jobs WHERE status = ? ORDER BY created_at DESC LIMIT ?"
        params: tuple = (status, limit)
    else:
        sql = "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?"
        params = (limit,)
    async with db.execute(sql, params) as cur:
        rows = await cur.fetchall()
    return [row_to_job(r) for r in rows]


async def cancel_job(job_id: str) -> bool:
    """Cancel a queued or running job (best-effort)."""
    job = await get_job(job_id)
    if not job or job.status not in ("queued", "running"):
        return False
    now = datetime.now(timezone.utc).isoformat()
    await _update_job(job_id, status="cancelled", ended_at=now)
    log.info("job_cancelled", job_id=job_id)
    return True
