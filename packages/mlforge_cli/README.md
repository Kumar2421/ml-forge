# MLForge CLI ⚒️

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-Proprietary-red.svg)](LICENSE)
[![User Interface](https://img.shields.io/badge/UI-Studio-violet.svg)](https://mlforge.ai)

**The performance-driven terminal interface for MLForge.**

The MLForge CLI is designed for high-productivity ML engineering. It provides a hardened, terminal-optimized gateway to the MLForge "Muscle" engine, allowing you to orchestrate the entire ML lifecycle without leaving your shell.

<p align="center">
  <img src="../mlforge_sdk/asset/models-list.png" alt="MLForge CLI" width="100%">
  <br>
  <em>High-fidelity terminal output for professional model discovery and dataset analysis.</em>
</p>

---

## 🚀 Key Features

- **Blazing Fast Start**: `mlforge start` spins up the local FastAPI engine and the Studio UI in seconds.
- **Deep Dataset Analytics**: **(NEW)** High-fidelity health reports with `mlforge dataset analytics`.
- **Granular Model Discovery**: Filter the 600+ model zoo by framework, hardware compatibility, and task.
- **Hardware Monitoring**: Real-time GPU/CPU telemetry via `mlforge system`.
- **Unified Jobs System**: Track training, benchmarks, and downloads through a centralized job queue.

---

## 📦 Installation

```bash
pip install mlforge-cli
```

---

## 🛠️ Command Reference

### 🏗️ Setup & Dashboard
| Command | Description |
| :--- | :--- |
| `mlforge start` | Launches the local engine and Electron Studio. |
| `mlforge login` | Sync your Hugging Face credentials for cloud registry access. |
| `mlforge system` | Real-time dashboard of GPU/VRAM/CPU/RAM utilization. |

### 📊 Dataset Management
| Command | Description |
| :--- | :--- |
| `mlforge dataset list` | View local library and cloud discovery results. |
| `mlforge dataset analytics` | **(NEW)** View health scores and quality issues (duplicates, missing labels). |
| `mlforge dataset import` | Pull datasets from HF or Roboflow to local NVMe storage. |

### 🔍 Model Exploration
| Command | Description |
| :--- | :--- |
| `mlforge explore models` | Search models with specific hardware and framework filters. |
| `mlforge explore download` | Queue a model download to your local zoo. |

### ⚡ Training & Execution
| Command | Description |
| :--- | :--- |
| `mlforge train start` | Launch local training with hyperparameters and augmentation configs. |
| `mlforge benchmark run` | Execute automated performance sweeps on your local hardware. |
| `mlforge infer run` | Run universal inference on local files or RTSP streams. |

---

## 🛡️ Security & Sovereignty

- **100% Local Compute**: Your data and compute weights never leave your machine.
- **Local SQLite Persistence**: All job history and metrics are stored in an auditable local database.
- **Proprietary Redaction**: Sensitive tokens are automatically masked in all terminal logs.

---

## 📄 License
© 2026 MLForge Team. All rights reserved. Proprietary software.
