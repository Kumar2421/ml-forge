"""
datasets/import_service.py — Dataset Import Pipeline.

Pipeline stages:
  1. Create job record
  2. Download dataset zip (chunked, progress-tracked)
  3. Extract zip safely (path-traversal protected)
  4. Detect annotation format & task type
  5. Index images into dataset_images table
  6. Parse & store metadata (Stats only, annotations are read-on-demand)
  7. Update dataset stats (images, classes, size)
  8. Mark job completed / failed

All stages run as background tasks.
Supports Roboflow, HuggingFace, and local file/folder imports.
"""
from __future__ import annotations

import asyncio
import hashlib
import os
import shutil
import uuid
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple

import aiofiles
import httpx
from huggingface_hub import snapshot_download

from config import settings
from . import registry as ds_reg
from .format_adapters import (
    YOLOAdapter, COCOAdapter, VOCAdapter, CreateMLAdapter, 
    RoboflowClassificationAdapter, NLPAdapter, TabularAdapter
)
from .base_adapter import DatasetAdapter
from .annotation_parser import _img_dimensions
from observability.logger import audit, get_logger
from models.dataset import DatasetStatus, DatasetTask, ImportRequest, Dataset

log = get_logger("import_service")

ADAPTERS: List[DatasetAdapter] = [
    YOLOAdapter(),
    COCOAdapter(),
    VOCAdapter(),
    CreateMLAdapter(),
    RoboflowClassificationAdapter(),
    NLPAdapter(),
    TabularAdapter(),
]

def get_adapter_for_path(path: Path) -> DatasetAdapter | None:
    for adapter in ADAPTERS:
        if adapter.detect(path):
            return adapter
    return None

async def recover_stale_jobs() -> None:
    """Cleanup dataset import jobs that were left in 'running' or 'queued' state."""
    await ds_reg.cleanup_stale_jobs()

def _dataset_path(dataset_id: str) -> Path:
    return settings.datasets_dir / dataset_id

# ── Entry Point ──────────────────────────────────────────────────────────────

async def start_import(req: ImportRequest) -> str:
    """Entry point to initiate a background import job."""
    job_id = f"job-{uuid.uuid4().hex[:8]}"
    
    # Create initial job record
    await ds_reg.update_job(
        job_id,
        dataset_id=req.dataset_id,
        status="queued",
        progress=0,
        message="Import queued",
        type=str(req.source)
    )

    # Launch background task
    asyncio.create_task(_run_pipeline(job_id, req, req.dataset_name or req.dataset_id))
    
    return job_id


# ── Pipeline orchestrator ────────────────────────────────────────────────────

