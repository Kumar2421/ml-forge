from typing import List, Optional
from pydantic import BaseModel

from .http import HttpClient

class Model(BaseModel):
    id: str
    name: str
    version: Optional[str] = "1.0.0"
    task: Optional[str] = None
    framework: Optional[str] = None
    downloaded: bool = False
    local_path: Optional[str] = None

class Job(BaseModel):
    id: str
    model_id: str
    model_name: str
    status: str
    progress: float = 0.0

class ModelRegistry:
    def __init__(self, http: HttpClient):
        self._http = http

    def list(
        self,
        task: Optional[str] = None,
        downloaded: Optional[bool] = None,
        search: Optional[str] = None,
        framework: Optional[List[str]] = None,
        hardware: Optional[List[str]] = None,
        source: Optional[List[str]] = None,
        sort_by: str = "downloads",
        sort_dir: str = "desc",
        limit: int = 200,
        offset: int = 0,
    ) -> List[Model]:
        params: dict = {
            "sort_by": sort_by,
            "sort_dir": sort_dir,
            "limit": limit,
            "offset": offset,
        }
        if task:
            params["task"] = task
        if downloaded is not None:
            params["downloaded"] = downloaded
        if search:
            params["search"] = search
        if framework:
            params["framework"] = framework
        if hardware:
            params["hardware"] = hardware
        if source:
            params["source"] = source

        data = self._http.post("/models", json_body=params)
        return [Model(**m) for m in data]

    def get(self, model_id: str) -> Model:
        data = self._http.post("/models", json_body={"model_id": model_id})
        if isinstance(data, list) and data:
            return Model(**data[0])
        raise ApiError(f"Model {model_id!r} not found via gateway")

    def download(self, model_id: str) -> Job:
        """Trigger a model download job"""
        model = self.get(model_id)
        payload = {
            "model_id": model.id,
            "model_name": model.name,
            "version": getattr(model, 'version', '1.0.0')
        }
        data = self._http.post("/download", json_body=payload)
        return Job(**data)

    def get_job(self, job_id: str) -> Job:
        """Get status of a download job"""
        data = self._http.get(f"/jobs/{job_id}")
        return Job(**data)
