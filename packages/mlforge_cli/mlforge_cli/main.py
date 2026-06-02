import json
import time
import subprocess
import sys
import webbrowser
from typing import Optional, Any

from mlforge_sdk import MLForge, delete_token, load_token, save_token

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.columns import Columns
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeRemainingColumn
from rich.align import Align
from rich.theme import Theme

from . import updates as _updates


def _resolve_version() -> str:
    """Resolve installed CLI version, falling back when running from source."""
    try:
        from importlib.metadata import version, PackageNotFoundError
        try:
            return version("ml-forge-cli")
        except PackageNotFoundError:
            return "0.1.1"
    except Exception:
        return "0.1.1"


VERSION = _resolve_version()

# ── Theme & Visuals ──────────────────────────────────────────────────────────

MLFORGE_THEME = Theme({
    "info": "cyan",
    "warning": "yellow",
    "error": "red",
    "success": "green",
    "highlight": "bold blue",
    "dim": "grey50",
})

console = Console(theme=MLFORGE_THEME)

BANNER = f"""
[bold blue]
 ███╗   ███╗██╗     ███████╗ ██████╗ ██████╗  ██████╗ ███████╗
 ████╗ ████║██║     ██╔════╝██╔═══██╗██╔══██╗██╔════╝ ██╔════╝
 ██╔████╔██║██║     █████╗  ██║   ██║██████╔╝██║  ███╗█████╗  
 ██║╚██╔╝██║██║     ██╔══╝  ██║   ██║██╔══██╗██║   ██║██╔══╝  
 ██║ ╚═╝ ██║███████╗██║     ╚██████╔╝██║  ██║╚██████╔╝███████╗
 ╚═╝     ╚═╝╚══════╝╚═╝      ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚══════╝
[/bold blue]
[dim]Industrial-Grade ML Workspace | v{VERSION}[/dim]
"""

def print_banner():
    console.print(Align.center(BANNER))

app = typer.Typer(
    help="MLForge CLI - Industrial-grade ML Workspace",
    rich_markup_mode="rich"
)

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


def _handle_api_error(e: Exception):
    """
    Common error handler for SDK/API calls.
    Suggests 'mlforge start' if connection fails.
    Handles 402 quota exceeded errors specially.
    """
    import requests
    from mlforge_sdk.http import ApiError

    if isinstance(e, requests.exceptions.ConnectionError):
        console.print("\n[bold red]Error: Could not connect to the MLForge Engine.[/bold red]")
        console.print("[yellow]The local backend might be offline.[/yellow]")
        console.print("\n[bold green]To start the backend, run:[/bold green]")
        console.print("  [white]mlforge start[/white]\n")
        raise typer.Exit(code=1)

    if isinstance(e, ApiError):
        # Handle 402 Payment Required (quota exceeded)
        if e.status == 402:
            console.print("\n[bold red]Limit exceeded[/bold red]")

            # Extract quota details from payload if available
            if e.payload and isinstance(e.payload, dict):
                resource = e.payload.get("resource", "unknown")
                used = e.payload.get("used", "?")
                limit = e.payload.get("limit", "?")
                console.print(f"[error]{resource}: {used}/{limit}[/error]")
                console.print("[yellow]You've reached your free tier limit[/yellow]")

                upgrade_url = e.payload.get("upgrade_url")
                if upgrade_url:
                    console.print(f"[info]Upgrade to Pro: {upgrade_url}[/info]")
                else:
                    console.print("[info]Upgrade to Pro for unlimited access: https://mlforge.in/upgrade[/info]")
            else:
                console.print("[error]You've reached your quota limit[/error]")
                console.print("[info]Upgrade to Pro: https://mlforge.in/upgrade[/info]")

            console.print()
            raise typer.Exit(code=1)

        # All other API errors
        console.print(f"\n[bold red]API Error:[/bold red] {str(e)}")
        raise typer.Exit(code=1)

    raise e


def _sdk(host: Any = None, port: Any = None, api_key: Optional[str] = None) -> MLForge:
    """
    Returns an MLForge SDK instance.
    Defaults to the local backend (127.0.0.1:8005).
    """
    host = _unwrap_typer_value(host)
    port = _unwrap_typer_value(port)
    api_key = _unwrap_typer_value(api_key)

    # Use defaults if still None
    host = host or "127.0.0.1"
    port = int(port) if port is not None else 8005
    
    # Try environment variable if no key provided
    import os
    effective_api_key = api_key or os.getenv("MLFORGE_API_KEY")

    return MLForge(host=str(host), port=port, api_key=effective_api_key)


def _add_global_opts(fn):
    return fn


project_app = typer.Typer(help="📦 Projects - Manage local ML workspaces")
explore_app = typer.Typer(help="🔍 Explore - Discover and download curated models")
dataset_app = typer.Typer(help="💾 Datasets - Discover and manage dataset imports")
train_app = typer.Typer(help="⚡ Training - Execute and monitor model fine-tuning")
benchmark_app = typer.Typer(help="📊 Benchmark - Run high-performance hardware tests")
infer_app = typer.Typer(help="🧠 Inference - Run models directly from the CLI")
update_app = typer.Typer(help="⬆️  Update - Check PyPI for newer CLI/SDK versions")

