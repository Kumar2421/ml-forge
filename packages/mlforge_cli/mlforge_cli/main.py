import json
import time
import subprocess
import sys
import webbrowser
from typing import Optional, Any

import typer
from rich.console import Console
from rich.table import Table

from mlforge_sdk import MLForge
from mlforge_sdk.auth import delete_token, load_token, save_token

app = typer.Typer(help="MLForge CLI - Local-first ML workspace (projects → explore → datasets → train/benchmark/infer)")
console = Console()

def _unwrap_typer_value(v: Any) -> Any:
    """
    When a Typer command function is called directly (not via Typer),
    parameters with defaults like `typer.Option(...)` remain `OptionInfo`.
    Convert `OptionInfo` to its `.default` to avoid crashes.
    """
    try:
        from typer.models import OptionInfo  # type: ignore
        if isinstance(v, OptionInfo):
            return v.default
    except Exception:
        pass
    return v


def _sdk(host: str | None = None, port: int | None = None) -> MLForge:
    # If host is provided, use it. Otherwise, use SDK defaults (which is Cloud).
    host = _unwrap_typer_value(host)
    port = _unwrap_typer_value(port)
    if host:
        return MLForge(host=str(host), port=int(port) if port else 7860)
    return MLForge()


def _add_global_opts(fn):
    return fn


project_app = typer.Typer(help="Create/open projects (mirrors WorkspaceDashboard)")
explore_app = typer.Typer(help="Explore models (mirrors ExploreView)")
dataset_app = typer.Typer(help="Datasets manager (mirrors DatasetDashboard)")
train_app = typer.Typer(help="Training runs")
benchmark_app = typer.Typer(help="Benchmark jobs/results")
infer_app = typer.Typer(help="Inference")

app.add_typer(project_app, name="project")
app.add_typer(explore_app, name="explore")
app.add_typer(dataset_app, name="dataset")
app.add_typer(train_app, name="train")
app.add_typer(benchmark_app, name="benchmark")
app.add_typer(infer_app, name="infer")


@app.command("start")
def start_backend(
    host: str = typer.Option("127.0.0.1", "--host", help="Host to bind the backend to"),
    port: int = typer.Option(8005, "--port", help="Port to bind the backend to"),
    no_ui: bool = typer.Option(False, "--no-ui", help="Don't open the browser automatically"),
):
    """Start the local MLForge backend engine and open the UI."""
    ui_url = f"http://{host}:{port}"
    console.print(f"[bold green]Starting local MLForge backend on {ui_url}...[/bold green]")
    
    if not no_ui:
        console.print(f"[cyan]Opening UI in browser: {ui_url}[/cyan]")
        webbrowser.open(ui_url)

    try:
        # Resolve the path to the bundled backend directory inside the package
        import os
        current_dir = os.path.dirname(os.path.abspath(__file__))
        
        # 1. Try to find bundled 'bin' directory (Production/Installed mode)
        bundled_backend = os.path.join(current_dir, "bin")
        
        # 2. Try to find local 'backend' directory (Development/Monorepo mode)
        dev_backend = os.path.abspath(os.path.join(current_dir, "..", "..", "..", "backend"))
        
        if os.path.exists(os.path.join(bundled_backend, "main.py")):
            backend_dir = bundled_backend
        elif os.path.exists(os.path.join(dev_backend, "main.py")):
            backend_dir = dev_backend
        else:
            # Fallback
            backend_dir = os.getcwd()

        console.print(f"[dim]Engine Path: {backend_dir}[/dim]")

        subprocess.run(
            [sys.executable, "-m", "uvicorn", "main:app", "--host", host, "--port", str(port)],
            cwd=backend_dir,
            check=True
        )
    except KeyboardInterrupt:
        console.print("\n[yellow]Backend stopped by user.[/yellow]")
    except Exception as e:
        console.print(f"[red]Error starting backend:[/red] {str(e)}")


@app.command("login")
def login(
    token: str = typer.Option(..., "--token", help="Hugging Face access token (for private Spaces)"),
):
    """Save Hugging Face token locally for authenticated cloud requests."""
    save_token(token)
    console.print("[green]Saved token to ~/.mlforge/credentials.json[/green]")