async def _run_pipeline(job_id: str, req: ImportRequest, dataset_name: str) -> None:
    started = datetime.utcnow().isoformat()
    await ds_reg.update_job(job_id, status="running", started_at=started, message="Starting import")
    await ds_reg.update_dataset_status(req.dataset_id, DatasetStatus.importing, progress=0.01)

    try:
        # Stage 1 – Resolve download URL or local path
        source_path = await _stage_acquire(job_id, req)

        # Stage 2 – Extract / Prepare Directory
        extract_dir = await _stage_extract(job_id, req.dataset_id, source_path)

        # Stage 3 – Detect adapter and Task
        await ds_reg.update_job(job_id, progress=0.55, message="Detecting dataset format...")
        adapter = await asyncio.to_thread(get_adapter_for_path, extract_dir)
        
        if not adapter:
            log.warning("no_adapter_found_generic_fallback", dataset_id=req.dataset_id)
            image_records = await asyncio.to_thread(_scan_images_generic, req.dataset_id, extract_dir)
            class_names = []
            task = DatasetTask.classification
            fmt_name = "custom"
        else:
            task = adapter.get_task(extract_dir)
            fmt_name = adapter.__class__.__name__.replace("Adapter", "").lower()
            
            log.info("adapter_detected", job_id=job_id, format=fmt_name, task=task)
            await ds_reg.update_job(job_id, progress=0.60, message=f"Parsing {fmt_name.upper()} {task.upper()}")

            # Stage 4 – Parse Metadata & Annotations (Streaming)
            class_names = await asyncio.to_thread(adapter.get_class_names, extract_dir)
            image_records = []
            all_annotations = []
            
            # Health metrics tracking
            hashes = {} # hash -> filename
            duplicates = 0
            empty_images = 0
            total_ann_count = 0
            
            for img_rec, anns in adapter.iter_items(req.dataset_id, extract_dir):
                # Duplicate detection via MD5 hash
                abs_path = extract_dir / img_rec["rel_path"]
                if abs_path.exists():
                    img_hash = _calculate_hash(abs_path)
                    if img_hash in hashes:
                        duplicates += 1
                        img_rec["metadata"] = json.dumps({"is_duplicate": True, "original": hashes[img_hash]})
                    else:
                        hashes[img_hash] = img_rec["filename"]
                
                if not anns:
                    empty_images += 1
                
                total_ann_count += len(anns)
                image_records.append(img_rec)
                all_annotations.extend(anns)

        if not image_records:
            raise ValueError(f"No valid data files found in {extract_dir}")

        # Stage 5 – Indexing
        await ds_reg.update_job(job_id, progress=0.80, message=f"Indexing {len(image_records)} items")
        await ds_reg.index_images(req.dataset_id, image_records)
        
        if all_annotations:
            await ds_reg.update_job(job_id, progress=0.85, message=f"Indexing {len(all_annotations)} annotations")
            await ds_reg.bulk_insert_annotations(all_annotations)

        # Stage 6 – Stats & Health Analysis
        size_bytes = await asyncio.to_thread(_dir_size, extract_dir)
        
        # Calculate Health Score (0-100)
        # Factors: duplicates, empty images (for detection), class balance (TODO)
        score = 100.0
        if len(image_records) > 0:
            dup_penalty = (duplicates / len(image_records)) * 50
            empty_penalty = (empty_images / len(image_records)) * 20 if task == DatasetTask.detection else 0
            score = max(0.0, 100.0 - dup_penalty - empty_penalty)

        stats_payload = {
            "image_count": len(image_records),
            "annotation_count": total_ann_count,
            "class_count": len(class_names),
            "empty_images": empty_images,
            "duplicate_count": duplicates,
            "health_score": round(score, 1),
            "avg_objects": round(total_ann_count / len(image_records), 2) if image_records else 0
        }

        await ds_reg.update_dataset_stats(
            req.dataset_id, 
            len(image_records), 
            len(class_names), 
            class_names, 
            size_bytes,
            stats=stats_payload
        )
        await ds_reg.update_dataset_task(req.dataset_id, task)

        # Cleanup temp zip if applicable
        if source_path.is_file() and source_path.suffix.lower() == ".zip" and "_tmp" in str(source_path):
            source_path.unlink(missing_ok=True)

        # Stage 7 – Project Linking (Integration point)
        local_path = str(extract_dir)
        from projects.service import link_dataset_to_active_project
        project_ds_root = await link_dataset_to_active_project(req.dataset_id, local_path)
        final_local_path = str(project_ds_root) if project_ds_root and project_ds_root.exists() else local_path

        # Completion
        await ds_reg.update_job(
            job_id, status="completed", progress=1.0,
            message="Import complete", ended_at=datetime.utcnow().isoformat(),
        )
        await ds_reg.update_dataset_status(req.dataset_id, DatasetStatus.imported, progress=1.0, local_path=final_local_path)
        await audit("dataset_import_complete", {"job_id": job_id, "path": final_local_path}, job_id=job_id)
        log.info("import_complete", job_id=job_id, dataset_id=req.dataset_id)

    except asyncio.CancelledError:
        await _fail_job(job_id, req.dataset_id, "Import cancelled by user or system")
        raise
    except Exception as exc:
        log.error("import_failed", job_id=job_id, error=str(exc))
        await _fail_job(job_id, req.dataset_id, str(exc))
        await audit("dataset_import_error", {"job_id": job_id, "error": str(exc)}, job_id=job_id, level="error")


async def _fail_job(job_id: str, dataset_id: str, error: str) -> None:
    await ds_reg.update_job(
        job_id, status="failed", error=error,
        ended_at=datetime.utcnow().isoformat(),
        message="Import failed",
    )
    await ds_reg.update_dataset_status(dataset_id, DatasetStatus.failed, progress=0.0)


# ── Stage 1: Acquire source ──────────────────────────────────────────────────