app.add_typer(project_app, name="project")
app.add_typer(explore_app, name="explore")
app.add_typer(dataset_app, name="dataset")
app.add_typer(train_app, name="train")
app.add_typer(benchmark_app, name="benchmark")
app.add_typer(infer_app, name="infer")
app.add_typer(update_app, name="update")


@update_app.command("check")
def update_check():
    """Check PyPI for newer versions of mlforge-cli and mlforge-sdk."""
    with console.status("Checking PyPI..."):
        result = _updates.status_report()

    table = Table(title="[bold blue]MLForge Update Status[/bold blue]", box=None)
    table.add_column("Package", style="cyan")
    table.add_column("Installed", style="dim")
    table.add_column("Latest", style="green")
    table.add_column("Status", style="bold")

    any_update = False
    for pkg, info in result.get("packages", {}).items():
        installed = info.get("installed") or "—"
        latest = info.get("latest") or "unknown"
        if info.get("installed") and info.get("latest") and installed != latest:
            status_text = "[bold yellow]update available[/bold yellow]"
            any_update = True
        elif info.get("latest") is None:
            status_text = "[dim]could not reach PyPI[/dim]"
        else:
            status_text = "[green]current[/green]"
        table.add_row(pkg, str(installed), str(latest), status_text)

    console.print(table)

    if any_update:
        console.print(
            "\n[bold]To upgrade, run:[/bold] [white]pip install -U ml-forge-cli ml-forge-sdk[/white]\n"
        )


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
    token: Optional[str] = typer.Option(None, "--token", help="Manually provide token (fallback)"),
):
    """
    Authenticate with MLForge. 
    Opens a browser to mlforge.in to complete the cross-platform web login flow.
    """
    if token:
        save_token(token)
        console.print("[success]Successfully saved manual token to ~/.mlforge/credentials.json[/success]")
        return

    import http.server
    import socketserver
    import urllib.parse
    import threading

    login_done = threading.Event()
    captured_data = {}

    class LoginHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            query = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(query)
            
            if "token" in params:
                captured_data["token"] = params["token"][0]
                if "user" in params:
                    try:
                        captured_data["user"] = json.loads(params["user"][0])
                    except: pass
                
                self.send_response(200)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(b"""
                    <html><body style='font-family:sans-serif; background:#0f172a; color:white; display:flex; flex-direction:column; align-items:center; justify-content:center; height:100vh;'>
                        <h1 style='color:#3b82f6;'>Login Successful!</h1>
                        <p>You can now close this tab and return to your terminal.</p>
                        <script>setTimeout(() => window.close(), 3000);</script>
                    </body></html>
                """)
                login_done.set()
            else:
                self.send_response(400)
                self.end_headers()

        def log_message(self, format, *args):
            return # silent

    # Attempt to find an open port
    port = 58261
    try:
        httpd = socketserver.TCPServer(("127.0.0.1", port), LoginHandler)
    except OSError:
        # Fallback to manual if port is blocked
        console.print("[warning]Local auth port 58261 is blocked.[/warning]")
        console.print("Please use: [bold]mlforge login --token YOUR_TOKEN[/bold]")
        return

    # Start server in background thread
    server_thread = threading.Thread(target=httpd.serve_forever)
    server_thread.daemon = True
    server_thread.start()

    callback_url = f"http://127.0.0.1:{port}"
    login_url = f"https://mlforge.in/login?callback={urllib.parse.quote(callback_url)}"
    
    console.print(f"\n[bold blue]Opening browser for authentication...[/bold blue]")
    console.print(f"[dim]URL: {login_url}[/dim]\n")
    
    if not webbrowser.open(login_url):
        console.print("[warning]Could not open browser automatically.[/warning]")
        console.print(f"Please open this link manually: [underline]{login_url}[/underline]\n")

    console.print("[cyan]Waiting for login to complete...[/cyan] (Ctrl+C to cancel)")
    
    try:
        # Wait for callback or timeout (2 mins)
        if login_done.wait(timeout=120):
            token = captured_data["token"]
            user = captured_data.get("user", {})
            save_token(token)
            
            username = user.get("username", "User")
            console.print(f"\n[success]Welcome back, {username}![/success]")
            console.print(f"[green]Authenticated successfully. Session token saved.[/green]")
        else:
            console.print("\n[error]Login timed out after 2 minutes.[/error]")
    except KeyboardInterrupt:
        console.print("\n[yellow]Login cancelled.[/yellow]")
    finally:
        httpd.shutdown()
        httpd.server_close()


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