@app.command("logout")
def logout():
    """Remove locally saved Hugging Face token."""
    delete_token()
    console.print("[yellow]Token removed from ~/.mlforge/credentials.json[/yellow]")


@app.command("whoami")
def whoami():
    """Show whether a token is configured (does not print the token)."""
    token = load_token()
    if token:
        console.print("[green]Authenticated: token is configured[/green]")
    else:
        console.print("[red]Not authenticated: run mlforge login --token ...[/red]")


@explore_app.command("models")
def explore_models(
    task: Optional[str] = typer.Option(None, "--task", "-t", help="Filter by task"),
    cached: Optional[bool] = typer.Option(None, "--cached", "-c", help="Show only cached models"),
    host: Optional[str] = typer.Option(None, "--host", help="Backend host"),
    port: Optional[int] = typer.Option(None, "--port", help="Backend port"),
):
    """List available models in the Model Zoo."""
    sdk = _sdk(host, port)
    models = sdk.models.list(task=task, downloaded=cached)
    table = Table(title="MLForge Model Zoo")
    table.add_column("ID", style="dim")
    table.add_column("Name", style="cyan")
    table.add_column("Task", style="green")
    table.add_column("Status", style="magenta")

    for m in models:
        status = "Cached" if m.downloaded else "Remote"
        table.add_row(m.id, m.name, m.task or "N/A", status)
    console.print(table)


@explore_app.command("download")
def explore_download_model(
    model_id: str = typer.Argument(..., help="The ID of the model to download"),
    host: Optional[str] = typer.Option(None, "--host", help="Backend host"),
    port: Optional[int] = typer.Option(None, "--port", help="Backend port"),
):
    """Download a model to local cache (download job)."""
    sdk = _sdk(host, port)
    with console.status(f"Triggering download for {model_id}...") as status:
        job = sdk.models.download(model_id)
        console.print(f"Download job created: {job.id}")

        while job.status not in ["completed", "failed", "cancelled"]:
            time.sleep(1)
            job = sdk.models.get_job(job.id)
            status.update(f"Downloading {model_id}: {job.progress:.1f}%")

        console.print(f"Job status: {job.status}")

@train_app.command("runs")
def train_list_runs(
    host: Optional[str] = typer.Option(None, "--host", help="Backend host"),
    port: Optional[int] = typer.Option(None, "--port", help="Backend port"),
):
    """List training runs."""
    sdk = _sdk(host, port)
    runs = sdk.train.list_runs()
    table = Table(title="MLForge Training Runs")
    table.add_column("Run #", style="dim")
    table.add_column("Model", style="cyan")
    table.add_column("Status", style="bold")
    table.add_column("Best Metric", style="emerald")
    for r in runs:
        best = "—"
        try:
            best = str(max(r.best_metric.values())) if r.best_metric else "—"
        except Exception:
            best = "—"
        table.add_row(str(r.run_number), r.model_name, r.status, best)
    console.print(table)

@dataset_app.command("list")
def dataset_list(
    source: Optional[str] = typer.Option(None, "--source", help="Filter by source (roboflow|huggingface|local|roboflow_curl)"),
    status: Optional[str] = typer.Option(None, "--status", help="Filter by status"),
    search: Optional[str] = typer.Option(None, "--search", help="Search query"),
    host: Optional[str] = typer.Option(None, "--host", help="Backend host"),
    port: Optional[int] = typer.Option(None, "--port", help="Backend port"),
):
    """List datasets."""
    sdk = _sdk(host, port)
    datasets = sdk.datasets.list(source=source, status=status, search=search)
    table = Table(title="MLForge Datasets")
    table.add_column("ID", style="dim")
    table.add_column("Name", style="cyan")
    table.add_column("Images", style="green")
    table.add_column("Classes", style="green")
    table.add_column("Format", style="magenta")
    for d in datasets:
        table.add_row(d.id, d.name, str(d.images), str(d.classes), d.format or "N/A")
    console.print(table)


