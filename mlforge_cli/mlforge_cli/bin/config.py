"""
config.py — Centralized application settings.
All tuneable knobs live here; override via environment variables.
"""
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── App ───────────────────────────────────────────────────────────
    app_name: str = "MLForge Platform"
    version: str = "1.0.0"
    debug: bool = False

    # ── API ───────────────────────────────────────────────────────────
    host: str = "0.0.0.0"
    port: int = 8005
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:2000",
        "http://127.0.0.1:2000",
    ]

    # ── Storage ───────────────────────────────────────────────────────
    base_dir: Path = Path(__file__).resolve().parents[1]
    data_dir: Path = base_dir / "data"
    models_dir:   Path = data_dir / "models"
    datasets_dir: Path = data_dir / "datasets"   # root for imported datasets
    logs_dir:     Path = data_dir / "logs"
    db_path:      Path = data_dir / "modelzoo.db"

    # ── Download Manager ──────────────────────────────────────────────
    max_concurrent_downloads: int = 5
    download_chunk_size: int = 1024 * 1024  # 1 MB
    download_max_retries: int = 3
    download_retry_delay: float = 2.0       # seconds (base, exponential backoff)

    # ── Search ────────────────────────────────────────────────────────
    search_max_results: int = 500

    # ── Sync ──────────────────────────────────────────────────────────
    auto_sync_on_startup: bool = True

    # ── Hugging Face API ──────────────────────────────────────────────
    hf_api_base: str = "https://huggingface.co/api"
    hf_hub_url:  str = "https://huggingface.co"
    hf_token: str | None = None             # Optional: HF_TOKEN env var
    hf_models_per_task: int = 100           # How many to pull per task

    # ── ONNX Zoo ──────────────────────────────────────────────────────
    onnx_models_url: str = (
        "https://raw.githubusercontent.com/onnx/models/main/README.md"
    )

    # ── Benchmark Bridge ──────────────────────────────────────────────
    benchmark_max_concurrent: int = 3      # max parallel benchmark jobs
    benchmark_max_log_lines:  int = 500    # log entries kept per job
    benchmark_ws_poll_hz:     float = 2.0  # WebSocket telemetry poll rate

    # ── Dataset Manager ───────────────────────────────────────────────
    roboflow_api_base:        str = "https://api.roboflow.com"
    dataset_import_workers:   int = 3          # max concurrent import jobs
    dataset_chunk_size:       int = 1024 * 1024 * 4   # 4 MB download chunk
    roboflow_cache_ttl_secs:  int = 3600       # 1 hour

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.datasets_dir.mkdir(parents=True, exist_ok=True)
        (self.datasets_dir / "_tmp").mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)


settings = Settings()