@app.command("system")
def system_dashboard():
    """Real-time hardware telemetry (CPU, GPU, RAM, Disk)."""
    import psutil
    import platform
    try:
        import cpuinfo
        cpu_brand = cpuinfo.get_cpu_info().get('brand_raw', 'Unknown CPU')
    except Exception:
        cpu_brand = platform.processor()

    # CPU info
    cpu_usage = psutil.cpu_percent(interval=0.5)
    cpu_cores = psutil.cpu_count(logical=False)
    cpu_threads = psutil.cpu_count(logical=True)
    
    # RAM info
    ram = psutil.virtual_memory()
    
    # Disk info
    disk = psutil.disk_usage('/')

    # GPU info (optional)
    gpu_stats = []
    try:
        import pynvml
        pynvml.nvmlInit()
        device_count = pynvml.nvmlDeviceGetCount()
        for i in range(device_count):
            handle = pynvml.nvmlDeviceGetHandleByIndex(i)
            name = pynvml.nvmlDeviceGetName(handle)
            mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
            util = pynvml.nvmlDeviceGetUtilizationRates(handle)
            gpu_stats.append({
                "name": name,
                "used": mem.used / 1024**3,
                "total": mem.total / 1024**3,
                "util": util.gpu
            })
        pynvml.nvmlShutdown()
    except Exception:
        pass

    # Build Panels
    cpu_panel = Panel(
        f"[bold cyan]{cpu_brand}[/bold cyan]\n"
        f"[dim]Cores:[/dim] {cpu_cores} [dim]Threads:[/dim] {cpu_threads}\n"
        f"[bold]Usage:[/bold] [highlight]{cpu_usage}%[/highlight]",
        title="[bold]CPU[/bold]", expand=True
    )

    ram_panel = Panel(
        f"[bold]Total:[/bold] {ram.total / 1024**3:.1f} GB\n"
        f"[bold]Used:[/bold] {ram.used / 1024**3:.1f} GB ([highlight]{ram.percent}%[/highlight])",
        title="[bold]Memory[/bold]", expand=True
    )

    disk_panel = Panel(
        f"[bold]Total:[/bold] {disk.total / 1024**3:.1f} GB\n"
        f"[bold]Free:[/bold] {disk.free / 1024**3:.1f} GB ([highlight]{disk.percent}%[/highlight])",
        title="[bold]Disk[/bold]", expand=True
    )

    console.print(Columns([cpu_panel, ram_panel, disk_panel]))

    if gpu_stats:
        for i, g in enumerate(gpu_stats):
            gpu_panel = Panel(
                f"[bold green]{g['name']}[/bold green]\n"
                f"[bold]VRAM:[/bold] {g['used']:.1f}/{g['total']:.1f} GB\n"
                f"[bold]Utilization:[/bold] [highlight]{g['util']}%[/highlight]",
                title=f"[bold]GPU {i}[/bold]", expand=True
            )
            console.print(gpu_panel)
    else:
        console.print("[dim]No NVIDIA GPU detected or pynvml not installed.[/dim]")


@explore_app.command("models")
def explore_models(
    search: Optional[str] = typer.Option(None, "--search", "-s", help="FTS search query"),
    task: Optional[str] = typer.Option(None, "--task", "-t", help="Filter by task"),
    framework: Optional[str] = typer.Option(None, "--framework", "-f", help="Filter by framework (pytorch|onnx)"),
    hardware: Optional[str] = typer.Option(None, "--hardware", help="Filter by hardware (cpu|cuda)"),
    source: Optional[str] = typer.Option(None, "--source", help="Filter by source (hf|local|onnx)"),
    cached: Optional[bool] = typer.Option(None, "--cached", "-c", help="Show only cached models"),
    sort_by: str = typer.Option("downloads", "--sort-by", help="downloads|accuracy|created_at"),
    sort_dir: str = typer.Option("desc", "--sort-dir", help="asc|desc"),
    limit: int = typer.Option(200, "--limit", help="Max results"),
    offset: int = typer.Option(0, "--offset"),
    host: Optional[str] = typer.Option(None, "--host", help="Backend host"),
    port: Optional[int] = typer.Option(None, "--port", help="Backend port"),
    api_key: Optional[str] = typer.Option(None, "--api-key", envvar="MLFORGE_API_KEY", help="MLForge API Key"),
):
    """List available models in the Model Zoo."""
    host = _unwrap_typer_value(host)
    port = _unwrap_typer_value(port)
    api_key = _unwrap_typer_value(api_key)
    search = _unwrap_typer_value(search)
    task = _unwrap_typer_value(task)
    framework = _unwrap_typer_value(framework)
    hardware = _unwrap_typer_value(hardware)
    source = _unwrap_typer_value(source)
    cached = _unwrap_typer_value(cached)
    sort_by = _unwrap_typer_value(sort_by)
    sort_dir = _unwrap_typer_value(sort_dir)
    limit = _unwrap_typer_value(limit)
    offset = _unwrap_typer_value(offset)

    sdk = _sdk(host, port, api_key)

    
    # Process comma-separated lists for SDK
    frameworks = framework.split(",") if framework else None
    hardwares = hardware.split(",") if hardware else None
    sources = source.split(",") if source else None

    models = sdk.models.list(
        task=task,
        downloaded=cached,
        search=search,
        framework=frameworks,
        hardware=hardwares,
        source=sources,
        sort_by=sort_by,
        sort_dir=sort_dir,
        limit=limit,
        offset=offset
    )
    table = Table(
        title="[bold blue]MLForge Model Zoo[/bold blue]",
        box=None,
        header_style="bold magenta",
        border_style="dim"
    )
    table.add_column("ID", style="dim", width=12)
    table.add_column("Name", style="bold cyan")
    table.add_column("Task", style="green")
    table.add_column("Downloads", justify="right")
    table.add_column("Status", justify="center")

    for m in models:
        status = "[bold green]Cached[/bold green]" if m.downloaded else "[dim]Remote[/dim]"
        downloads = f"{m.downloads:,}" if hasattr(m, 'downloads') and m.downloads else "0"
        table.add_row(m.id, m.name, m.task or "N/A", downloads, status)
    
    console.print(Panel(table, border_style="blue", padding=(1, 2)))


