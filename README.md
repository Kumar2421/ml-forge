<div align="center">

# ⚒️ MLForge

**The Unified AI/ML Engineering Platform — Local-First, Full Lifecycle.**

[![PyPI](https://img.shields.io/pypi/v/mlforge-sdk?label=pip%20install%20mlforge-sdk&color=7c3aed)](https://pypi.org/project/mlforge-sdk/)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-Proprietary-red.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey.svg)](https://mlforge.in)
[![Discord](https://img.shields.io/badge/community-Discord-5865F2.svg)](https://mlforge.in/discord)

*Model Zoo · Dataset Management · Training · Inference · Benchmark · Logs — all in one.*

**[Website](https://mlforge.in) · [Docs](https://mlforge.in/docs) · [Desktop App](https://mlforge.in/download) · [Discord](https://mlforge.in/discord)**

</div>

---

## What is MLForge?

MLForge is an open AI/ML engineering ecosystem designed for ML engineers who want the **full training lifecycle in a single tool** — without depending on cloud infrastructure.

> "Stop switching between HuggingFace, Weights & Biases, Roboflow, and custom scripts. MLForge is all of it."

```
Discover Models → Import Datasets → Train → Test Inference → Benchmark → Ship
      ↑                                                                      ↑
  600+ models                                                       Local GPU
  HF + Roboflow                                                      No cloud
  + local import                                                   required
```

### The Core Difference

| | MLForge | Roboflow | HuggingFace | Weights & Biases | AWS SageMaker |
|--|---------|---------|------------|-----------------|---------------|
| Model Zoo | ✅ | ❌ | ✅ | ❌ | ✅ |
| Dataset Management | ✅ | ✅ | ✅ | ❌ | ⚠️ |
| Local GPU Training | ✅ | ❌ | ❌ | ❌ | ❌ |
| Training UI | ✅ | ❌ | ❌ | ❌ | ⚠️ |
| Inference Testing | ✅ | ✅ | ⚠️ | ❌ | ⚠️ |
| Benchmark Suite | ✅ | ❌ | ❌ | ❌ | ❌ |
| Desktop App | ✅ | ❌ | ❌ | ❌ | ❌ |
| Python SDK | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Data stays local** | ✅ | ❌ | ❌ | ❌ | ❌ |
| **No cloud required** | ✅ | ❌ | ❌ | ❌ | ❌ |

---

## Installation

```bash
pip install mlforge-sdk mlforge-cli
```

Start the local studio:

```bash
mlforge start
# Studio running at http://localhost:8005
# Desktop dashboard opens automatically
```

---

## SDK Quickstart

### 5-line Training Workflow

```python
from mlforge_sdk import MLForge

forge = MLForge()  # connects to local engine

run = forge.train.start(
    model_id="yolov8-nano-detection",
    dataset_id="construction-safety-v2",
    task="detection",
    params={"epochs": 100, "batchSize": 16, "lr": 0.01, "imgSize": 640}
)

print(f"Training started: run #{run['run_number']}")
```

### Full Detection Workflow

```python
from mlforge_sdk import MLForge
import time

forge = MLForge()

# 1. Find a model
models = forge.models.list(task="object-detection", downloaded=True)
model = models[0]
print(f"Using: {model.name}")

# 2. Check your datasets
datasets = forge.datasets.list()
dataset = next(d for d in datasets if "detection" in d.name.lower())

# 3. Start training
run = forge.train.start(
    model_id=model.id,
    dataset_id=dataset.id,
    task="detection",
    params={
        "epochs": 100,
        "batchSize": 16,
        "imgSize": 640,
        "lr": 0.01,
        "optimizer": "AdamW",
        "device": "0",        # GPU ID, or "0,1" for multi-GPU
    }
)

# 4. Poll for completion
run_id = run["run_id"]
while True:
    history = forge.train.get_history(run_id)
    if history:
        latest = history[-1]
        print(f"Epoch {latest['epoch']} | mAP@50: {latest.get('mAP50', 0):.4f}")
    runs = forge.train.list_runs()
    current = next((r for r in runs if r.id == run_id), None)
    if current and current.status in ("completed", "failed"):
        break
    time.sleep(10)

print(f"Training complete. Final loss: {current.final_loss:.4f}")

# 5. Run inference
import base64
with open("test_image.jpg", "rb") as f:
    b64 = base64.b64encode(f.read()).decode()

result = forge.inference.run(
    model_id=model.id,
    image_base64=b64,
    confidence=0.25,
    iou_threshold=0.45
)

print(f"Detected {len(result['detections'])} objects in {result['total_ms']:.1f}ms")
for det in result["detections"]:
    print(f"  [{det['class_name']}] conf={det['confidence']:.2f}")
```

### Benchmark Two Models

```python
from mlforge_sdk import MLForge

forge = MLForge()

# Compare inference speed across models
job = forge.benchmark.start(
    model_ids=["yolov8-nano-detection", "yolov8-small-detection"],
    dataset_id="my-dataset",
    config={"input_source": "dataset", "iterations": 100}
)

results = forge.benchmark.get_results(job["job_id"])
for r in results:
    print(f"{r['model_name']}: {r['fps']:.1f} FPS | {r['latency_p95']:.1f}ms p95")
```

---

## CLI Reference

```bash
# Start the local studio + dashboard
mlforge start

# Explore the global model registry (600+ models)
mlforge explore models --task detection
mlforge explore models --task classification --framework transformers

# Download a model
mlforge explore download yolov8-nano-detection

# Import a dataset from Roboflow
mlforge dataset import roboflow --workspace my-org --project license-plates --version 3

# Import from HuggingFace
mlforge dataset import hf --repo username/my-dataset

# Run benchmark
mlforge benchmark run --model yolov8-nano --dataset my-dataset --source video

# Start training (CLI)
mlforge train start --model yolov8-nano --dataset my-dataset --epochs 100
```

---

## Platform Access Layers

MLForge gives you **4 ways to work** — pick what fits:

| Layer | When to use |
|-------|-------------|
| **Desktop App** | Visual workflow, live metrics, no code required |
| **Web Studio** | Team access, browser-based, same features as desktop |
| **Python SDK** | Automation, CI/CD pipelines, notebooks |
| **CLI** | Scripts, DevOps, headless servers |

---

## Core Dashboards

### Model Zoo
- 600+ industrial models (YOLO, Transformers, ONNX, SAM)
- One-click download to local storage
- Local model import (PyTorch, ONNX, GGUF, Safetensors)
- Search by task, framework, hardware target

### Dataset Manager
- HuggingFace + Roboflow + local folder import
- Dataset health check (class balance, duplicates, corrupted files)
- Class distribution analytics + annotation density maps
- Multi-format export (YOLO, COCO, Pascal VOC)

### Training Dashboard
- YOLO detection, classification, segmentation, pose estimation
- Real-time loss curves + metric charts (mAP, precision, recall)
- Checkpoint management (save / resume / download)
- Augmentation controls (HSV, mosaic, mixup, copy-paste)
- Pause/resume without losing progress
- Live validation preview every epoch
- Multi-run comparison overlay

### Inference Engine
- Task-specific input modes: Image · Video · Webcam · RTSP · URL · Text
- Live bounding box canvas with zoom + pan + overlay toggle
- Real-time FPS, latency, GPU utilization metrics
- Webcam inference loop at 15fps via WebSocket
- Export results as JSON

### Benchmark Suite
- Compare models on FPS, latency, accuracy, memory
- Video, RTSP stream, webcam, and dataset sources
- Hardware profiling (GPU %, VRAM, CPU)
- Radar charts + leaderboard

### Unified Logs
- Training · Inference · Benchmark · System logs in one panel
- Source filter tabs (All / Training / Inference / Benchmark)
- Real-time streaming, level filter (DEBUG / INFO / WARN / ERROR)

---

## Supported Tasks

| Task | Training Engine | Inference |
|------|----------------|-----------|
| Object Detection | YOLOv8/v11 ✅ | YOLO + ONNX ✅ |
| Image Classification | YOLO-cls ✅ | YOLO + ONNX ✅ |
| Instance Segmentation | YOLO-seg ✅ | YOLO ✅ |
| Pose Estimation | YOLO-pose ✅ | YOLO ✅ |
| NLP / Text | Transformers 🔜 | Transformers 🔜 |
| Audio (Whisper) | Whisper 🔜 | 🔜 |
| Text Generation / LLM | LoRA/PEFT 🔜 | 🔜 |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    MLForge Ecosystem                         │
│                                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │ Desktop  │  │  Web     │  │ Python   │  │   CLI    │   │
│  │   App    │  │  Studio  │  │   SDK    │  │          │   │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘   │
│       └─────────────┴─────────────┴──────────────┘         │
│                            │                                │
│              ┌─────────────▼─────────────┐                 │
│              │    Local FastAPI Engine    │                 │
│              │  (127.0.0.1 — your GPU)   │                 │
│              │                           │                 │
│              │  Training │ Inference      │                 │
│              │  Dataset  │ Benchmark      │                 │
│              │  Models   │ Logs          │                 │
│              └─────────────┬─────────────┘                 │
│                            │                                │
│              ┌─────────────▼─────────────┐                 │
│              │   Cloud Registry Gateway  │                 │
│              │  (Model catalog · Auth)   │                 │
│              └───────────────────────────┘                 │
└─────────────────────────────────────────────────────────────┘

Data flow: Cloud → Metadata only. Compute + data = local.
```

---

## Privacy & Security

**Data Sovereignty** — your data never leaves your machine:

- Engine binds to `127.0.0.1` by default — not reachable from network
- Model weights, datasets, training artifacts: all local storage
- All job history + metrics: local SQLite (not sent anywhere)
- Cloud registry provides metadata and model listings only
- HIPAA/GDPR/defense-compatible: zero PII egress

---

## Roadmap

- [x] YOLO Detection / Classification / Segmentation / Pose training
- [x] Schema-driven task-specific UI (fully extensible)
- [x] Checkpoint management + resume from checkpoint
- [x] Multi-run comparison charts
- [x] Real pause/resume (engine-level, no data loss)
- [x] Webcam real-time inference loop
- [x] Unified log streaming (training + inference + system)
- [ ] HuggingFace Transformers training engine (NLP/LLM)
- [ ] LoRA / PEFT fine-tuning for LLMs
- [ ] Rich annotation studio (Roboflow-complete feature set)
- [ ] Face recognition dataset creation pipeline
- [ ] Cloud GPU option (RunPod / Lambda integration)
- [ ] npm package for JavaScript/TypeScript workflows
- [ ] Annotation marketplace

---

## Contributing

MLForge core engine is proprietary. The SDK and CLI are open for community contributions.

```bash
git clone https://github.com/Kumar2421/mlforge
cd mlforge/packages/mlforge_sdk
pip install -e ".[dev]"
pytest tests/
```

Issues, feature requests, and discussions: [GitHub Issues](https://github.com/Kumar2421/mlforge/issues)

---

## License

© 2026 MLForge Team. SDK and CLI packages are MIT licensed.  
Core studio engine is proprietary. [Contact for enterprise licensing.](mailto:sales@mlforge.in)
