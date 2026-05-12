# MLForge SDK ⚒️

**Universal Python SDK for Industrial-Grade AIML Engineering.**

MLForge SDK provides a high-level programmatic interface to the MLForge ecosystem. It allows you to discover models, manage datasets, and orchestrate high-performance training and inference runs with ease.

## 🚀 Features

- **Model Registry**: Programmatic access to a curated zoo of 600+ models.
- **Unified Inference**: Execute YOLO, Transformers, and ONNX models through a consistent API.
- **Dataset Management**: Import and analyze datasets from multiple sources (HF, Roboflow, Local).
- **Training Orchestration**: Start, monitor, and manage training runs on local hardware.
- **Benchmarking**: Automate performance validation across different hardware and precisions.

## 📦 Installation

```bash
pip install mlforge-sdk
```

## 🛠️ Quick Start

```python
from mlforge_sdk import MLForge

# Connect to the Cloud Registry (Brain)
forge = MLForge()

# List available object detection models
models = forge.models.list(task="detection")
for m in models[:5]:
    print(f"Found: {m.name} ({m.id})")

# Run inference on a local image
result = forge.inference.run(
    model_id="ultralytics_yolov8",
    image_path="path/to/image.jpg",
    conf=0.25
)

print(f"Detections: {len(result.detections)}")
```

## 📄 License
© 2026 MLForge Team. All rights reserved. Proprietary software.
