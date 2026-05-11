"""
database/connection.py — Async SQLite connection & migration bootstrap.
Single module responsible for DB lifecycle. All queries use this pool.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import aiosqlite

from config import settings

# Module-level connection (shared within the process)
_db: aiosqlite.Connection | None = None
_lock = asyncio.Lock()


async def get_db() -> aiosqlite.Connection:
    """Return the singleton async database connection."""
    global _db
    async with _lock:
        if _db is None:
            _db = await _open_connection()
    return _db


async def _open_connection() -> aiosqlite.Connection:
    settings.ensure_dirs()
    conn = await aiosqlite.connect(settings.db_path, check_same_thread=False)
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA journal_mode=WAL")
    await conn.execute("PRAGMA foreign_keys=ON")
    await conn.execute("PRAGMA synchronous=NORMAL")
    await conn.execute("PRAGMA cache_size=-65536")   # 64 MB page cache
    await _run_migrations(conn)
    await conn.commit()
    return conn


async def _run_migrations(conn: aiosqlite.Connection) -> None:
    """Apply all schema files idempotently (CREATE IF NOT EXISTS)."""
    base = Path(__file__).parent
    
    # ── STEP 1: Ensure basic tables exist ──
    for schema_file in ["schema.sql", "dataset_schema.sql", "benchmark_schema.sql"]:
        path = base / schema_file
        if path.exists():
            sql = path.read_text(encoding="utf-8")
            await conn.executescript(sql)

    # ── STEP 2: Legacy Alterations ──
    # Check 'models' table for specific columns
    async with conn.execute("PRAGMA table_info(models)") as cur:
        cols = {r[1] for r in await cur.fetchall()}
    
    if cols: # only if table exists
        if "download_url" not in cols:
            await conn.execute("ALTER TABLE models ADD COLUMN download_url TEXT")

        if "active_version" not in cols:
            await conn.execute("ALTER TABLE models ADD COLUMN active_version TEXT")

        if "metrics" not in cols:
            await conn.execute("ALTER TABLE models ADD COLUMN metrics TEXT NOT NULL DEFAULT '{}' ")

    # Check 'datasets' table for new columns (e.g. active_version)
    async with conn.execute("PRAGMA table_info(datasets)") as cur:
        ds_cols = {r[1] for r in await cur.fetchall()}
    
    if ds_cols:
        if "active_version" not in ds_cols:
            await conn.execute("ALTER TABLE datasets ADD COLUMN active_version TEXT NOT NULL DEFAULT 'v1'")
        if "roboflow_id" not in ds_cols:
            await conn.execute("ALTER TABLE datasets ADD COLUMN roboflow_id TEXT")
        if "health_score" not in ds_cols:
            await conn.execute("ALTER TABLE datasets ADD COLUMN health_score INTEGER NOT NULL DEFAULT 0")

    # Check 'models' table for project_id
    async with conn.execute("PRAGMA table_info(models)") as cur:
        model_cols = {r[1] for r in await cur.fetchall()}
    
    if model_cols and "project_id" not in model_cols:
        await conn.execute("ALTER TABLE models ADD COLUMN project_id TEXT REFERENCES projects(id) ON DELETE CASCADE")

    # Clean up any lingering temporary tables from failed legacy migrations
    # COMMIT is essential here to ensure background jobs see the clean state immediately
    # We use a try/except block to avoid "no such table" errors if the table is already gone
    try:
        await conn.execute("DROP TABLE IF EXISTS datasets_old")
    except:
        pass
    
    try:
        await conn.execute("DROP TABLE IF EXISTS dataset_jobs_old")
    except:
        pass

    await conn.commit()

async def close_db() -> None:
    global _db
    async with _lock:
        if _db is not None:
            await _db.close()
            _db = None
