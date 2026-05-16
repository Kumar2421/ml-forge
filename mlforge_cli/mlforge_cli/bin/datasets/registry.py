"""
datasets/registry.py — Dataset Registry: persistent CRUD against datasets table.
All DB interactions for datasets and dataset_jobs live here.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from database.connection import get_db
from models.dataset import Dataset, DatasetJob, DatasetStatus, row_to_dataset, row_to_job
from observability.logger import get_logger

log = get_logger("dataset_registry")


# ── Dataset CRUD ──────────────────────────────────────────────────────────────

async def get_all_datasets(
    task: str | None = None,
    format: str | None = None,
    source: str | None = None,
    status: str | None = None,
    search: str | None = None,
    starred: bool | None = None,
    limit: int = 500,
    offset: int = 0,
) -> list[Dataset]:
    db = await get_db()
    clauses = []
    params: list[Any] = []

    if task:
        clauses.append("task = ?")
        params.append(task)
    if format:
        clauses.append("format = ?")
        params.append(format)
    if source:
        clauses.append("source = ?")
        params.append(source)
    if status:
        clauses.append("status = ?")
        params.append(status)
    if starred is not None:
        clauses.append("starred = ?")
        params.append(1 if starred else 0)
    if search:
        clauses.append("(name LIKE ? OR description LIKE ? OR tags LIKE ?)")
        q = f"%{search}%"
        params.extend([q, q, q])

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = f"SELECT * FROM datasets {where} ORDER BY updated_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    async with db.execute(sql, params) as cur:
        rows = await cur.fetchall()
    return [row_to_dataset(r) for r in rows]


async def get_dataset_stats(dataset_id: str) -> dict:
    """Get pre-computed class distributions and statistics from the indexed annotations."""
    db = await get_db()
    
    # Class distribution (from dataset_annotations table)
    async with db.execute(
        "SELECT label, COUNT(*) as count FROM dataset_annotations WHERE dataset_id=? GROUP BY label ORDER BY count DESC",
        (dataset_id,)
    ) as cur:
        dist = await cur.fetchall()
    
    # Split distribution (from dataset_images table)
    async with db.execute(
        "SELECT split, COUNT(*) as count FROM dataset_images WHERE dataset_id=? GROUP BY split",
        (dataset_id,)
    ) as cur:
        splits = await cur.fetchall()

    return {
        "class_distribution": {row["label"]: row["count"] for row in dist},
        "split_distribution": {row["split"]: row["count"] for row in splits}
    }


async def get_dataset(dataset_id: str) -> Dataset | None:
    db = await get_db()
    async with db.execute("SELECT * FROM datasets WHERE id = ?", (dataset_id,)) as cur:
        row = await cur.fetchone()
    return row_to_dataset(row) if row else None


async def count_datasets() -> int:
    db = await get_db()
    async with db.execute("SELECT COUNT(*) FROM datasets") as cur:
        row = await cur.fetchone()
    return row[0] if row else 0


async def upsert_dataset(ds: Dataset) -> None:
    """Insert or replace a dataset record."""
    db = await get_db()

    task = getattr(ds.task, "value", ds.task)
    fmt = getattr(ds.format, "value", ds.format)
    src = getattr(ds.source, "value", ds.source)
    status = getattr(ds.status, "value", ds.status)
    await db.execute(
        """INSERT OR REPLACE INTO datasets
           (id, name, description, task, format, source, status,
            images, classes, class_names, size_bytes, size_label,
            local_path, import_progress, tags, versions, active_version,
            starred, roboflow_id, created_at, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,datetime('now'))""",
        (
            ds.id, ds.name, ds.description, task, fmt,
            src, status,
            ds.images, ds.classes,
            json.dumps(ds.class_names), ds.size_bytes, ds.size_label,
            ds.local_path, ds.import_progress,
            json.dumps(ds.tags),
            json.dumps([v.model_dump() if hasattr(v, "model_dump") else v for v in ds.versions]),
            ds.active_version,
            1 if ds.starred else 0,
            ds.roboflow_id,
            ds.created_at or datetime.utcnow().isoformat(),
        ),
    )
    await db.commit()


async def update_dataset_status(
    dataset_id: str,
    status: DatasetStatus,
    progress: float | None = None,
    local_path: str | None = None,
) -> None:
    db = await get_db()
    if progress is not None and local_path is not None:
        await db.execute(
            "UPDATE datasets SET status=?, import_progress=?, local_path=? WHERE id=?",
            (status.value, progress, local_path, dataset_id),
        )
    elif progress is not None:
        await db.execute(
            "UPDATE datasets SET status=?, import_progress=? WHERE id=?",
            (status.value, progress, dataset_id),
        )
    else:
        await db.execute(
            "UPDATE datasets SET status=? WHERE id=?",
            (status.value, dataset_id),
        )
    await db.commit()


async def update_dataset_stats(
    dataset_id: str, 
    images: int, 
    classes: int, 
    class_names: list[str], 
    size_bytes: int,
    stats: dict | None = None
) -> None:
    db = await get_db()
    
    # Calculate health score if stats provided
    health_score = 0.0
    if stats:
        health_score = stats.get("health_score", 0.0)
    
    await db.execute(
        """UPDATE datasets
           SET images=?, classes=?, class_names=?, size_bytes=?,
               size_label=?, stats=?, health_score=?
           WHERE id=?""",
        (
            images, classes, json.dumps(class_names),
            size_bytes, _fmt_bytes(size_bytes),
            json.dumps(stats) if stats else None,
            health_score,
            dataset_id,
        ),
    )
    await db.commit()


async def delete_dataset(dataset_id: str) -> bool:
    db = await get_db()
    async with db.execute("SELECT 1 FROM datasets WHERE id=?", (dataset_id,)) as cur:
        exists = await cur.fetchone()
    if not exists:
        return False
    await db.execute("DELETE FROM datasets WHERE id=?", (dataset_id,))
    await db.commit()
    return True


async def toggle_starred(dataset_id: str) -> bool:
    """Toggle starred flag, return new value."""
    db = await get_db()
    async with db.execute("SELECT starred FROM datasets WHERE id=?", (dataset_id,)) as cur:
        row = await cur.fetchone()
    if not row:
        return False
    new_val = 0 if row["starred"] else 1
    await db.execute("UPDATE datasets SET starred=? WHERE id=?", (new_val, dataset_id))
    await db.commit()
    return bool(new_val)


# ── Bulk dataset upsert from Roboflow ────────────────────────────────────────

async def bulk_upsert_datasets(datasets: list[Dataset]) -> int:
    """Insert/update many datasets in a single transaction."""
    if not datasets:
        return 0
    db = await get_db()
    now = datetime.utcnow().isoformat()
    rows = [
        (
            ds.id, ds.name, ds.description, ds.task.value, ds.format.value,
            ds.source.value, ds.status.value,
            ds.images, ds.classes,
            json.dumps(ds.class_names), ds.size_bytes, ds.size_label,
            ds.local_path, ds.import_progress,
            json.dumps(ds.tags), json.dumps([]),
            ds.active_version, 0, ds.roboflow_id,
            ds.created_at or now,
        )
        for ds in datasets
    ]
    await db.executemany(
        """INSERT OR IGNORE INTO datasets
           (id, name, description, task, format, source, status,
            images, classes, class_names, size_bytes, size_label,
            local_path, import_progress, tags, versions, active_version,
            starred, roboflow_id, created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        rows,
    )
    await db.commit()
    return len(datasets)