@dataset_app.command("import")
def dataset_import(
    dataset_id: str = typer.Argument(..., help="Dataset id (e.g. rf-..., local-..., hf-...)"),
    source: str = typer.Option(..., "--source", help="roboflow|roboflow_curl|huggingface|local"),
    roboflow_key: Optional[str] = typer.Option(None, "--roboflow-key"),
    roboflow_workspace: Optional[str] = typer.Option(None, "--roboflow-workspace"),
    roboflow_project: Optional[str] = typer.Option(None, "--roboflow-project"),
    roboflow_version: int = typer.Option(1, "--roboflow-version"),
    hf_dataset_id: Optional[str] = typer.Option(None, "--hf-dataset-id"),
    local_path: Optional[str] = typer.Option(None, "--local-path"),
    download_url: Optional[str] = typer.Option(None, "--download-url"),
    dataset_name: Optional[str] = typer.Option(None, "--dataset-name"),
    curl_format: Optional[str] = typer.Option(None, "--curl-format"),
    headers_json: Optional[str] = typer.Option(None, "--headers-json", help="JSON object of headers for roboflow_curl"),
    host: Optional[str] = typer.Option(None, "--host", help="Backend host"),
    port: Optional[int] = typer.Option(None, "--port", help="Backend port"),
):
    """Import a dataset (mirrors ImportModal tabs)."""
    sdk = _sdk(host, port)
    headers = {}
    if headers_json:
        headers = json.loads(headers_json)

    payload = {
        "dataset_id": dataset_id,
        "source": source,
        "roboflow_key": roboflow_key,
        "roboflow_workspace": roboflow_workspace,
        "roboflow_project": roboflow_project,
        "roboflow_version": roboflow_version,
        "hf_dataset_id": hf_dataset_id,
        "local_path": local_path,
        "download_url": download_url,
        "headers": headers,
        "dataset_name": dataset_name,
        "curl_format": curl_format,
        "name": dataset_name,
    }
    resp = sdk.datasets.import_dataset(dataset_id, payload)
    console.print(f"Queued import job: {resp.job_id} (dataset_id={resp.dataset_id})")

@benchmark_app.command("results")
def benchmark_results(
    host: Optional[str] = typer.Option(None, "--host", help="Backend host"),
    port: Optional[int] = typer.Option(None, "--port", help="Backend port"),
):
    """List benchmark results."""
    sdk = _sdk(host, port)
    results = sdk.benchmark.list_results()
    table = Table(title="MLForge Benchmark Results")
    table.add_column("Result ID", style="dim")
    table.add_column("Job ID", style="dim")
    table.add_column("Model", style="cyan")
    table.add_column("Task", style="green")
    table.add_row(*["(see job)", "(see job)", "(see job)", "(see job)"])
    # Keep output small and safe even if schema changes.
    for r in results[:50]:
        table.add_row(r.id[:8], r.job_id[:8], r.model_id or "—", r.task or "—")
    console.print(table)