async def _stage_acquire(job_id: str, req: ImportRequest) -> Path:
    """Resolves the source (Download URL, HF Repo, or Local Path)."""
    await ds_reg.update_job(job_id, progress=0.05, message="Acquiring source...")

    if req.source in ("roboflow", "roboflow_curl"):
        return await _acquire_roboflow(job_id, req)
    
    if req.source == "huggingface":
        return await _acquire_huggingface(job_id, req)
    
    if req.source == "local":
        return await _acquire_local(job_id, req)

    raise ValueError(f"Unsupported source provider: {req.source}")


async def _acquire_roboflow(job_id: str, req: ImportRequest) -> Path:
    """Specialized Roboflow downloader using SDK or direct link."""
    # Attempt SDK first (more reliable for Universe)
    try:
        from roboflow import Roboflow
        api_key = req.roboflow_key or (req.headers.get("Authorization") if req.headers else None)
        if api_key and "Bearer " in str(api_key):
            api_key = api_key.split("Bearer ")[-1].strip()
        
        if api_key and req.roboflow_workspace and req.roboflow_project:
            rf = Roboflow(api_key=api_key)
            project = rf.workspace(req.roboflow_workspace).project(req.roboflow_project)
            version_obj = project.version(req.roboflow_version or 1)
            
            tmp_target = DATASETS_ROOT / "_tmp" / f"rf-{uuid.uuid4().hex[:8]}"
            await ds_reg.update_job(job_id, progress=0.10, message="Downloading via Roboflow SDK...")
            
            # Threaded SDK call
            await asyncio.to_thread(
                version_obj.download, 
                _format_to_rf_slug(str(req.format)), 
                location=str(tmp_target)
            )
            return tmp_target
    except Exception as e:
        log.warning("roboflow_sdk_fallback", error=str(e))

    # Fallback to direct HTTP download
    url = req.download_url
    if not url and req.source == "roboflow":
        from adapters.roboflow_adapter import RoboflowAdapter
        url = await RoboflowAdapter.get_download_url(
            api_key=req.roboflow_key,
            workspace=req.roboflow_workspace,
            project_id=req.roboflow_project,
            version=req.roboflow_version,
            export_format=_format_to_rf_slug(str(req.format)),
        )
    
    if not url:
        raise ValueError("Could not resolve Roboflow download URL")
        
    return await _download_zip(job_id, req.dataset_id, url, req.headers)


