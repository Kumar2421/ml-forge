# MLForge CLI Command Reference

The MLForge CLI is an industrial-grade terminal interface for managing ML projects, models, and datasets.

## Core Commands

### `mlforge system`
Real-time hardware telemetry.
- **Displays**: CPU usage/brand, RAM availability, Disk space, and NVIDIA GPU metrics (VRAM, Util).

### `mlforge login`
Authenticate with Hugging Face to access private models and spaces.
- **Usage**: `mlforge login --token <HF_TOKEN>`

### `mlforge start`
Launch the local MLForge backend server.
- **Options**: `--host`, `--port`

---

## Model Exploration (`mlforge explore`)

### `mlforge explore models`
List available models in the Model Zoo.
- **Filters**: `--search`, `--task`, `--framework`, `--cached`
- **Example**: `mlforge explore models --task object-detection --cached`

### `mlforge explore download`
Download a model to your local cache.
- **Usage**: `mlforge explore download <MODEL_ID>`

---

## Dataset Management (`mlforge dataset`)

### `mlforge dataset list`
List all datasets currently imported in the local workspace.

### `mlforge dataset import`
Import datasets from various sources (Roboflow, Hugging Face, Local).
- **Sources**: `roboflow`, `huggingface`, `local`
- **Example**: `mlforge dataset import <ID> --source roboflow --roboflow-key <KEY>`

### `mlforge dataset analytics`
View deep health and quality analytics for a dataset.
- **Usage**: `mlforge dataset analytics <DATASET_ID>`

---

## Project Management (`mlforge project`)

### `mlforge project list`
List all projects in the workspace.

### `mlforge project open`
Set the active project for the backend.
- **Usage**: `mlforge project open <PROJECT_ID>`