# ── Dataset Jobs ──────────────────────────────────────────────────────────────

async def create_job(
    dataset_id: str,
    dataset_name: str,
    job_type: str,
) -> DatasetJob:
    db = await get_db()
    job_id = f"djob-{uuid.uuid4().hex[:12]}"
    now = datetime.utcnow().isoformat()
    await db.execute(
        """INSERT INTO dataset_jobs
           (id, type, status, dataset_id, dataset_name, progress, message, created_at)
           VALUES (?, ?, 'queued', ?, ?, 0.0, '', ?)""",
        (job_id, job_type, dataset_id, dataset_name, now),
    )
    await db.commit()
    return DatasetJob(
        id=job_id, type=job_type, status="queued",
        dataset_id=dataset_id, dataset_name=dataset_name,
        created_at=now,
    )


async def update_job(
    job_id: str,
    status: str | None = None,
    progress: float | None = None,
    message: str | None = None,
    error: str | None = None,
    started_at: str | None = None,
    ended_at: str | None = None,
) -> None:
    db = await get_db()
    parts = []
    params: list[Any] = []
    if status is not None:
        parts.append("status=?");       params.append(status)
    if progress is not None:
        parts.append("progress=?");     params.append(progress)
    if message is not None:
        parts.append("message=?");      params.append(message)
    if error is not None:
        parts.append("error=?");        params.append(error)
    if started_at is not None:
        parts.append("started_at=?");   params.append(started_at)
    if ended_at is not None:
        parts.append("ended_at=?");     params.append(ended_at)
    if not parts:
        return
    params.append(job_id)
    await db.execute(f"UPDATE dataset_jobs SET {', '.join(parts)} WHERE id=?", params)
    await db.commit()


async def get_job(job_id: str) -> DatasetJob | None:
    db = await get_db()
    async with db.execute("SELECT * FROM dataset_jobs WHERE id=?", (job_id,)) as cur:
        row = await cur.fetchone()
    return row_to_job(row) if row else None