@infer_app.command("run")
def infer_run(
    model_id: str = typer.Argument(..., help="Model ID to use"),
    image: Optional[str] = typer.Argument(None, help="Path to input image"),
    adapter_type: str = typer.Option("yolo", "--adapter-type"),
    precision: str = typer.Option("FP16", "--precision"),
    text: Optional[str] = typer.Option(None, "--text", help="Text prompt/input"),
    # Advanced YOLO
    conf: float = typer.Option(0.25, "--conf", help="Confidence threshold (YOLO)"),
    iou: float = typer.Option(0.45, "--iou", help="IOU threshold (YOLO)"),
    max_det: int = typer.Option(300, "--max-det", help="Max detections (YOLO)"),
    # Advanced Transformers
    temp: float = typer.Option(0.7, "--temp", help="Temperature (Transformers)"),
    top_p: float = typer.Option(0.9, "--top-p"),
    max_tokens: int = typer.Option(256, "--max-tokens"),
    # Execution
    provider: str = typer.Option("CUDAExecutionProvider", "--provider", help="ONNX Execution Provider"),
    host: Optional[str] = typer.Option(None, "--host", help="Backend host"),
    port: Optional[int] = typer.Option(None, "--port", help="Backend port"),
):
    """Run inference (JSON request, like the UI pipeline)."""
    sdk = _sdk(host, port)

    yolo_cfg = None
    if adapter_type == "yolo":
        yolo_cfg = {"confidence": conf, "iou_threshold": iou, "max_detections": max_det}
    
    trans_cfg = None
    if adapter_type == "transformers":
        trans_cfg = {"temperature": temp, "top_p": top_p, "max_new_tokens": max_tokens}
    
    onnx_cfg = None
    if adapter_type == "onnx":
        onnx_cfg = {"execution_provider": provider}

    with console.status(f"Running inference with {model_id}..."):
        result = sdk.inference.run(
            model_id,
            image_path=image,
            adapter_type=adapter_type,
            precision=precision,
            text_input=text,
            yolo_config=yolo_cfg,
            transformers_config=trans_cfg,
            onnx_config=onnx_cfg
        )

    if result.status != "ok":
        raise typer.Exit(code=1)

    console.print(f"Inference OK: total_ms={result.total_ms:.1f} quality={result.quality_score}")
    if result.detections:
        table = Table(title="Detections")
        table.add_column("Class", style="cyan")
        table.add_column("Confidence", style="green")
        table.add_column("Box", style="dim")
        for det in result.detections[:50]:
            table.add_row(
                str(det.get("class_name") or det.get("class") or det.get("label") or "—"),
                str(det.get("confidence") or "—"),
                str([det.get("x1"), det.get("y1"), det.get("x2"), det.get("y2")]),
            )
        console.print(table)

@project_app.command("list")
def project_list(
    host: Optional[str] = typer.Option(None, "--host", help="Backend host"),
    port: Optional[int] = typer.Option(None, "--port", help="Backend port"),
):
    """List projects from backend registry."""
    sdk = _sdk(host, port)
    projects = sdk.projects.list()
    table = Table(title="MLForge Projects")
    table.add_column("ID", style="dim")
    table.add_column("Name", style="cyan")
    table.add_column("Path", style="dim")
    table.add_column("Last Opened", style="green")
    for p in projects:
        table.add_row(p.id, p.name, p.path, p.last_opened)
    console.print(table)


@project_app.command("open")
def project_open(
    project_id: str = typer.Argument(..., help="Project id to open (sets active project on backend)"),
    host: Optional[str] = typer.Option(None, "--host", help="Backend host"),
    port: Optional[int] = typer.Option(None, "--port", help="Backend port"),
):
    """Open a project (sets backend active project_id/path)."""
    sdk = _sdk(host, port)
    sdk.projects.open(project_id)
    console.print(f"Active project set: {project_id}")


# ── Backward compatible aliases ─────────────────────────────────────────────

@app.command("list-models")
def list_models_alias(
    task: Optional[str] = typer.Option(None, "--task", "-t"),
    cached: Optional[bool] = typer.Option(None, "--cached", "-c"),
):
    explore_models(task=task, cached=cached)


@app.command("download-model")
def download_model_alias(model_id: str = typer.Argument(...)):
    explore_download_model(model_id=model_id)


@app.command("list-datasets")
def list_datasets_alias():
    dataset_list()


@app.command("list-runs")
def list_runs_alias():
    train_list_runs()


@app.command("list-benchmarks")
def list_benchmarks_alias():
    benchmark_results()


@app.command("run-inference")
def run_inference_alias(
    model_id: str = typer.Argument(...),
    image: Optional[str] = typer.Argument(None),
):
    infer_run(model_id=model_id, image=image)

def version_callback(value: bool):
    if value:
        console.print(f"MLForge CLI v0.1.0")
        raise typer.Exit()

@app.callback()
def main(
    version: Optional[bool] = typer.Option(
        None, "--version", callback=version_callback, is_eager=True, help="Show the version and exit."
    ),
):
    """
    MLForge CLI - Industrial-Grade ML Platform.
    Manage projects, explore models, and run high-performance training/inference.
    """
    pass

if __name__ == "__main__":
    app()
