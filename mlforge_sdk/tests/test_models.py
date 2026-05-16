import pytest
from mlforge_sdk.models import ModelRegistry, Model, Job

def test_list_models(mock_http):
    mock_http.get.return_value = [
        {"id": "m1", "name": "Model 1", "task": "detection", "downloaded": True},
        {"id": "m2", "name": "Model 2", "task": "segmentation", "downloaded": False}
    ]

    registry = ModelRegistry(mock_http)
    models = registry.list(task="detection")

    assert len(models) == 2
    assert models[0].id == "m1"
    assert models[1].downloaded is False
    mock_http.get.assert_called_once_with("/models", params={"task": "detection"})

def test_download_model(mock_http):
    # Mock model lookup
    mock_http.get.return_value = {"id": "m1", "name": "Model 1", "version": "1.2.3"}
    # Mock download trigger
    mock_http.post.return_value = {
        "id": "job-123",
        "model_id": "m1",
        "model_name": "Model 1",
        "status": "pending",
        "progress": 0.0
    }

    registry = ModelRegistry(mock_http)
    job = registry.download("m1")

    assert isinstance(job, Job)
    assert job.id == "job-123"
    assert job.status == "pending"
    mock_http.post.assert_called_once()
