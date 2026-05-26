import base64
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from .http import HttpClient

class InferenceResult(BaseModel):
    model_config = ConfigDict(extra="ignore")
    request_id: str
    model_id: str
    adapter_type: str
    timestamp: float
    preprocess_ms: float = 0.0
    inference_ms: float = 0.0
    postprocess_ms: float = 0.0
    total_ms: float = 0.0
    detections: List[Dict[str, Any]] = Field(default_factory=list)
    text_output: Optional[str] = None
    raw_output: Any = None
    pipeline: List[Dict[str, Any]] = Field(default_factory=list)
    quality_score: Optional[float] = None
    error: Optional[str] = None
    status: str = "ok"

class InferenceClient:
    def __init__(self, http: HttpClient):
        self._http = http

    @staticmethod
    def _file_to_base64(path: str) -> str:
        data = Path(path).read_bytes()
        return base64.b64encode(data).decode("utf-8")

    def run_request(self, payload: Dict[str, Any]) -> InferenceResult:
        data = self._http.post("/inference/run", json_body=payload)
        return InferenceResult(**data)

    def run(
        self,
        model_id: str,
        image_path: Optional[str] = None,
        *,
        adapter_type: str = "auto",
        precision: str = "FP16",
        image_base64: Optional[str] = None,
        text_input: Optional[str] = None,
        video_url: Optional[str] = None,
        rtsp_url: Optional[str] = None,
        yolo_config: Optional[Dict[str, Any]] = None,
        transformers_config: Optional[Dict[str, Any]] = None,
        onnx_config: Optional[Dict[str, Any]] = None,
        custom_config: Optional[Dict[str, Any]] = None,
        run_mode: str = "single",
    ) -> InferenceResult:
        """Compatibility-friendly wrapper.

        If you pass image_path, it is converted to base64 and sent as JSON.
        """
        if image_base64 is None and image_path is not None:
            image_base64 = self._file_to_base64(image_path)

        payload: Dict[str, Any] = {
            "model_id": model_id,
            "adapter_type": adapter_type,
            "precision": precision,
            "image_base64": image_base64,
            "text_input": text_input,
            "video_url": video_url,
            "rtsp_url": rtsp_url,
            "yolo_config": yolo_config,
            "transformers_config": transformers_config,
            "onnx_config": onnx_config,
            "custom_config": custom_config,
            "run_mode": run_mode,
        }
        return self.run_request(payload)
