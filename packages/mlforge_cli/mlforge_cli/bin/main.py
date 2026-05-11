"""
main.py — FastAPI application entry point.
Wires together all modules, registers middleware/routes, manages lifespan.
"""
from __future__ import annotations

import os
import sys

# Ensure backend root is in sys.path to resolve 'backend.*' imports correctly
# when running from the 'backend' directory.
backend_root = os.path.dirname(os.path.abspath(__file__))
if backend_root not in sys.path:
    sys.path.insert(0, backend_root)

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator

import traceback

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from api.routes import jobs as jobs_router
from api.routes import models as models_router
from api.routes import sync as sync_router
from api.routes import datasets as datasets_router
from api.routes import benchmark as benchmark_router
from api.routes import system as system_router
from api.routes import projects as projects_router
from api.routes import inference as inference_router
from api.routes import training as training_router
from config import settings
from database.connection import close_db, get_db
from middleware.logging_middleware import RequestLoggingMiddleware
from observability.logger import configure_logging, get_logger

# ── Logging bootstrap (must be first) ─────────────────────────────────────────
configure_logging()
log = get_logger("main")


# ── Lifespan ──────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Startup
    settings.ensure_dirs()
    log.info("startup", host=settings.host, port=settings.port, version=settings.version)
    await get_db()   # Bootstrap DB / run migrations
    log.info("database_ready", path=str(settings.db_path))

    # Job Recovery (Cleanup stale imports/benchmarks)
    try:
        from datasets.import_service import recover_stale_jobs
        await recover_stale_jobs()
    except Exception as e:
        log.error("job_recovery_failed", error=str(e))

    if settings.auto_sync_on_startup:
        from registry.registry import count_models

        current = await count_models()
        if current == 0:
            from api.routes.sync import _run_full_sync

            log.info("auto_sync_startup_triggered")
            asyncio.create_task(_run_full_sync())

    yield  # ← app runs

    # Shutdown
    await close_db()
    log.info("shutdown")


# ── Application ───────────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    description="Production ML Model Zoo backend — local-first, traceable, extensible.",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    # Log full traceback for debugging 500s.
    log.error(
        "unhandled_exception",
        path=request.url.path,
        error=str(exc),
        traceback=traceback.format_exc(),
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal Server Error", "error": str(exc)},
    )

# ── Middleware ─────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=r"^https?://(localhost|127\\.0\\.0\\.1)(:\\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestLoggingMiddleware)

# ── Routes ────────────────────────────────────────────────────────────────────
app.include_router(models_router.router)
app.include_router(jobs_router.router)
app.include_router(sync_router.router)
app.include_router(datasets_router.router)
app.include_router(benchmark_router.router)
app.include_router(system_router.router)
app.include_router(projects_router.router)
app.include_router(inference_router.router)
app.include_router(training_router.router)


# ── Static Files (UI) ────────────────────────────────────────────────────────
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    # Mount the assets directory specifically to ensure correct MIME types for JS/CSS
    assets_dir = os.path.join(static_dir, "assets")
    if os.path.exists(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    # Mount the rest of the static files
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/{full_path:path}")
    async def serve_ui(full_path: str):
        # API routes and common system paths
        if full_path.startswith("api/") or full_path in ["health", "docs", "redoc", "openapi.json"]:
            return JSONResponse(status_code=404, content={"detail": "Not Found"})
        
        # Check if the requested file exists in the static directory (for favicon, etc.)
        # This also handles files in /assets if the browser doesn't use the /assets prefix correctly
        file_path = os.path.join(static_dir, full_path)
        
        # IMPORTANT: If it's a request for a file that exists, serve it with proper MIME type.
        # FastAPI's FileResponse handles MIME types based on extension.
        if full_path and os.path.isfile(file_path):
            return FileResponse(file_path)
            
        # Fallback to index.html for SPA routing (only for non-file paths)
        if "." not in full_path:
            index_file = os.path.join(static_dir, "index.html")
            if os.path.exists(index_file):
                return FileResponse(index_file)
        
        return JSONResponse(status_code=404, content={"detail": "Not Found"})


@app.get("/health", tags=["system"])
async def health() -> dict:
    from registry.registry import count_models
    from datasets.registry import count_datasets
    n_models = await count_models()
    n_datasets = await count_datasets()
    return {
        "status": "ok",
        "version": settings.version,
        "model_count": n_models,
        "dataset_count": n_datasets,
    }


# ── Dev runner ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_config=None,  # We use structlog
    )