async def get_all_jobs(limit: int = 100) -> list[DatasetJob]:
    db = await get_db()
    async with db.execute(
        "SELECT * FROM dataset_jobs ORDER BY created_at DESC LIMIT ?", (limit,)
    ) as cur:
        rows = await cur.fetchall()
    return [row_to_job(r) for r in rows]


# ── Image Index ───────────────────────────────────────────────────────────────

async def index_images(
    dataset_id: str,
    records: list[dict],   # [{id, filename, rel_path, width, height, split, ann_count}]
) -> int:
    db = await get_db()
    await db.executemany(
        """INSERT OR IGNORE INTO dataset_images
           (id, dataset_id, filename, rel_path, width, height, split, ann_count)
           VALUES (:id, :dataset_id, :filename, :rel_path, :width, :height, :split, :ann_count)""",
        [{"dataset_id": dataset_id, **r} for r in records],
    )
    await db.commit()
    return len(records)


async def get_image_page(
    dataset_id: str,
    page: int = 0,
    page_size: int = 20,
    split: str | None = None,
    class_label: str | None = None,
) -> tuple[int, list[dict]]:
    db = await get_db()
    
    clauses = ["dataset_id=?"]
    params: list[Any] = [dataset_id]
    
    if split:
        clauses.append("split=?")
        params.append(split)
        
    if class_label:
        # Join with annotations table to filter by class
        where = f"WHERE {' AND '.join(clauses)} AND id IN (SELECT image_id FROM dataset_annotations WHERE label=?)"
        count_params = params + [class_label]
    else:
        where = f"WHERE {' AND '.join(clauses)}"
        count_params = params

    async with db.execute(f"SELECT COUNT(*) FROM dataset_images {where}", count_params) as cur:
        total = (await cur.fetchone())[0]
        
    params_final = count_params + [page_size, page * page_size]
    async with db.execute(
        f"SELECT * FROM dataset_images {where} ORDER BY filename LIMIT ? OFFSET ?", params_final
    ) as cur:
        rows = await cur.fetchall()
    return total, [dict(r) for r in rows]


async def get_annotations_for_image(image_id: str) -> list[dict]:
    db = await get_db()
    async with db.execute(
        "SELECT * FROM dataset_annotations WHERE image_id=?", (image_id,)
    ) as cur:
        rows = await cur.fetchall()
    return [dict(r) for r in rows]


async def bulk_insert_annotations(records: list[dict]) -> int:
    if not records:
        return 0
    db = await get_db()
    await db.executemany(
        """INSERT OR IGNORE INTO dataset_annotations
           (id, image_id, dataset_id, label, bbox_x, bbox_y, bbox_w, bbox_h,
            normalised, area, confidence, ann_type)
           VALUES (:id,:image_id,:dataset_id,:label,:bbox_x,:bbox_y,:bbox_w,:bbox_h,
                   :normalised,:area,:confidence,:ann_type)""",
        records,
    )
    await db.commit()
    return len(records)


    # ── Universal Dataset Items ──────────────────────────────────────────────

async def get_universal_items(
        self,
        dataset_id: str,
        page: int = 0,
        page_size: int = 20,
        split: str | None = None,
        class_label: str | None = None,
    ) -> tuple[int, list[dict]]:
        """Fetch polymorphic dataset items (images, text rows, etc.) and their annotations."""
        db = await get_db()
        
        # 1. Get total and base item records
        total, items = await self.get_image_page(dataset_id, page, page_size, split, class_label)
        
        # 2. Convert to universal format
        # This is a bridge until we fully move to the universal schema
        return total, items

async def bulk_insert_universal_annotations(self, records: list[dict]) -> int:
        """Insert universal annotations into the extended schema."""
        if not records:
            return 0
        db = await get_db()
        await db.executemany(
            """INSERT OR IGNORE INTO dataset_annotations
               (id, image_id, dataset_id, label, bbox_x, bbox_y, bbox_w, bbox_h,
                normalised, area, confidence, ann_type, segmentation, keypoints, metadata)
               VALUES (:id,:image_id,:dataset_id,:label,:bbox_x,:bbox_y,:bbox_w,:bbox_h,
                       :normalised,:area,:confidence,:ann_type,:segmentation,:keypoints,:metadata)""",
            records,
        )
        await db.commit()
        return len(records)

async def update_dataset_task(dataset_id: str, task: str) -> None:
    db = await get_db()
    await db.execute("UPDATE datasets SET task=? WHERE id=?", (task, dataset_id))
    await db.commit()


async def cleanup_stale_jobs() -> None:
    """Mark running/queued jobs as failed on startup."""
    db = await get_db()
    await db.execute(
        "UPDATE dataset_jobs SET status='failed', error='System restart' WHERE status IN ('running', 'queued')"
    )
    await db.commit()


def _fmt_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"