async def _acquire_huggingface(job_id: str, req: ImportRequest) -> Path:
    if not req.hf_dataset_id:
        raise ValueError("hf_dataset_id is missing")
    
    dest_dir = _dataset_path(req.dataset_id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    
    await ds_reg.update_job(job_id, progress=0.10, message=f"Cloning {req.hf_dataset_id} from HF...")
    
    await asyncio.to_thread(
        snapshot_download,
        repo_id=req.hf_dataset_id,
        repo_type="dataset",
        local_dir=str(dest_dir),
        token=settings.hf_token,
        local_dir_use_symlinks=False
    )
    return dest_dir


async def _acquire_local(job_id: str, req: ImportRequest) -> Path:
    if not req.local_path:
        raise ValueError("local_path is missing for local import")
    
    path = Path(os.path.normpath(req.local_path.strip().strip('"').strip("'")))
    if not path.exists():
        raise FileNotFoundError(f"Local path does not exist: {path}")
    
    return path


# ── Stage 2: Extraction ──────────────────────────────────────────────────────

async def _stage_extract(job_id: str, dataset_id: str, source_path: Path) -> Path:
    dest = _dataset_path(dataset_id)
    dest.mkdir(parents=True, exist_ok=True)

    if source_path.is_dir():
        if source_path == dest:
            return dest
        await ds_reg.update_job(job_id, progress=0.45, message="Copying local files...")
        await asyncio.to_thread(_copy_dir_contents, source_path, dest)
        return dest

    # It's a zip
    await ds_reg.update_job(job_id, progress=0.45, message="Extracting archive...")
    await ds_reg.update_dataset_status(dataset_id, DatasetStatus.extracting, progress=0.45)
    await asyncio.to_thread(_safe_extract, source_path, dest)
    return dest


# ── Stage 3: Parsing (Memory-Safe) ───────────────────────────────────────────

def _heuristic_task_detection(fmt: str, root: Path) -> DatasetTask:
    """Improved task detection based on file content."""
    if fmt == "csv":
        return DatasetTask.nlp
    
    # Check for segmentation in COCO
    if fmt == "coco":
        # Sample first few lines of JSON if possible or check file size
        return DatasetTask.segmentation # Heuristic: most modern COCO use cases
        
    if fmt in ("yolo", "voc"):
        return DatasetTask.detection
        
    return DatasetTask.classification


def _parse_yolo(dataset_id: str, root: Path) -> Tuple[List[str], List[Tuple[Dict, List[Dict]]]]:
    class_map = YOLOParser.load_class_map(root)
    results = []
    # Generator approach to keep memory low
    for rel_path, image_id, split, anns in YOLOParser.iter_dataset(root, dataset_id, class_map):
        abs_path = root / rel_path
        w, h = _img_dimensions(abs_path)
        img_rec = {
            "id": image_id, "filename": Path(rel_path).name,
            "rel_path": str(rel_path), "width": w, "height": h,
            "split": split, "ann_count": len(anns),
        }
        results.append((img_rec, anns))
    return class_map, results


def _parse_coco(dataset_id: str, root: Path) -> Tuple[List[str], List[Tuple[Dict, List[Dict]]]]:
    ann_files = COCOParser.find_annotation_files(root)
    all_classes: list[str] = []
    results = []
    for ann_file in ann_files:
        classes, coco_results = COCOParser.parse_file(ann_file, dataset_id)
        all_classes = list(dict.fromkeys(all_classes + classes))
        for rel_path, image_id, split, anns in coco_results:
            abs_path = root / rel_path
            w, h = _img_dimensions(abs_path)
            img_rec = {
                "id": image_id, "filename": Path(rel_path).name,
                "rel_path": str(rel_path), "width": w, "height": h,
                "split": split, "ann_count": len(anns),
            }
            results.append((img_rec, anns))
    return all_classes, results


def _parse_voc(dataset_id: str, root: Path) -> Tuple[List[str], List[Tuple[Dict, List[Dict]]]]:
    class_set = set()
    results = []
    for rel_path, image_id, split, w, h, anns in VOCParser.iter_dataset(root, dataset_id):
        img_rec = {
            "id": image_id, "filename": Path(rel_path).name,
            "rel_path": str(rel_path), "width": w, "height": h,
            "split": split, "ann_count": len(anns),
        }
        results.append((img_rec, anns))
        for ann in anns:
            class_set.add(ann["label"])
    return sorted(list(class_set)), results


def _parse_csv(dataset_id: str, root: Path) -> Tuple[List[str], List[Tuple[Dict, List[Dict]]]]:
    all_classes = set()
    results = []
    for csv_path in root.rglob("*.csv"):
        anns = CSVParser.parse_file(csv_path, dataset_id)
        # For CSV, each annotation is a row. We group by text entry id (image_id)
        anns_by_id: Dict[str, List[Dict]] = {}
        for ann in anns:
            all_classes.add(ann["label"])
            anns_by_id.setdefault(ann["image_id"], []).append(ann)
        
        for text_id, grouped_anns in anns_by_id.items():
            img_rec = {
                "id": text_id, "filename": csv_path.name,
                "rel_path": str(csv_path.relative_to(root)),
                "width": 0, "height": 0, "split": "train", "ann_count": len(grouped_anns),
            }
            results.append((img_rec, grouped_anns))
    return sorted(list(all_classes)), results


def _parse_txt(dataset_id: str, root: Path) -> Tuple[List[str], List[Tuple[Dict, List[Dict]]]]:
    from datasets.annotation_parser import RoboflowTXTParser
    results = []
    class_set = set()
    
    for rel_path, image_id, split, anns in RoboflowTXTParser.iter_dataset(root, dataset_id):
        abs_path = root / rel_path
        w, h = _img_dimensions(abs_path)
        img_rec = {
            "id": image_id, "filename": Path(rel_path).name,
            "rel_path": str(rel_path), "width": w, "height": h,
            "split": split, "ann_count": len(anns),
        }
        results.append((img_rec, anns))
        for ann in anns:
            class_set.add(ann["label"])
            
    return sorted(list(class_set)), results


def _parse_generic_folder(dataset_id: str, root: Path) -> Tuple[List[str], List[Tuple[Dict, List[Dict]]]]:
    """
    Enhanced generic folder parser. Supports:
    1. root/class_name/img.jpg
    2. root/train/class_name/img.jpg
    3. root/images/img.jpg
    """
    results = []
    class_set = set()
    exts = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}
    
    # Structural keywords to ignore as classes
    ignore = {"images", "labels", "train", "val", "test", "validation", "training", "valid", "testing", "unknown", "annotations"}

    for img_path in sorted(root.rglob("*")):
        if img_path.suffix.lower() not in exts:
            continue
            
        rel_path = img_path.relative_to(root)
        parts = rel_path.parts
        
        # Heuristic for class detection
        label = "unknown"
        split = "train"
        
        # Detect split if first folder is a split keyword
        if parts[0].lower() in ignore and len(parts) > 1:
            if parts[0].lower() in ("train", "training"): split = "train"
            elif parts[0].lower() in ("val", "valid", "validation"): split = "val"
            elif parts[0].lower() in ("test", "testing"): split = "test"

            # Check if next part is class name
            if len(parts) > 2 and parts[1].lower() not in ignore:
                label = parts[1]
            elif len(parts) > 1 and parts[1].lower() not in ignore:
                label = parts[1]
        elif len(parts) > 1 and parts[0].lower() not in ignore:
            label = parts[0]

        anns = []
        if label != "unknown":
            class_set.add(label)
            image_id = f"img-{uuid.uuid4().hex[:12]}"
            # Create a virtual annotation for classification
            from datasets.annotation_parser import _make_ann
            anns.append(_make_ann(image_id, dataset_id, label, ann_type="classification"))
        else:
            image_id = f"img-{uuid.uuid4().hex[:12]}"
            
        w, h = _img_dimensions(img_path)
        img_rec = {
            "id": image_id,
            "filename": img_path.name,
            "rel_path": str(rel_path),
            "width": w, "height": h,
            "split": split,
            "ann_count": len(anns),
        }
        results.append((img_rec, anns))
        
    return sorted(list(class_set)), results


