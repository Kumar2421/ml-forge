from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict

from .http import HttpClient

class Dataset(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    name: str
    format: Optional[str] = None
    images: int = 0
    classes: int = 0
    size_label: str = "0 MB"


class DatasetJob(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    type: str
    status: str
    dataset_id: str
    dataset_name: str
    progress: float = 0.0
    message: str = ""
    error: Optional[str] = None


class ImportResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    job_id: str
    dataset_id: str
    status: str
    message: str

class DatasetClient:
    def __init__(self, http: HttpClient):
        self._http = http

    def list(
        self,
        *,
        task: Optional[str] = None,
        format: Optional[str] = None,
        source: Optional[str] = None,
        status: Optional[str] = None,
        search: Optional[str] = None,
        starred: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dataset]:
        params: Dict[str, Any] = {
            "task": task,
            "format": format,
            "source": source,
            "status": status,
            "search": search,
            "starred": starred,
            "limit": limit,
            "offset": offset,
        }
        data = self._http.get("/datasets", params=params)
        return [Dataset(**d) for d in data]

    def get(self, dataset_id: str) -> Dataset:
        data = self._http.get(f"/datasets/{dataset_id}")
        return Dataset(**data)

    def import_dataset(self, dataset_id: str, payload: Dict[str, Any]) -> ImportResponse:
        data = self._http.post(f"/datasets/{dataset_id}/import", json_body=payload)
        return ImportResponse(**data)

    def list_jobs(self, *, limit: int = 50) -> List[DatasetJob]:
        data = self._http.get("/datasets/jobs", params={"limit": limit})
        return [DatasetJob(**j) for j in data]

    def get_job(self, job_id: str) -> DatasetJob:
        data = self._http.get(f"/datasets/jobs/{job_id}")
        return DatasetJob(**data)

    def stop_job(self, job_id: str) -> Dict[str, Any]:
        return self._http.post(f"/datasets/jobs/{job_id}/stop")

    def pause_job(self, job_id: str) -> Dict[str, Any]:
        return self._http.post(f"/datasets/jobs/{job_id}/pause")

    def resume_job(self, job_id: str) -> Dict[str, Any]:
        return self._http.post(f"/datasets/jobs/{job_id}/resume")

    def toggle_star(self, dataset_id: str) -> Dict[str, Any]:
        return self._http.post(f"/datasets/{dataset_id}/star")

    def delete(self, dataset_id: str, *, delete_files: bool = False) -> Dict[str, Any]:
        return self._http.delete(f"/datasets/{dataset_id}", params={"delete_files": delete_files})

    def search_roboflow(
        self,
        api_key: str,
        query: str,
        workspace: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> List[Dataset]:
        payload = {
            "api_key": api_key,
            "query": query,
            "workspace": workspace,
            "page": page,
            "page_size": page_size,
        }
        data = self._http.post("/datasets/search/roboflow", json_body=payload)
        return [Dataset(**d) for d in data]

    def sync_roboflow(self, api_key: str, workspace: str) -> Dict[str, Any]:
        params = {"api_key": api_key, "workspace": workspace}
        return self._http.post("/datasets/sync/roboflow", params=params)
