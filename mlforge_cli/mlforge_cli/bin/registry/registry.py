"""
registry/registry.py — Model Registry.
Responsible for persisting, reading, and updating model metadata in SQLite.
All callers go through this module; no direct DB access from other modules.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any



from database.connection import get_db
from models.model import Model, ModelVersion, row_to_model
from observability.logger import audit, get_logger

log = get_logger("registry")


async def upsert_model(model: Model) -> None:
    """Insert or update a model record (and its first version)."""
    db = await get_db()
    now = datetime.now(timezone.utc).isoformat()

    await db.execute(
        """INSERT INTO models
               (id, name, variant, task, framework, source, provider, description,
                download_url, size, size_label, tags, hardware, status, downloaded, local_path, project_id,
                active_version, metrics,
                downloads, rating, liked, created_at, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(id) DO UPDATE SET
               name=excluded.name,
               variant=excluded.variant,
               task=excluded.task,
               framework=excluded.framework,
               source=excluded.source,
               provider=excluded.provider,
               description=excluded.description,
               download_url=excluded.download_url,
               size=excluded.size,
               size_label=excluded.size_label,
               tags=excluded.tags,
               hardware=excluded.hardware,
               status=excluded.status,
               downloads=excluded.downloads,
               rating=excluded.rating,
               active_version=excluded.active_version,
               metrics=excluded.metrics,
               local_path=excluded.local_path,
               project_id=excluded.project_id,
               updated_at=excluded.updated_at""",
        (
            model.id, model.name, model.variant, model.task, model.framework,
            model.source, model.provider, model.description, model.download_url,
            model.size, model.size_label, json.dumps(model.tags), json.dumps(model.hardware),
            model.status, int(model.downloaded), model.local_path, model.project_id,
            model.active_version, model.metrics.model_dump_json(),
            model.downloads, model.rating, int(model.liked),
            model.created_at or now, now,
        ),
    )

    # Upsert versions
    for v in model.versions:
        version_id = f"{model.id}_{v.version}"
        await db.execute(
            """INSERT INTO model_versions
                   (version_id, model_id, version, label, description, metrics, release_date, changelog)
               VALUES (?,?,?,?,?,?,?,?)
               ON CONFLICT(version_id) DO UPDATE SET
                   label=excluded.label, description=excluded.description,
                   release_date=excluded.release_date, changelog=excluded.changelog""",
            (
                version_id, model.id, v.version, v.label, v.description,
                json.dumps({}), v.releaseDate, v.changelog,
            ),
        )
    await db.commit()


async def bulk_upsert(models: list[Model]) -> None:
    """Batch upsert for sync operations."""
    inserted = 0
    for model in models:
        await upsert_model(model)
        inserted += 1
    log.info("registry_bulk_upsert", total=inserted)
    await audit("registry_sync", payload={"count": inserted})


async def get_model(model_id: str) -> Model | None:
    db = await get_db()
    async with db.execute("SELECT * FROM models WHERE id = ?", (model_id,)) as cur:
        row = await cur.fetchone()
    if not row:
        return None

    # Fetch versions
    async with db.execute(
        "SELECT * FROM model_versions WHERE model_id = ? ORDER BY created_at DESC",
        (model_id,),
    ) as cur:
        version_rows = await cur.fetchall()

    versions = [
        ModelVersion(
            version=r["version"],
            label=r["label"],
            description=r["description"] if "description" in r.keys() else None,
            releaseDate=r["release_date"] if "release_date" in r.keys() and r["release_date"] else "",
            changelog=r["changelog"] if "changelog" in r.keys() else None,
        )
        for r in version_rows
    ]
    return row_to_model(row, versions)


async def list_models(
    *,
    tasks: list[str] | None = None,
    frameworks: list[str] | None = None,
    hardware: list[str] | None = None,
    sources: list[str] | None = None,
    downloaded: bool | None = None,
    sort_by: str = "downloads",
    sort_dir: str = "desc",
    limit: int = 500,
    offset: int = 0,
    search: str | None = None,
    project_id: str | None = None,
) -> list[Model]:
    db = await get_db()

    # ── WHERE conditions ──────────────────────────────────────────────
    conditions: list[str] = []
    params: list[Any] = []

    # FTS5 subquery — valid SQLite syntax
    if search and search.strip():
        fts_term = f'"{search.strip()}"*'
        conditions.append(
            "m.id IN (SELECT id FROM models_fts WHERE models_fts MATCH ?)"
        )
        params.append(fts_term)

    if tasks:
        placeholders = ",".join(["?"] * len(tasks))
        conditions.append(f"m.task IN ({placeholders})")
        params.extend(tasks)

    if frameworks:
        placeholders = ",".join(["?"] * len(frameworks))
        conditions.append(f"m.framework IN ({placeholders})")
        params.extend(frameworks)

    if sources:
        placeholders = ",".join(["?"] * len(sources))
        conditions.append(f"m.source IN ({placeholders})")
        params.extend(sources)

    if hardware:
        hw_conds = ["m.hardware LIKE ?" for _ in hardware]
        conditions.append(f"({' OR '.join(hw_conds)})")
        params.extend([f"%{h}%" for h in hardware])

    if downloaded is not None:
        conditions.append("m.downloaded = ?")
        params.append(int(downloaded))

    if project_id:
        conditions.append("(m.project_id = ? OR m.project_id IS NULL)")
        params.append(project_id)

    where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    # ── Sort ──────────────────────────────────────────────────────────
    sort_col_map = {
        "downloads": "m.downloads",
        "name":      "m.name",
        "size":      "m.size",
        "rating":    "m.rating",
        "created":   "m.created_at",
    }
    col = sort_col_map.get(sort_by, "m.downloads")
    direction = "DESC" if sort_dir == "desc" else "ASC"

    sql = f"""
        SELECT m.* FROM models m
        {where_clause}
        ORDER BY {col} {direction} NULLS LAST
        LIMIT ? OFFSET ?
    """

    async with db.execute(sql, params + [limit, offset]) as cur:
        rows = await cur.fetchall()

    models = [row_to_model(row, []) for row in rows]
    if not models:
        return models

    ids = [m.id for m in models]
    placeholders = ",".join(["?"] * len(ids))
    async with db.execute(
        f"SELECT * FROM model_versions WHERE model_id IN ({placeholders}) ORDER BY created_at DESC",
        ids,
    ) as cur:
        vrows = await cur.fetchall()

    by_model: dict[str, list[ModelVersion]] = {}
    for r in vrows:
        mv = ModelVersion(
            version=r["version"],
            label=r["label"],
            description=r["description"] if "description" in r.keys() else None,
            releaseDate=r["release_date"] if "release_date" in r.keys() and r["release_date"] else "",
            changelog=r["changelog"] if "changelog" in r.keys() else None,
        )
        by_model.setdefault(r["model_id"], []).append(mv)

    return [m.model_copy(update={"versions": by_model.get(m.id, [])}) for m in models]


async def update_model_status(
    model_id: str,
    *,
    status: str | None = None,
    downloaded: bool | None = None,
    local_path: str | None = None,
) -> None:
    db = await get_db()
    now = datetime.now(timezone.utc).isoformat()
    parts: list[str] = ["updated_at = ?"]
    vals: list[Any] = [now]
    if status is not None:
        parts.append("status = ?"); vals.append(status)
    if downloaded is not None:
        parts.append("downloaded = ?"); vals.append(int(downloaded))
    if local_path is not None:
        parts.append("local_path = ?"); vals.append(local_path)
    vals.append(model_id)
    await db.execute(f"UPDATE models SET {', '.join(parts)} WHERE id = ?", vals)
    await db.commit()


async def count_models() -> int:
    db = await get_db()
    async with db.execute("SELECT COUNT(*) FROM models") as cur:
        row = await cur.fetchone()
    return row[0] if row else 0
