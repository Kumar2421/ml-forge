"""
projects/service.py — Active project session + model workspace linking.

Tracks which project is currently open (via the `session` DB table) and
copies freshly-downloaded model files into the project's models/ folder
so the benchmark engine and other workspaces can locate them.
"""
from __future__ import annotations

import os
import shutil
import uuid
from pathlib import Path
from datetime import datetime, timezone

from database.connection import get_db
from observability.logger import get_logger, audit
from models.model import Model, ModelMetrics
from registry.registry import upsert_model

log = get_logger("projects.service")


async def import_local_model(
    name: str,
    task: str,
    framework: str,
    source_file_path: str
) -> Model:
    """Import a local model file into the active project."""
    project_id = await get_active_project_id()
    project_path = await get_active_project_path()
    
    if not project_id or not project_path:
        raise ValueError("No active project found. Please open a project first.")

    src = Path(source_file_path)
    if not src.exists():
        raise FileNotFoundError(f"Source model file not found: {source_file_path}")

    # Create destination directory in project
    model_id = f"local-{uuid.uuid4().hex[:12]}"
    dest_dir = Path(project_path) / "models" / model_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    
    dest_path = dest_dir / src.name
    shutil.copy2(src, dest_path)
    
    # Calculate size
    size_bytes = dest_path.stat().st_size
    size_label = f"{size_bytes / (1024*1024):.1f} MB" if size_bytes > 1024*1024 else f"{size_bytes / 1024:.1f} KB"

    # Create model entry
    now = datetime.now(timezone.utc).isoformat()
    model = Model(
        id=model_id,
        name=name,
        task=task,
        framework=framework,
        source="local",
        provider="Local Import",
        size=size_bytes,
        size_label=size_label,
        local_path=str(dest_path),
        project_id=project_id,
        downloaded=True,
        status="cached",
        created_at=now,
        updated_at=now,
        metrics=ModelMetrics()
    )
    
    await upsert_model(model)
    await audit("model_imported_locally", model_id=model_id, payload={"name": name, "project_id": project_id})
    log.info("model_imported_locally", model_id=model_id, name=name, path=str(dest_path))
    
    return model


# ── Session helpers ───────────────────────────────────────────────────────────

async def set_active_project(project_id: str, project_path: str) -> None:
    """Persist the currently open project in the session table."""
    db = await get_db()
    await db.execute(
        "INSERT INTO session (key, value) VALUES ('active_project_id', ?)"
        " ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (project_id,),
    )
    await db.execute(
        "INSERT INTO session (key, value) VALUES ('active_project_path', ?)"
        " ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (project_path,),
    )
    await db.commit()
    log.info("active_project_set", project_id=project_id, path=project_path)


async def get_active_project_id() -> str | None:
    """Return the ID of the currently open project, or None."""
    db = await get_db()
    async with db.execute(
        "SELECT value FROM session WHERE key = 'active_project_id'"
    ) as cur:
        row = await cur.fetchone()
    return row["value"] if row else None


async def get_active_project_path() -> str | None:
    """Return the filesystem path of the currently open project, or None."""
    db = await get_db()
    async with db.execute(
        "SELECT value FROM session WHERE key = 'active_project_path'"
    ) as cur:
        row = await cur.fetchone()
    return row["value"] if row else None


# ── Workspace model linking ───────────────────────────────────────────────────

async def link_model_to_active_project(model_id: str, source_path: str) -> None:
    """Copy the downloaded model file into the active project's models/ folder.

    This is a best-effort operation — if no project is open, or if the copy
    fails for any reason, we log and continue rather than failing the download.
    """
    project_path = await get_active_project_path()
    if not project_path:
        log.debug("link_model_skipped_no_project", model_id=model_id)
        return

    src = Path(source_path)
    if not src.exists():
        log.warning("link_model_source_missing", model_id=model_id, path=source_path)
        return

    dest_dir = Path(project_path) / "models" / model_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / src.name

    if dest.exists():
        log.debug("link_model_already_exists", model_id=model_id, dest=str(dest))
        return

    try:
        shutil.copy2(src, dest)
        log.info("model_linked_to_project", model_id=model_id, project=project_path, dest=str(dest))
    except OSError as exc:
        log.warning("link_model_copy_failed", model_id=model_id, error=str(exc))


async def link_dataset_to_active_project(dataset_id: str, source_path: str) -> None:
    """Copy the imported dataset folder into the active project's datasets/ folder.

    This is a best-effort operation — if no project is open, or if the copy
    fails for any reason, we log and continue rather than failing the import.
    """
    project_path = await get_active_project_path()
    if not project_path:
        log.debug("link_dataset_skipped_no_project", dataset_id=dataset_id)
        return

    src = Path(source_path)
    if not src.exists():
        log.warning("link_dataset_source_missing", dataset_id=dataset_id, path=source_path)
        return

    dest_dir = Path(project_path) / "datasets" / dataset_id
    
    if dest_dir.exists():
        log.debug("link_dataset_already_exists", dataset_id=dataset_id, dest=str(dest_dir))
        return

    try:
        if src.is_dir():
            shutil.copytree(src, dest_dir, dirs_exist_ok=True)
        else:
            # If it's a file (e.g. zip that wasn't extracted yet), just copy it
            dest_dir.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest_dir)
            
        log.info("dataset_linked_to_project", dataset_id=dataset_id, project=project_path, dest=str(dest_dir))
        return dest_dir
    except OSError as exc:
        log.warning("link_dataset_copy_failed", dataset_id=dataset_id, error=str(exc))
        return None
