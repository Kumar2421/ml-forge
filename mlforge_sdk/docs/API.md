# MLForge SDK API Reference

The `mlforge_sdk` provides a high-level Python interface to the MLForge ecosystem.

## Initialization

```python
from mlforge_sdk import MLForge

# Connect to local backend (default)
sdk = MLForge()

# Connect to a remote backend
sdk = MLForge(host="http://192.168.1.50", port=8005)
```

## Models Interface (`sdk.models`)

### `list(**filters)`
List models from the registry.
- **Filters**: `task`, `downloaded`, `search`, `framework`, `hardware`, `source`.

### `download(model_id)`
Trigger a model download job. Returns a `Job` object.

### `get_job(job_id)`
Get status and progress of a background job.

## Datasets Interface (`sdk.datasets`)

### `list(limit=50, offset=0)`
List local datasets.

### `import_dataset(dataset_id, payload)`
Trigger a dataset import. Returns an `ImportResponse`.

### `get_analytics(dataset_id)`
Retrieve health and distribution metrics for a dataset.

## Training Interface (`sdk.training`)

### `list_runs(project_id)`
List all training runs for a specific project.

### `start_run(config)`
Trigger a new training run based on a configuration object.
```python
config = {
    "model_id": "yolov8n",
    "dataset_id": "my-custom-dataset",
    "epochs": 100,
    "imgsz": 640
}
sdk.training.start_run(config)
```