# ── Utilities ────────────────────────────────────────────────────────────────

async def _download_zip(job_id: str, dataset_id: str, url: str, custom_headers: dict = None) -> Path:
    tmp_dir = DATASETS_ROOT / "_tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    zip_path = tmp_dir / f"{dataset_id}-{uuid.uuid4().hex[:8]}.zip"

    headers = {
        "User-Agent": "Mozilla/5.0 (MLForge Workbench)",
        "Accept": "application/zip, application/octet-stream, */*",
    }
    if custom_headers: headers.update(custom_headers)

    async with httpx.AsyncClient(follow_redirects=True, timeout=600.0, headers=headers) as client:
        async with client.stream("GET", url) as resp:
            resp.raise_for_status()
            total = int(resp.headers.get("content-length", 0)) or None
            downloaded = 0
            async with aiofiles.open(zip_path, "wb") as f:
                async for chunk in resp.aiter_bytes(chunk_size=settings.download_chunk_size):
                    await f.write(chunk)
                    downloaded += len(chunk)
                    if total:
                        pct = 0.10 + (downloaded / total) * 0.35 # 10% -> 45%
                        await ds_reg.update_job(job_id, progress=round(pct, 3), message=f"Downloading: {_fmt_bytes(downloaded)} / {_fmt_bytes(total)}")

    return zip_path


def _safe_extract(zip_path: Path, dest: Path) -> None:
    with zipfile.ZipFile(str(zip_path), "r") as zf:
        for member in zf.namelist():
            if os.path.isabs(member) or ".." in Path(member).parts: continue
            zf.extract(member, str(dest))


def _copy_dir_contents(src: Path, dest: Path) -> None:
    for item in src.iterdir():
        s, d = src / item.name, dest / item.name
        if s.is_dir(): shutil.copytree(s, d, dirs_exist_ok=True)
        else: shutil.copy2(s, d)


def _scan_images_generic(dataset_id: str, root: Path) -> list[dict]:
    records = []
    exts = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
    for img_path in sorted(root.rglob("*")):
        if img_path.suffix.lower() in exts:
            w, h = _img_dimensions(img_path)
            records.append({
                "id": f"img-{uuid.uuid4().hex[:12]}",
                "filename": img_path.name,
                "rel_path": str(img_path.relative_to(root)),
                "width": w, "height": h, "split": "train", "ann_count": 0,
            })
    return records


def _dir_size(path: Path) -> int:
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


def _fmt_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024: return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


def _format_to_rf_slug(fmt: str) -> str:
    return {"yolo": "yolov8", "coco": "coco", "voc": "voc"}.get(fmt, "yolov8")

def _format_to_rf_slug(fmt: str) -> str:
    return {"yolo": "yolov8", "coco": "coco", "voc": "voc"}.get(fmt, "yolov8")
