"""api/routes/projects.py — /projects REST endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from models.project import Project
from observability.logger import audit
from projects.registry import delete_project, get_project, list_projects, touch_last_opened, upsert_project
from projects.service import set_active_project


router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=list[Project])
async def projects_list(
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> list[Project]:
    projects = await list_projects(limit=limit, offset=offset)
    await audit("api_list_projects", payload={"count": len(projects)})
    return projects


@router.post("", response_model=Project)
async def projects_upsert(project: Project) -> Project:
    # Ensure project.created_at and last_opened are set if missing
    if not project.created_at:
        project.created_at = datetime.now(timezone.utc).isoformat()
    if not project.last_opened:
        project.last_opened = datetime.now(timezone.utc).isoformat()
        
    await upsert_project(project)
    await audit("api_upsert_project", payload={"project_id": project.id})
    return project


@router.post("/{project_id}/open", status_code=204, response_model=None)
async def projects_open(project_id: str) -> None:
    await touch_last_opened(project_id)
    project = await get_project(project_id)
    if project:
        await set_active_project(project.id, project.path)
    await audit("api_open_project", payload={"project_id": project_id})


@router.delete("/{project_id}", status_code=204, response_model=None)
async def projects_delete(project_id: str) -> None:
    ok = await delete_project(project_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    await audit("api_delete_project", payload={"project_id": project_id})

