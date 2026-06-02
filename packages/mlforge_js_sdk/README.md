# @mlforge/sdk

TypeScript/JavaScript SDK for MLForge Studio. Access training, inference, datasets, benchmarks, and model management programmatically.

## Installation

```bash
npm install @mlforge/sdk
```

## Quick Start

```typescript
import { MLForge } from "@mlforge/sdk";

// Initialize (requires MLForge Studio running on localhost:8005)
const forge = new MLForge();

// List available models
const models = await forge.models.list();
console.log(models);
```

## Authentication

Authenticate with a Supabase JWT token:

```typescript
const forge = new MLForge();
forge.authenticate(token);

// Or pass token on init
const forge = new MLForge({ token: "your-jwt-token" });
```

## Core Workflow

### 1. Create a Project (Required)

All operations (training, inference, benchmarking) require a project:

```typescript
const project = await forge.projects.create({ name: "my-project" });
console.log(project.id); // Use this for all operations
```

### 2. Select a Model

```typescript
const models = await forge.models.list({ task: "detection" });
const model = models[0];
```

### 3. Import or Select a Dataset

```typescript
// List datasets
const datasets = await forge.datasets.list();

// Or import from Roboflow
const job = await forge.datasets.import("roboflow-dataset-id", {
  project_id: project.id,
  api_key: "your-roboflow-key",
});
```

### 4. Train a Model

```typescript
const trainRun = await forge.training.start({
  project_id: project.id,
  model_id: model.id,
  dataset_id: dataset.id,
  task: "detection",
  epochs: 50,
  batch_size: 16,
  device: "cuda",
});

// Monitor progress
const run = await forge.training.get(trainRun.run_id);
console.log(`Epoch ${run.epoch}/${run.total_epochs}, Loss: ${run.metrics.loss}`);
```

### 5. Run Inference

```typescript
const result = await forge.inference.run({
  project_id: project.id,
  model_id: model.id,
  task: "detection",
  image_base64: imageBase64,
});

console.log(result.detections); // [ { class_name, confidence, bbox } ]
```

### 6. Benchmark Models

```typescript
const benchmark = await forge.benchmark.run({
  project_id: project.id,
  model_id: "yolov8n",
  dataset_id: dataset.id,
  task: "detection",
  framework: "pytorch",
});

const result = await forge.benchmark.getResult(benchmark.job_id);
console.log(result.metrics); // { mAP, latency_ms, fps, ... }
```

### 7. Export Results

```typescript
const export_job = await forge.exports.start({
  project_id: project.id,
  run_id: trainRun.run_id,
  format: "onnx",
  include_weights: true,
});

// Wait for completion, then download
const blob = await forge.exports.download(export_job.job_id);
```

## API Reference

### MLForge

Main factory class for SDK.

#### Methods

- `authenticate(token: string)` — Set auth token
- `isAuthenticated(): boolean` — Check auth status
- `clearAuth()` — Remove token

#### Properties

- `projects` — ProjectsClient
- `models` — ModelsClient
- `datasets` — DatasetsClient
- `training` — TrainingClient
- `inference` — InferenceClient
- `benchmark` — BenchmarkClient
- `exports` — ExportsClient

### ProjectsClient

Manage projects.

```typescript
await forge.projects.create({ name: "project-name" });
await forge.projects.list();
await forge.projects.get(projectId);
await forge.projects.open(projectId);
await forge.projects.delete(projectId);
```

### ModelsClient

Discover and download models.

```typescript
await forge.models.list({ task?: string; framework?: string; query?: string });
await forge.models.get(modelId);
await forge.models.download(modelId); // Returns { job_id }
await forge.models.getJob(jobId);
```

### DatasetsClient

Import and manage datasets.

```typescript
await forge.datasets.list({ task?, format?, search?, limit?, offset? });
await forge.datasets.get(datasetId);
await forge.datasets.import(datasetId, { project_id, ... });
await forge.datasets.getAnalytics(datasetId);
await forge.datasets.listJobs();
await forge.datasets.getJob(jobId);
await forge.datasets.searchRoboflow({ api_key, query?, workspace? });
await forge.datasets.syncRoboflow({ api_key, workspace });
```

### TrainingClient

Train models.

```typescript
await forge.training.start({
  project_id,
  model_id,
  dataset_id,
  task: "detection",
  epochs?: number;
  batch_size?: number;
  lr?: number;
  // ...
});
await forge.training.get(runId);
await forge.training.list();
await forge.training.stop(runId);
await forge.training.pause(runId);
await forge.training.resume(runId);
await forge.training.getHistory(runId); // Returns epoch metrics
```

### InferenceClient

Run inference.

```typescript
await forge.inference.run({
  project_id,
  model_id,
  task: "detection",
  image_base64?: string;
  image_path?: string;
  conf_threshold?: number;
  // ...
});
await forge.inference.getSchema(task);
```

### BenchmarkClient

Compare model performance.

```typescript
await forge.benchmark.run({
  project_id,
  model_id,
  dataset_id?,
  task?,
  framework?,
  // ...
});
await forge.benchmark.listResults();
await forge.benchmark.listJobs();
await forge.benchmark.getJob(jobId);
await forge.benchmark.getResult(jobId);
```

### ExportsClient

Export trained models.

```typescript
await forge.exports.start({
  project_id,
  run_id,
  format: "onnx" | "tensorrt" | "coreml" | "tflite",
  include_weights?: boolean;
  include_metadata?: boolean;
});
await forge.exports.list({ project_id? });
await forge.exports.get(exportId);
await forge.exports.cancel(exportId);
await forge.exports.download(exportId); // Returns Blob
```

## Error Handling

```typescript
import { ApiError } from "@mlforge/sdk";

try {
  await forge.training.start({ ... });
} catch (error) {
  if (error instanceof ApiError) {
    if (error.status === 401) {
      console.log("Authentication required");
    } else if (error.status === 402) {
      console.log("Rate limit exceeded");
    }
  }
}
```

## Configuration

```typescript
const forge = new MLForge({
  baseUrl: "http://127.0.0.1",      // Default: http://127.0.0.1:8005
  timeout: 30_000,                   // Request timeout in ms (default: 30s)
  token: "jwt-token",                // Supabase JWT token
});
```

## Zero Dependencies

This SDK has zero external dependencies. It uses native Fetch API for HTTP requests and works in both Node.js and browser environments.

## License

MIT
