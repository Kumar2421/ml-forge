from typing import Any, Dict, List, Optional
from pydantic import BaseModel

from .http import HttpClient

class TrainRun(BaseModel):
    id: str
    run_number: int
    model_id: str
    model_name: str
    dataset_id: str
    dataset_name: str
    task: str
    status: str
    epochs_done: int
    total_epochs: int
    best_metric: Dict[str, float]
    final_loss: float
    duration: str
    created_at: float
    completed_at: Optional[float] = None
    hyperparams: Dict[str, Any]

class TrainingClient:
    def __init__(self, http: HttpClient):
        self._http = http

    def list_runs(self) -> List[TrainRun]:
        data = self._http.get("/train/runs")
        return [TrainRun(**r) for r in data]

    def start(self, model_id: str, dataset_id: str, task: str, 
              params: Dict[str, Any], project_id: str = "default") -> Dict[str, Any]:
        payload = {
            "model_id": model_id,
            "dataset_id": dataset_id,
            "task": task,
            "hyperparams": params,
            "augmentation": {},
            "scheduler": {},
            "project_id": project_id
        }
        return self._http.post("/train/start", json_body=payload)

    def get_history(self, run_id: str) -> List[Dict[str, Any]]:
        data = self._http.get(f"/train/runs/{run_id}/history")
        if data is None:
            return []
        return data
