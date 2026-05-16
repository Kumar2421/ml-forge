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

BANNER = """
[bold blue]
 ███╗   ███╗██╗     ███████╗ ██████╗ ██████╗  ██████╗ ███████╗
 ████╗ ████║██║     ██╔════╝██╔═══██╗██╔══██╗██╔════╝ ██╔════╝
 ██╔████╔██║██║     █████╗  ██║   ██║██████╔╝██║  ███╗█████╗  
 ██║╚██╔╝██║██║     ██╔══╝  ██║   ██║██╔══██╗██║   ██║██╔══╝  
 ██║ ╚═╝ ██║███████╗██║     ╚██████╔╝██║  ██║╚██████╔╝███████╗
 ╚═╝     ╚═╝╚══════╝╚═╝      ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚══════╝
[/bold blue]
[dim]Industrial-Grade ML Workspace | v0.1.1[/dim]
"""

def print_banner():
    console.print(Align.center(BANNER))

app = typer.Typer(
    help="MLForge CLI - Industrial-grade ML Workspace",
    rich_markup_mode="rich"
)

@app.callback(invoke_without_command=True)
def main_callback(
    ctx: typer.Context,
    version: bool = typer.Option(None, "--version", "-v", help="Show version"),
):
    """Entry point for MLForge CLI."""
    if version:
        console.print("[bold blue]MLForge CLI[/bold blue] [dim]v0.1.1[/dim]")
        raise typer.Exit()
    
    if ctx.invoked_subcommand is None:
        print_banner()
        console.print("\n[bold]Usage:[/bold] mlforge [COMMAND] [ARGS]...")
        console.print("[dim]Run 'mlforge --help' for available commands.[/dim]")

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
        console.print(f"MLForge CLI v0.1.0")
        raise typer.Exit()

@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: Optional[bool] = typer.Option(
        None, "--version", callback=version_callback, is_eager=True, help="Show the version and exit."
    ),
):
    """
    MLForge CLI - Industrial-Grade ML Platform.
    Manage projects, explore models, and run high-performance training/inference.
    """
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