@explore_app.command("download")
def explore_download_model(
    model_id: str = typer.Argument(..., help="The ID of the model to download"),
    host: Optional[str] = typer.Option(None, "--host", help="Backend host"),
    port: Optional[int] = typer.Option(None, "--port", help="Backend port"),
):
    """Download a model to local cache with progress bar."""
    sdk = _sdk(host, port)
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=40),
        TaskProgressColumn(),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        task_id = progress.add_task(f"Downloading {model_id}...", total=100)
        
        job = sdk.models.download(model_id)
        
        while job.status not in ["completed", "failed", "cancelled"]:
            time.sleep(0.5)
            job = sdk.models.get_job(job.id)
            progress.update(task_id, completed=job.progress)
        
        if job.status == "completed":
            console.print(f"[success]Successfully downloaded {model_id}[/success]")
        else:
            console.print(f"[error]Download failed for {model_id}: {job.status}[/error]")

@train_app.command("start")
def train_start(
    project_id: str = typer.Option(..., "--project-id", "-p", help="Project ID"),
    model_id: str = typer.Option(..., "--model-id", "-m", help="Model ID"),
    dataset_id: str = typer.Option(..., "--dataset-id", "-d", help="Dataset ID"),
    task: str = typer.Option("detection", "--task", "-t", help="Task type"),
    epochs: int = typer.Option(50, "--epochs", "-e", help="Number of epochs"),
    batch_size: int = typer.Option(16, "--batch-size", "-b", help="Batch size"),
    learning_rate: float = typer.Option(0.01, "--lr", help="Learning rate"),
    device: str = typer.Option("auto", "--device", help="Device (cpu|cuda|auto)"),
    host: Optional[str] = typer.Option(None, "--host", help="Backend host"),
    port: Optional[int] = typer.Option(None, "--port", help="Backend port"),
):
    """Start a training run with live metrics display."""
    try:
        sdk = _sdk(host, port)

        console.print(f"\n[bold cyan]Starting Training Run[/bold cyan]")
        console.print(f"  Model: [green]{model_id}[/green]")
        console.print(f"  Dataset: [green]{dataset_id}[/green]")
        console.print(f"  Task: [yellow]{task}[/yellow]")
        console.print(f"  Epochs: [blue]{epochs}[/blue]\n")

        # Start training
        with console.status("[yellow]Initializing training...[/yellow]"):
            response = sdk.train.start(
                project_id=project_id,
                model_id=model_id,
                dataset_id=dataset_id,
                task=task,
                epochs=epochs,
                batch_size=batch_size,
                lr=learning_rate,
                device=device,
            )
            run_id = response.get("run_id")

        if not run_id:
            console.print("[error]Failed to start training: no run_id returned[/error]")
            raise typer.Exit(code=1)

        console.print(f"[success]✓ Training started: {run_id}[/success]\n")

        # Monitor progress
        last_epoch = 0
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeRemainingColumn(),
            transient=False,
        ) as progress:
            task_id = progress.add_task(f"Training {model_id}", total=epochs)

            while True:
                try:
                    run = sdk.train.get(run_id)

                    if run.status in ["completed", "failed", "stopped"]:
                        progress.update(task_id, completed=epochs)
                        break

                    if run.epoch > last_epoch:
                        progress.update(task_id, advance=(run.epoch - last_epoch))
                        last_epoch = run.epoch

                    time.sleep(2)
                except Exception as e:
                    console.print(f"[warning]Monitor error: {str(e)}[/warning]")
                    time.sleep(5)

        # Final summary
        run = sdk.train.get(run_id)
        summary_table = Table(title=f"Training Summary - {run_id}", box=None)
        summary_table.add_column("Metric", style="cyan")
        summary_table.add_column("Value", style="green")
        summary_table.add_row("Status", run.status.upper())
        summary_table.add_row("Total Epochs", str(run.epoch))
        for metric_key, metric_val in (run.metrics or {}).items():
            summary_table.add_row(metric_key, f"{metric_val:.4f}")

        console.print(Panel(summary_table, border_style="green", title="[bold green]Complete[/bold green]"))

    except Exception as e:
        _handle_api_error(e)


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
    table.add_column("Best Metric", style="green")
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
    task: Optional[str] = typer.Option(None, "--task", "-t", help="Filter by task"),
    format: Optional[str] = typer.Option(None, "--format", "-f", help="Filter by format (yolo|coco|voc|...)"),
    source: Optional[str] = typer.Option(None, "--source", "-s", help="Filter by source (roboflow|huggingface|local|roboflow_curl)"),
    status: Optional[str] = typer.Option(None, "--status", help="Filter by status (available|imported)"),
    search: Optional[str] = typer.Option(None, "--search", help="Search query"),
    starred: Optional[bool] = typer.Option(None, "--starred", help="Show only starred"),
    limit: int = typer.Option(100, "--limit"),
    offset: int = typer.Option(0, "--offset"),
    cloud: bool = typer.Option(True, "--cloud/--local", help="Use cloud catalog (default) or local engine"),
    host: Optional[str] = typer.Option(None, "--host", help="Backend host"),
    port: Optional[int] = typer.Option(None, "--port", help="Backend port"),
    api_key: Optional[str] = typer.Option(None, "--api-key", envvar="MLFORGE_API_KEY", help="MLForge API Key"),
):
    """List datasets."""
    sdk = MLForge(api_key=api_key) if cloud else _sdk(host, port, api_key)
    datasets = sdk.datasets.list(
        task=task,
        format=format,
        source=source,
        status=status,
        search=search,
        starred=starred,
        limit=limit,
        offset=offset
    )
    table = Table(
        title="[bold blue]Local Datasets[/bold blue]",
        box=None,
        header_style="bold magenta"
    )
    table.add_column("ID", style="dim", width=12)
    table.add_column("Name", style="bold cyan")
    table.add_column("Items", justify="right", style="green")
    table.add_column("Classes", justify="right", style="green")
    table.add_column("Format", style="magenta")

    for d in datasets:
        table.add_row(
            d.id, 
            d.name, 
            f"{d.images:,}" if d.images else "0", 
            str(d.classes or 0), 
            d.format or "N/A"
        )
    
    console.print(Panel(table, border_style="blue", padding=(1, 2)))


