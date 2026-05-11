"""
api/routes/models.py — /models REST endpoints.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Form
from models.model import Model
from observability.logger import audit, get_logger
from registry.registry import count_models, get_model, list_models
from projects.service import get_active_project_id, import_local_model
from projects.registry import get_project
from pathlib import Path
import os
import tempfile

log = get_logger("api.models")
router = APIRouter(prefix="/models", tags=["models"])


@router.get("", response_model=list[Model])
async def index(
    search:     Annotated[str | None, Query()] = None,
    task:       Annotated[list[str] | None, Query()] = None,
    framework:  Annotated[list[str] | None, Query()] = None,
    hardware:   Annotated[list[str] | None, Query()] = None,
    source:     Annotated[list[str] | None, Query()] = None,
    downloaded: Annotated[bool | None, Query()] = None,
    sort_by:    Annotated[str, Query()] = "downloads",
    sort_dir:   Annotated[str, Query()] = "desc",
    limit:      Annotated[int, Query(ge=1, le=1000)] = 200,
    offset:     Annotated[int, Query(ge=0)] = 0,
    project_id: Annotated[str | None, Query()] = None,
) -> list[Model]:
    """
    List and search models.
    Supports FTS search + server-side filtering.
    Target: < 100ms for up to 5 000 models.
    """
    effective_project_id = project_id or await get_active_project_id()

    models = await list_models(
        search=search,
        tasks=task,
        frameworks=framework,
        hardware=hardware,
        sources=source,
        downloaded=downloaded,
        sort_by=sort_by,
        sort_dir=sort_dir,
        limit=limit,
        offset=offset,
        project_id=effective_project_id,
    )

    # If we have an active project, derive cache state from its workspace.
    # This makes "downloaded" and "local_path" reflect the *current project*.
    if effective_project_id:
        proj = await get_project(effective_project_id)
        if proj:
            project_models_dir = Path(proj.path) / "models"

            updated: list[Model] = []
            for m in models:
                model_dir = project_models_dir / m.id
                if model_dir.exists() and model_dir.is_dir():
                    # Pick the first file in the model directory (best-effort).
                    found_file: str | None = None
                    try:
                        for p in model_dir.rglob("*"):
                            if p.is_file():
                                found_file = str(p)
                                break
                    except Exception:
                        found_file = None

                    if found_file:
                        updated.append(m.model_copy(update={"downloaded": True, "local_path": found_file}))
                        continue

                # Not present in this project → treat as not cached for this project.
                updated.append(m.model_copy(update={"downloaded": False, "local_path": None}))

            models = updated

    await audit("api_list_models", payload={"count": len(models), "search": search})
    return models


@router.post("/import", response_model=Model)
async def import_model(
    name: Annotated[str, Form()],
    task: Annotated[str, Form()],
    framework: Annotated[str, Form()],
    file: UploadFile = File(...),
) -> Model:
    """Import a local model file into the active project."""
    # Save uploaded file to a temporary location
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename or "")[1]) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        model = await import_local_model(
            name=name,
            task=task,
            framework=framework,
            source_file_path=tmp_path
        )
        return model
    except Exception as e:
        log.error("model_import_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


@router.get("/{model_id}", response_model=Model)
async def detail(model_id: str) -> Model:
    model = await get_model(model_id)
    if not model:
        raise HTTPException(status_code=404, detail=f"Model '{model_id}' not found")
    await audit("api_get_model", model_id=model_id)
    return model
