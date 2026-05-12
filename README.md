# MLForge ⚒️

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-Proprietary-red.svg)](LICENSE)
[![User Interface](https://img.shields.io/badge/UI-Studio-violet.svg)](https://mlforge.ai)

**Industrial-Grade Hybrid ML Platform: Global Discovery, Local Sovereignty.**

MLForge provides the infrastructure for professional AIML engineering. It bridges the gap between discovering state-of-the-art models and executing them on local hardware, ensuring that your compute and data remain strictly under your control.

<p align="center">
  <img src="packages/mlforge_sdk/asset/models-list.png" alt="MLForge Ecosystem" width="100%">
</p>

---

## 🏗️ The "Brain & Muscle" Architecture

MLForge is uniquely structured to provide the best of both worlds:

- **The Brain (Cloud Registry)**: A central intelligence hub hosted on Hugging Face Spaces. It curates a global library of 600+ industrial-grade models and datasets, providing metadata and hardware compatibility gates.
- **The Muscle (Local Engine)**: A hardened compute backend that runs on your workstation. It handles heavy GPU/CPU tensor computation, local dataset management, and hardware telemetry.

---

## 🚀 Core Capabilities

- **Unified Model Zoo**: Instant access to YOLO, Transformers, and ONNX models for Detection, Classification, and more.
- **Local-First Datasets**: Download and analyze millions of images from HF/Roboflow using local bandwidth and storage.
- **Deep Analytics**: Professional-grade terminal and web dashboards for dataset health and performance metrics.
- **Hardware Telemetry**: Real-time monitoring of VRAM, CPU, and power consumption during training and inference.
- **Sovereign Training**: Execute high-performance training jobs on local CUDA or Apple Silicon hardware.

---

## 📦 Installation

```bash
# Install the universal CLI and SDK
pip install mlforge-sdk mlforge-cli
```

---

## 💻 CLI Quickstart

The MLForge CLI is your command center for professional ML development.

```bash
# 1. Start your local studio
mlforge start

# 2. Explore the global model registry
mlforge explore models --task detection --framework onnx

# 3. Analyze local dataset health (NEW!)
mlforge dataset analytics rf-license-plate-detection
```

---

## 🛡️ Security & Privacy

We believe in **Data Sovereignty**:
- **Local-Only Binding**: The engine binds to `127.0.0.1` by default.
- **IP Protection**: Your datasets and model weights never leave your machine.
- **Local SQLite Persistence**: All job history and metrics are stored in an auditable local database.

---

## 📄 License & Terms
© 2026 MLForge Team. This software is proprietary. For enterprise licensing and support, contact [sales@mlforge.ai](mailto:sales@mlforge.ai).