@dataset_app.command("search-roboflow")
def dataset_search_roboflow(
    query: str = typer.Argument(..., help="Search query for Roboflow Universe"),
    api_key: str = typer.Option(..., "--api-key", envvar="ROBOFLOW_API_KEY"),
    workspace: Optional[str] = typer.Option(None, "--workspace"),
    page: int = typer.Option(1, "--page"),
    page_size: int = typer.Option(20, "--page-size"),
    cloud: bool = typer.Option(True, "--cloud/--local", help="Use cloud backend (default) or local engine"),
    host: Optional[str] = typer.Option(None, "--host", help="Backend host"),
    port: Optional[int] = typer.Option(None, "--port", help="Backend port"),
):
    """Live search Roboflow Universe."""
    sdk = MLForge() if cloud else _sdk(host, port)
    datasets = sdk.datasets.search_roboflow(
        api_key=api_key,
        query=query,
        workspace=workspace,
        page=page,
        page_size=page_size
    )
    table = Table(title=f"Roboflow Search Results: {query}")
    table.add_column("ID", style="dim")
    table.add_column("Name", style="cyan")
    table.add_column("Images", style="green")
    table.add_column("Classes", style="green")
    for d in datasets:
        table.add_row(d.id, d.name, str(d.images), str(d.classes))
    console.print(table)


@dataset_app.command("sync-roboflow")
def dataset_sync_roboflow(
    api_key: str = typer.Option(..., "--api-key", envvar="ROBOFLOW_API_KEY"),
    workspace: str = typer.Option(..., "--workspace", help="Workspace slug"),
    cloud: bool = typer.Option(True, "--cloud/--local", help="Use cloud backend (default) or local engine"),
    host: Optional[str] = typer.Option(None, "--host", help="Backend host"),
    port: Optional[int] = typer.Option(None, "--port", help="Backend port"),
):
    """Sync all datasets from a Roboflow workspace."""
    sdk = MLForge() if cloud else _sdk(host, port)
    result = sdk.datasets.sync_roboflow(api_key=api_key, workspace=workspace)
    console.print(f"[green]Successfully synced {result.get('synced', 0)} datasets from workspace '{workspace}'[/green]")


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
    
    if hasattr(resp, 'job_id') and resp.job_id:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            task_id = progress.add_task(f"Importing {dataset_id}...", total=100)
            
            while True:
                time.sleep(1)
                job = sdk.models.get_job(resp.job_id) # Using models.get_job as a generic job poller if available
                progress.update(task_id, completed=job.progress)
                if job.status in ["completed", "failed", "cancelled"]:
                    break
            
            if job.status == "completed":
                console.print(f"[success]Successfully imported {dataset_id}[/success]")
            else:
                console.print(f"[error]Import failed: {job.status}[/error]")
    else:
        console.print(f"[success]Dataset import initiated for {dataset_id}[/success]")

