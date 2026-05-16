import pytest
from mlforge_sdk.inference import InferenceClient, InferenceResult

def test_inference_run_success(mock_http):
    # Setup mock response
    mock_http.post.return_value = {
        "request_id": "test-req",
        "model_id": "test-model",
        "adapter_type": "yolo",
        "timestamp": 123456789.0,
        "total_ms": 150.5,
        "status": "ok",
        "detections": [
            {"x1": 10, "y1": 10, "x2": 50, "y2": 50, "confidence": 0.9, "class_id": 1, "class_name": "cat"}
        ]
    }

    client = InferenceClient(mock_http)
    
    # We mock the _file_to_base64 to avoid file IO in unit tests
    # Or just pass image_base64 directly
    result = client.run(
        model_id="test-model",
        image_base64="dGVzdC1pbWFnZQ==", # "test-image" in base64
        adapter_type="yolo",
        precision="FP16"
    )

    assert isinstance(result, InferenceResult)
    assert result.status == "ok"
    assert len(result.detections) == 1
    assert result.detections[0]["class_name"] == "cat"
    
    # Verify HTTP call
    mock_http.post.assert_called_once()
    args, kwargs = mock_http.post.call_args
    assert args[0] == "/inference/run"
    assert kwargs["json_body"]["model_id"] == "test-model"

def test_inference_run_error(mock_http):
    mock_http.post.return_value = {
        "request_id": "err-req",
        "model_id": "bad-model",
        "adapter_type": "yolo",
        "timestamp": 123456789.0,
        "status": "error",
        "error": "Model failed to load"
    }

    client = InferenceClient(mock_http)
    result = client.run(model_id="bad-model")

    assert result.status == "error"
    assert result.error == "Model failed to load"
