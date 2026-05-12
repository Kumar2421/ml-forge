# MLForge CLI ⚒️

**Industrial-Grade Hybrid ML Platform: Cloud Intelligence, Local Execution.**

MLForge CLI is the terminal interface for the MLForge Studio environment. It provides a seamless bridge between a global model/dataset registry and your local hardware.

## 🌟 Key Capabilities

- **Hybrid Architecture**: Discovery via Cloud Registry ("The Brain"), Compute via Local Engine ("The Muscle").
- **Full Workspace Management**: Create and manage projects directly from the terminal.
- **Embedded UI**: Launch the "Forge Dark" React dashboard with a single command.
- **Production-Ready**: Built-in telemetry, audit logging, and hardware acceleration (CUDA/CPU).

## 📦 Installation

```bash
pip install mlforge-cli
```

## 🚀 Usage

### Start the Engine & UI
Launch the local backend engine and open the visual dashboard in your browser:
```bash
mlforge start
```

### Explore the Model Zoo
Search and discover models in the curated registry:
```bash
mlforge list-models --task detection
```

### Run Inference
Execute high-performance inference with advanced controls:
```bash
mlforge infer run <model_id> <image_path> --conf 0.5 --iou 0.45
```

### Manage Datasets
List your local datasets and their analytics:
```bash
mlforge list-datasets
```

## 🛡️ Security
MLForge CLI follows a local-first security model. The backend binds to `127.0.0.1` by default, ensuring your local hardware and data remain private and protected.

## 📄 License
© 2026 MLForge Team. All rights reserved. Proprietary software.