@dataset_app.command("analytics")
def dataset_analytics(
    dataset_id: str = typer.Argument(..., help="Dataset ID to analyze"),
    cloud: bool = typer.Option(True, "--cloud/--local"),
    host: Optional[str] = typer.Option(None, "--host"),
    port: Optional[int] = typer.Option(None, "--port"),
):
    """View deep analytics for a dataset (health, quality, distributions)."""
    sdk = MLForge() if cloud else _sdk(host, port)
    with console.status(f"Fetching analytics for {dataset_id}..."):
        a = sdk.datasets.get_analytics(dataset_id)

    # Health Score Panel
    score = a.healthScore
    color = "green" if score >= 8 else "yellow" if score >= 6 else "red"
    health_panel = Panel(
        f"[bold {color}]{score}/10[/bold {color}]\n" +
        ("[dim]Excellent[/dim]" if score >= 8 else "[dim]Good[/dim]" if score >= 6 else "[dim]Needs Attention[/dim]"),
        title="Health Score",
        expand=False
    )

    # Split Panel
    train, val, test = a.split.get("train", 0), a.split.get("val", 0), a.split.get("test", 0)
    split_table = Table.grid(padding=(0, 1))
    split_table.add_row("[blue]Train[/blue]", f"{train}%")
    split_table.add_row("[green]Val[/green]", f"{val}%")
    split_table.add_row("[yellow]Test[/yellow]", f"{test}%")
    split_panel = Panel(split_table, title="Split", expand=False)

    # Quality Panel
    q = a.qualityIssues
    quality_table = Table.grid(padding=(0, 1))
    quality_table.add_row("Missing Labels", f"[red]{q.get('missingLabels', 0)}[/red]")
    quality_table.add_row("Empty Images", f"[yellow]{q.get('emptyImages', 0)}[/yellow]")
    quality_table.add_row("Duplicates", f"[red]{q.get('duplicates', 0)}[/red]")
    quality_panel = Panel(quality_table, title="Quality Issues", expand=False)

    console.print(Columns([health_panel, split_panel, quality_panel]))

    # Class Distribution Table
    if a.classDistribution:
        dist_table = Table(title=f"Class Distribution (Top {len(a.classDistribution)})", box=None)
        dist_table.add_column("Class", style="cyan")
        dist_table.add_column("Count", justify="right")
        dist_table.add_column("Distribution")
        
        max_count = max(c.get("count", 1) for c in a.classDistribution)
        for c in a.classDistribution[:10]:
            count = c.get("count", 0)
            bar_width = int((count / max_count) * 20)
            dist_table.add_row(c.get("name", "—"), str(count), "█" * bar_width)
        
        console.print(dist_table)

