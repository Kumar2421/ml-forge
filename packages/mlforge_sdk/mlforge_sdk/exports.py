from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict

from .http import HttpClient


class ExportJob(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    project_id: str
    run_id: str
    format: str
    status: str
    progress: Optional[float] = None
    artifact_url: Optional[str] = None
    created_at: Optional[str] = None
    completed_at: Optional[str] = None


class ExportsClient:
    def __init__(self, http: HttpClient):
        self._http = http

    def list(
        self,
        *,
        project_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[ExportJob]:
        params: Dict[str, Any] = {"project_id": project_id, "limit": limit, "offset": offset}
        data = self._http.get("/exports", params=params)
        return [ExportJob(**e) for e in data]

    def get(self, export_id: str) -> ExportJob:
        data = self._http.get(f"/exports/{export_id}")
        return ExportJob(**data)

    def start(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        data = self._http.post("/exports", json_body=ctx)
        return data

    def cancel(self, export_id: str) -> None:
        self._http.post(f"/exports/{export_id}/cancel")

    def download(self, export_id: str) -> bytes:
        """Download export artifact as bytes."""
        import requests

        url = f"{self._http._base_url}/exports/{export_id}/download"
        token = getattr(self._http, "_token", None)
        headers = {"Authorization": f"Bearer {token}"} if token else {}

        resp = requests.get(url, headers=headers)
        resp.raise_for_status()
        return resp.content
