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

    def list(self, task: Optional[str] = None, downloaded: Optional[bool] = None) -> List[Model]:
        params = {}
        if task:
            params["task"] = task
        if downloaded is not None:
            params["downloaded"] = downloaded

        data = self._http.get("/models", params=params)
        return [Model(**m) for m in data]

    def get(self, model_id: str) -> Model:
        data = self._http.get(f"/models/{model_id}")
        return Model(**data)

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