@benchmark_app.command("run")
def benchmark_run(
    project_id: str = typer.Option(..., "--project-id", "-p", help="Project ID"),
    model_id: str = typer.Option(..., "--model-id", "-m", help="Model ID"),
    dataset_id: Optional[str] = typer.Option(None, "--dataset-id", "-d", help="Dataset ID (optional)"),
    task: Optional[str] = typer.Option(None, "--task", "-t", help="Task type"),
    framework: str = typer.Option("pytorch", "--framework", "-f", help="Framework"),
    hardware: str = typer.Option("auto", "--hardware", help="Hardware type"),
    precision: str = typer.Option("fp32", "--precision", help="Precision (fp32|fp16|int8)"),
    batch_size: int = typer.Option(32, "--batch-size", "-b", help="Batch size"),
    host: Optional[str] = typer.Option(None, "--host", help="Backend host"),
    port: Optional[int] = typer.Option(None, "--port", help="Backend port"),
):
    """Run a benchmark with live progress and metrics."""
    try:
        sdk = _sdk(host, port)

        console.print(f"\n[bold cyan]Starting Benchmark[/bold cyan]")
        console.print(f"  Model: [green]{model_id}[/green]")
        console.print(f"  Framework: [yellow]{framework}[/yellow]")
        console.print(f"  Precision: [blue]{precision}[/blue]")
        console.print(f"  Hardware: [magenta]{hardware}[/magenta]\n")

        # Start benchmark
        with console.status("[yellow]Initializing benchmark...[/yellow]"):
            response = sdk.benchmark.run(
                project_id=project_id,
                model_id=model_id,
                dataset_id=dataset_id,
                task=task,
                framework=framework,
                hardware=hardware,
                precision=precision,
                batch_size=batch_size,
            )
            job_id = response.get("job_id")

        if not job_id:
            console.print("[error]Failed to start benchmark: no job_id returned[/error]")
            raise typer.Exit(code=1)

        console.print(f"[success]✓ Benchmark started: {job_id}[/success]\n")

        # Monitor progress
        last_progress = 0.0
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeRemainingColumn(),
            transient=False,
        ) as progress:
            bench_task = progress.add_task(f"Benchmarking {model_id}", total=100)

            while True:
                try:
                    job = sdk.benchmark.get_job(job_id)

                    if job.status in ["completed", "failed", "cancelled"]:
                        progress.update(bench_task, completed=100)
                        break

                    current_progress = min(job.progress or last_progress, 99.9)
                    if current_progress > last_progress:
                        progress.update(bench_task, completed=current_progress)
                        last_progress = current_progress

                    time.sleep(1)
                except Exception as e:
                    console.print(f"[warning]Monitor error: {str(e)}[/warning]")
                    time.sleep(5)

        # Fetch and display results
        try:
            result = sdk.benchmark.get_result(job_id)
            metrics_table = Table(title=f"Benchmark Results - {job_id}", box=None)
            metrics_table.add_column("Metric", style="cyan")
            metrics_table.add_column("Value", style="green")

            for key, val in (result.metrics or {}).items():
                if isinstance(val, float):
                    metrics_table.add_row(key, f"{val:.4f}")
                else:
                    metrics_table.add_row(key, str(val))

            console.print(Panel(metrics_table, border_style="green", title="[bold green]Benchmark Complete[/bold green]"))
        except Exception as e:
            console.print(f"[warning]Could not fetch full results: {str(e)}[/warning]")
            console.print(f"[info]Job ID for reference: {job_id}[/info]")

    except Exception as e:
        _handle_api_error(e)


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
    adapter_type: str = typer.Option("auto", "--adapter-type"),
    precision: str = typer.Option("FP16", "--precision"),
    text: Optional[str] = typer.Option(None, "--text", help="Text prompt/input"),
    video: Optional[str] = typer.Option(None, "--video", help="URL to video file"),
    rtsp: Optional[str] = typer.Option(None, "--rtsp", help="RTSP stream URL"),
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
    if adapter_type in ["yolo", "auto"]:
        yolo_cfg = {"confidence": conf, "iou_threshold": iou, "max_detections": max_det}
    
    trans_cfg = None
    if adapter_type in ["transformers", "auto"]:
        trans_cfg = {"temperature": temp, "top_p": top_p, "max_new_tokens": max_tokens}
    
    onnx_cfg = None
    if adapter_type in ["onnx", "auto"]:
        onnx_cfg = {"execution_provider": provider}

    with console.status(f"Running inference with {model_id}..."):
        result = sdk.inference.run(
            model_id,
            image_path=image,
            adapter_type=adapter_type,
            precision=precision,
            text_input=text,
            video_url=video,
            rtsp_url=rtsp,
            yolo_config=yolo_cfg,
            transformers_config=trans_cfg,
            onnx_config=onnx_cfg
        )

    if result.status != "ok":
        console.print(f"[error]Inference failed: {result.error}[/error]")
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


@infer_app.command("stream")
def infer_stream(
    model_id: str = typer.Argument(..., help="Model ID to use"),
    video: Optional[str] = typer.Option(None, "--video", help="URL to video file"),
    rtsp: Optional[str] = typer.Option(None, "--rtsp", help="RTSP stream URL"),
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(8005, "--port"),
):
    """
    Continuous stream inference with a modern dashboard layout.
    Connects to backend WebSockets for live results and logs.
    """
    import asyncio
    import websockets
    from rich.live import Live
    from rich.layout import Layout
    from rich.text import Text
    from rich.logging import RichHandler
    import logging

    # 1. Setup Layout
    layout = Layout()
    layout.split_row(
        Layout(name="logs", ratio=1),
        Layout(name="results", ratio=1)
    )

    log_content = []
    detection_table = Table(title="Live Detections", box=None)
    detection_table.add_column("Frame", style="dim")
    detection_table.add_column("Class", style="cyan")
    detection_table.add_column("Conf", style="green")
    detection_table.add_column("Latency", style="magenta")

    def make_layout():
        # Logs panel
        log_panel = Panel(
            "\n".join(log_content[-15:]), 
            title="[bold blue]Live Events[/bold blue]", 
            border_style="dim"
        )
        layout["logs"].update(log_panel)
        
        # Results panel
        layout["results"].update(Panel(detection_table, title="[bold green]Detections[/bold green]"))
        return layout

    async def run_ws():
        uri = f"ws://{host}:{port}/api/v1/inference/ws/stream" # Check if prefix is needed
        # Actually it's just /inference/ws/stream if following the router prefix in main.py
        # Backend main.py: app.include_router(inference_router.router)
        # inference.py: router = APIRouter(prefix="/inference", ...)
        uri = f"ws://{host}:{port}/inference/ws/stream"

        try:
            async with websockets.connect(uri) as ws:
                # Send start command
                await ws.send(json.dumps({
                    "command": "start",
                    "request": {
                        "model_id": model_id,
                        "adapter_type": "auto",
                        "video_url": video,
                        "rtsp_url": rtsp,
                        "run_mode": "continuous"
                    }
                }))

                while True:
                    msg = await ws.recv()
                    data = json.loads(msg)

                    if data["type"] == "log":
                        d = data["data"]
                        lvl = d.get("level", "INFO")
                        msg_text = d.get("message", "")
                        color = "green" if lvl == "INFO" else "yellow" if lvl == "WARNING" else "red"
                        log_content.append(f"[{color}]{lvl}[/{color}] {msg_text}")
                    
                    elif data["type"] == "frame":
                        fid = data.get("frame_id", 0)
                        lat = data.get("latency_ms", 0)
                        dets = data.get("detections", [])
                        
                        # Clear table but keep headers
                        nonlocal detection_table
                        new_table = Table(title="Live Detections", box=None)
                        new_table.add_column("Frame", style="dim")
                        new_table.add_column("Class", style="cyan")
                        new_table.add_column("Conf", style="green")
                        new_table.add_column("Latency", style="magenta")
                        
                        for det in dets[:10]:
                            new_table.add_row(
                                str(fid),
                                str(det.get("class_name", "—")),
                                f"{det.get('confidence', 0):.2f}",
                                f"{lat:.1f}ms"
                            )
                        detection_table = new_table

                    elif data["type"] == "error":
                        log_content.append(f"[bold red]ERROR: {data.get('message')}[/bold red]")

        except Exception as e:
            log_content.append(f"[bold red]WS Connection Error: {str(e)}[/bold red]")

    try:
        with Live(make_layout(), refresh_per_second=10) as live:
            asyncio.run(run_ws())
    except KeyboardInterrupt:
        console.print("\n[yellow]Streaming stopped.[/yellow]")

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

