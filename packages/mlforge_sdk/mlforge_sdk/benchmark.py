from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from .http import HttpClient

class BenchmarkResult(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    job_id: str
    metrics: Dict[str, Any]
    telemetry_summary: Dict[str, Any]
    created_at: Optional[str] = None
    model_id: Optional[str] = None
    dataset_id: Optional[str] = None
    task: Optional[str] = None
    framework: Optional[str] = None
    hardware: Optional[str] = None
    precision: Optional[str] = None


class BenchmarkJob(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    model_id: str
    dataset_id: str
    task: str
    framework: str
    hardware: str
    precision: str
    batch_size: int
    status: str
    progress: float = 0.0
    logs: List[str] = Field(default_factory=list)


class BenchmarkRunResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    job_id: str
    status: str
    message: str

class BenchmarkClient:
    def __init__(self, http: HttpClient):
        self._http = http

    def list_results(self) -> List[BenchmarkResult]:
        data = self._http.get("/benchmark/results/all", params={"limit": 100})
        return [BenchmarkResult(**r) for r in data]

    def list_jobs(
        self,
        *,
        status: Optional[str] = None,
        model_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[BenchmarkJob]:
        params: Dict[str, Any] = {"status": status, "model_id": model_id, "limit": limit}
        data = self._http.get("/benchmark/jobs", params=params)
        return [BenchmarkJob(**j) for j in data]

    def run(self, ctx: Dict[str, Any]) -> BenchmarkRunResponse:
        data = self._http.post("/benchmark/run", json_body=ctx)
        return BenchmarkRunResponse(**data)

    def validate(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        return self._http.post("/benchmark/validate", json_body=ctx)

    def get_job(self, job_id: str) -> BenchmarkJob:
        data = self._http.get(f"/benchmark/{job_id}")
        return BenchmarkJob(**data)

    def get_result(self, job_id: str) -> BenchmarkResult:
        data = self._http.get(f"/benchmark/{job_id}/result")
        return BenchmarkResult(**data)
