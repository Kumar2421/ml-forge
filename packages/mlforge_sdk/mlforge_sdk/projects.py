from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict

from .http import HttpClient


class Project(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    name: str
    path: str
    created_at: str
    last_opened: str
    status: str = "idle"


class ProjectsClient:
    def __init__(self, http: HttpClient):
        self._http = http

    def list(self, *, limit: int = 200, offset: int = 0) -> List[Project]:
        data = self._http.get("/projects", params={"limit": limit, "offset": offset})
        return [Project(**p) for p in data]

    def upsert(self, project: Project) -> Project:
        data = self._http.post("/projects", json_body=project.model_dump())
        return Project(**data)

    def open(self, project_id: str) -> None:
        self._http.post(f"/projects/{project_id}/open")

    def delete(self, project_id: str) -> None:
        self._http.delete(f"/projects/{project_id}")