@app.command("list-models", help="Alias for: explore models")
def list_models_alias(
    ctx: typer.Context,
    task: Optional[str] = typer.Option(None, "--task", "-t"),
    cached: Optional[bool] = typer.Option(None, "--cached", "-c"),
):
    ctx.invoke(explore_models, task=task, cached=cached)


@app.command("download-model", help="Alias for: explore download")
def download_model_alias(ctx: typer.Context, model_id: str = typer.Argument(...)):
    ctx.invoke(explore_download_model, model_id=model_id)


@app.command("list-datasets", help="Alias for: dataset list")
def list_datasets_alias(ctx: typer.Context):
    ctx.invoke(dataset_list)


@app.command("list-runs", help="Alias for: train list-runs")
def list_runs_alias(ctx: typer.Context):
    ctx.invoke(train_list_runs)


@app.command("list-benchmarks", help="Alias for: benchmark results")
def list_benchmarks_alias(ctx: typer.Context):
    ctx.invoke(benchmark_results)


@app.command("run-inference", help="Alias for: infer run")
def run_inference_alias(
    ctx: typer.Context,
    model_id: str = typer.Argument(...),
    image: Optional[str] = typer.Argument(None),
):
    ctx.invoke(infer_run, model_id=model_id, image=image)

def version_callback(value: bool):
    if value:
        console.print(f"MLForge CLI v{VERSION}")
        raise typer.Exit()

@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: Optional[bool] = typer.Option(
        None, "--version", callback=version_callback, is_eager=True, help="Show the version and exit."
    ),
    no_update_check: bool = typer.Option(
        False,
        "--no-update-check",
        envvar="MLFORGE_NO_UPDATE_CHECK",
        help="Disable the PyPI update-availability nudge for this invocation.",
    ),
):
    """
    MLForge CLI - Industrial-Grade ML Platform.
    Manage projects, explore models, and run high-performance training/inference.
    """
    # Surface a one-line PyPI update nudge (read from local cache; never blocks).
    # Skip when running the `update` subcommand itself to avoid noise.
    if not no_update_check and ctx.invoked_subcommand != "update":
        try:
            nudge = _updates.startup_nudge()
            if nudge:
                console.print(f"[dim yellow]{nudge}[/dim yellow]", err=True)
        except Exception:
            pass

    if ctx.invoked_subcommand is None:
        # Print the large ASCII banner
        print_banner()
        
        # Simple "animation" for the entry point subtitle
        subtitle = "Initializing performance-driven AIML engineering environment..."
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
        ) as progress:
            progress.add_task(description=subtitle, total=None)
            time.sleep(1.2)

        console.print("\n[bold blue]CORE MODULES[/bold blue]")
        console.print("[cyan]• Projects[/cyan]      Create and manage your ML workspaces")
        console.print("[cyan]• Explore[/cyan]       Discover 500+ curated models and datasets")
        console.print("[cyan]• Benchmark[/cyan]     Run high-performance hardware tests")
        console.print("[cyan]• Training[/cyan]      Execute and monitor compute-heavy runs")
        console.print("\n[grey50]Type [bold white]mlforge --help[/bold white] to see all available commands[/grey50]\n")

if __name__ == "__main__":
    app()
