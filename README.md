# MLForge ⚒️

**Industrial-Grade Hybrid ML Platform: Cloud Intelligence, Local Execution.**

MLForge provides a seamless bridge between a global model/dataset registry and your local hardware. Manage projects, explore models, and run training/benchmarking/inference with full IP protection and data privacy.

## 🚀 Key Features

- **Hybrid Architecture**: Metadata and discovery live in the cloud (Hugging Face Spaces); GPU-intensive tasks stay local.
- **IP Protection**: Core local engines are obfuscated/compiled for secure distribution.
- **Unified Interface**: Built-in web dashboard served automatically from the CLI.
- **Enterprise-Ready CLI/SDK**: Full control over your ML lifecycle from the terminal or Python scripts.

## 📦 Installation

`ash
pip install mlforge-sdk mlforge-cli
`

## 🛠️ Quickstart

### 1. Start the Local Workspace
MLForge launches a local background engine and opens your browser to the dashboard automatically.
`ash
mlforge start
`
*UI URL: http://127.0.0.1:8005*

### 2. Discover Models (CLI)
Explore the global Model Zoo directly from your terminal.
`ash
mlforge explore models
`

## 📐 Architecture: The Hybrid Edge

MLForge uses a **Brain & Muscle** design:
- **The Brain (Cloud)**: Central registry for models, datasets, and cross-machine project syncing.
- **The Muscle (Local)**: High-performance engines for training, benchmarking, and inference. Your data never leaves your infrastructure.

## 💻 CLI Command Tree

- mlforge start — Launch local engine & UI.
- mlforge project [list|open|create] — Workspace management.
- mlforge explore [models|download] — Global model discovery.
- mlforge dataset [list|import] — Local and remote dataset registry.
- mlforge train runs — Training lifecycle management.
- mlforge benchmark results — Performance analytics.
- mlforge infer run — Hardware-accelerated inference.

---
© 2026 MLForge Team. Industrial-Grade ML Infrastructure.
