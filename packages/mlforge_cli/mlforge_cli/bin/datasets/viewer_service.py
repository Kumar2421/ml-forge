"""
datasets/viewer_service.py — Dataset Viewer Service.

Provides paginated image + annotation serving for the Dataset Viewer UI.
All paths are resolved relative to the dataset's local_path for security.
"""
from __future__ import annotations

from pathlib import Path

from datasets import registry as ds_reg
from models.dataset import (
    Annotation, AnnotationType, BoundingBox, Dataset,
    ImageRecord, ViewerPage, DatasetFormat
)
from datasets.annotation_parser import YOLOParser, COCOParser, VOCParser, CSVParser
from observability.logger import get_logger

log = get_logger("viewer_service")


from .format_adapters import NLPAdapter, TabularAdapter
from models.dataset import UniversalViewerPage, UniversalDatasetItem, UniversalAnnotation, DatasetContentType, DatasetTask

async def get_universal_viewer_page(
    dataset_id: str,
    page: int = 0,
    page_size: int = 20,
    split: str | None = None,
    class_label: str | None = None,
) -> UniversalViewerPage:
    """Polymorphic viewer endpoint that adapts based on dataset task."""
    ds = await ds_reg.get_dataset(dataset_id)
    if not ds:
        raise ValueError("Dataset not found")
        
    ds_root = Path(ds.local_path) if ds.local_path else None
    
    # 1. Vision Tasks (Detection, Seg, Pose) -> Use existing image-centric logic
    if ds.task in (DatasetTask.detection, DatasetTask.segmentation, DatasetTask.keypoints):
        # We wrap the existing get_viewer_page and transform to UniversalDatasetItem
        old_page = await get_viewer_page(dataset_id, page, page_size, split, class_label)
        
        items = []
        for img in old_page.images:
            items.append(UniversalDatasetItem(
                id=img.image_id,
                content_type=DatasetContentType.image,
                filename=img.filename,
                metadata={"width": img.width, "height": img.height, "split": img.split},
                annotations=[
                    UniversalAnnotation(
                        label=ann.label,
                        type=ann.type.value if hasattr(ann.type, 'value') else str(ann.type),
                        bbox=[ann.bbox.x, ann.bbox.y, ann.bbox.width, ann.bbox.height] if ann.bbox else None,
                        segmentation=ann.segmentation,
                        keypoints=ann.keypoints,
                        confidence=ann.confidence,
                        metadata=ann.metadata
                    ) for ann in img.annotations
                ]
            ))
        
        return UniversalViewerPage(
            dataset_id=dataset_id,
            page=page,
            page_size=page_size,
            total=old_page.total,
            total_pages=old_page.total_pages,
            items=items
        )

    # 2. NLP Tasks (CSV, JSONL)
    elif ds.task == DatasetTask.nlp and ds_root:
        adapter = NLPAdapter()
        total, items = await adapter.get_items(ds_root, page, page_size)
        total_pages = max(1, (total + page_size - 1) // page_size)
        return UniversalViewerPage(
            dataset_id=dataset_id,
            page=page,
            page_size=page_size,
            total=total,
            total_pages=total_pages,
            items=items
        )

    # 3. Tabular Tasks (CSV, Parquet)
    elif ds.task == DatasetTask.tabular and ds_root:
        adapter = TabularAdapter()
        total, items = await adapter.get_items(ds_root, page, page_size)
        total_pages = max(1, (total + page_size - 1) // page_size)
        return UniversalViewerPage(
            dataset_id=dataset_id,
            page=page,
            page_size=page_size,
            total=total,
            total_pages=total_pages,
            items=items
        )

    # Fallback / Empty
    return UniversalViewerPage(
        dataset_id=dataset_id,
        page=page,
        page_size=page_size,
        total=0,
        total_pages=0,
        items=[]
    )

async def get_viewer_page(
    dataset_id: str,
    page: int = 0,
    page_size: int = 20,
    split: str | None = None,
    class_label: str | None = None,
) -> ViewerPage:
    """
    Return a paginated viewer page for the dataset.
    Images come from the index; annotations are loaded per-image.
    """
    if page_size > 100:
        page_size = 100   # cap to prevent huge payloads

    total, image_rows = await ds_reg.get_image_page(dataset_id, page, page_size, split, class_label)
    ds = await ds_reg.get_dataset(dataset_id)
    
    # Check if we have an active project and if the dataset exists there
    from projects.service import get_active_project_path
    project_path = await get_active_project_path()
    
    # Dynamically load annotations from database first, fallback to filesystem if needed
    image_ids = [row["id"] for row in image_rows]
    dynamic_anns: dict[str, list[Annotation]] = {img_id: [] for img_id in image_ids}

    # 1. Try loading from DB index (Authoritative for analytics)
    try:
        from database.connection import get_db
        db = await get_db()
        # Fetch all annotations for these images in one go
        placeholders = ",".join(["?"] * len(image_ids))
        async with db.execute(
            f"SELECT * FROM dataset_annotations WHERE image_id IN ({placeholders})",
            image_ids
        ) as cur:
            rows = await cur.fetchall()
            for r in rows:
                dynamic_anns[r["image_id"]].append(_row_to_annotation(dict(r)))
    except Exception as e:
        log.warning("db_annotation_read_failed", error=str(e), dataset_id=dataset_id)

    # 2. Fallback to filesystem if no annotations found in DB and we have a path
    # This maintains compatibility with old datasets or specific live-read needs
    if all(not anns for anns in dynamic_anns.values()) and ds and ds.local_path:
        ds_root = Path(ds.local_path)
        # Use ds.local_path directly as it is now authoritative project-local path
        # Fallback to global removed per user request

        fmt = ds.format.value if hasattr(ds.format, 'value') else str(ds.format)
        
        try:
            if fmt == DatasetFormat.yolo.value or fmt == "yolo":
                class_map = YOLOParser.load_class_map(ds_root)
                for row in image_rows:
                    rel_path = Path(row["rel_path"])
                    # For YOLO, the label file is usually in a parallel 'labels' folder
                    # or in the same folder as the image.
                    # Roboflow structure: train/images/img.jpg -> train/labels/img.txt
                    parts = list(rel_path.parts)
                    
                    label_rel = None
                    if "images" in parts:
                        idx = parts.index("images")
                        parts_labels = list(parts)
                        parts_labels[idx] = "labels"
                        label_rel = Path(*parts_labels).with_suffix(".txt")
                    
                    # Fallback: same folder
                    label_same_folder = rel_path.with_suffix(".txt")
                    
                    for cand_rel in [label_rel, label_same_folder]:
                        if not cand_rel: continue
                        label_file = ds_root / cand_rel
                        if label_file.exists():
                            anns = YOLOParser.parse_file(label_file, row["id"], ds.id, class_map)
                            dynamic_anns[row["id"]] = [_row_to_annotation(a) for a in anns]
                            break

            elif fmt == DatasetFormat.coco.value or fmt == "coco":
                jsons = COCOParser.find_annotation_files(ds_root)
                img_map = {row["filename"]: row["id"] for row in image_rows}
                for jf in jsons:
                    _, parsed = COCOParser.parse_file(jf, ds.id)
                    for p_rel, _, _, anns in parsed:
                        fname = Path(p_rel).name
                        if fname in img_map:
                            img_id = img_map[fname]
                            dynamic_anns[img_id].extend([_row_to_annotation(a) for a in anns])

            elif fmt == DatasetFormat.voc.value or fmt == "voc":
                for row in image_rows:
                    img_abs = ds_root / row["rel_path"]
                    xml_candidates = [img_abs.with_suffix(".xml")]
                    parts = list(Path(row["rel_path"]).parts)
                    if "JPEGImages" in parts:
                        idx = parts.index("JPEGImages")
                        parts[idx] = "Annotations"
                        xml_candidates.append(ds_root.joinpath(*parts).with_suffix(".xml"))
                    
                    for cand in xml_candidates:
                        if cand.exists():
                            _, _, _, anns = VOCParser.parse_file(cand, row["id"], ds.id)
                            dynamic_anns[row["id"]] = [_row_to_annotation(a) for a in anns]
                            break

            elif fmt == "csv":
                for row in image_rows:
                    csv_path = ds_root / row["rel_path"]
                    if csv_path.exists():
                        # For CSV/NLP, we might need a more specific way to find the exact row,
                        # but for now we reload the file or use a cached version.
                        # Since get_viewer_page is paginated, we'll parse the file.
                        anns = CSVParser.parse_file(csv_path, ds.id)
                        # Find the annotation matching this "image_id" (which is the text entry id)
                        matching_anns = [a for a in anns if a["image_id"] == row["id"]]
                        dynamic_anns[row["id"]] = [_row_to_annotation(a) for a in matching_anns]

        except Exception as e:
            log.error("dynamic_annotation_read_failed", error=str(e), dataset_id=dataset_id)

    images: list[ImageRecord] = []
    for row in image_rows:
        annotations = dynamic_anns.get(row["id"], [])
        images.append(ImageRecord(
            image_id    = row["id"],
            filename    = row["filename"],
            width       = row["width"],
            height      = row["height"],
            path        = row["rel_path"],
            annotations = annotations,
            split       = row["split"],
        ))

    total_pages = max(1, (total + page_size - 1) // page_size)

    return ViewerPage(
        dataset_id  = dataset_id,
        page        = page,
        page_size   = page_size,
        total       = total,
        total_pages = total_pages,
        images      = images,
    )


def _row_to_annotation(row: dict) -> Annotation:
    bbox = None
    if row.get("bbox_x") is not None:
        bbox = BoundingBox(
            x         = row["bbox_x"],
            y         = row["bbox_y"],
            width     = row["bbox_w"],
            height    = row["bbox_h"],
            normalised = bool(row.get("normalised", 1)),
        )
    
    segmentation = None
    if row.get("segmentation"):
        try:
            import json
            segmentation = json.loads(row["segmentation"])
        except:
            pass

    return Annotation(
        label        = row["label"],
        bbox         = bbox,
        segmentation = segmentation,
        confidence   = row.get("confidence"),
        area         = row.get("area"),
        type         = AnnotationType(row.get("ann_type", "detection")),
    )


async def resolve_image_path(dataset_id: str, image_id: str) -> Path | None:
    """
    Resolve the absolute filesystem path for an image.
    Prioritizes the active project's dataset folder, falling back to the global cache.
    Returns None if dataset not imported or image not found.
    """
    ds = await ds_reg.get_dataset(dataset_id)
    if ds is None or not ds.local_path:
        return None

    base_root = Path(ds.local_path)
    # ds.local_path is now authoritative project-local path
    # Fallback removed per user request

    from database.connection import get_db
    db = await get_db()
    async with db.execute(
        "SELECT rel_path FROM dataset_images WHERE id=? AND dataset_id=?",
        (image_id, dataset_id),
    ) as cur:
        row = await cur.fetchone()
    if not row:
        return None

    abs_path = base_root / row["rel_path"]
    if not abs_path.exists():
        return None

    # Security: ensure path is under base_root
    try:
        abs_path.resolve().relative_to(base_root.resolve())
    except ValueError:
        log.warning("path_traversal_attempt", dataset_id=dataset_id, image_id=image_id)
        return None

    return abs_path
