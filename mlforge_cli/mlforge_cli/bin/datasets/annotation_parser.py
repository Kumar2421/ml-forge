"""
datasets/annotation_parser.py — Multi-format annotation parser.

Supports:
  - YOLO (darknet .txt + classes.txt / data.yaml)
  - COCO (instances_*.json / _annotations.coco.json)
  - Pascal VOC (*.xml)

All formats normalise to the unified Annotation schema with
normalised bounding boxes (0–1 range, x_topleft, y_topleft, w, h).
"""
from __future__ import annotations

import csv
import json
import re
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Iterator, Optional

from observability.logger import get_logger

log = get_logger("annotation_parser")


# ── Unified Output ────────────────────────────────────────────────────────────

def _make_ann(
    image_id: str,
    dataset_id: str,
    label: str,
    bbox: tuple[float, float, float, float] | None = None,   # x, y, w, h  (normalised)
    normalised: bool = True,
    area: float | None = None,
    confidence: float | None = None,
    ann_type: str = "detection",
    segmentation: list[list[float]] | None = None,
    keypoints: list[float] | None = None,
    metadata: dict | None = None,
) -> dict:
    return {
        "id":           f"ann-{uuid.uuid4().hex[:12]}",
        "image_id":     image_id,
        "dataset_id":   dataset_id,
        "label":        label,
        "bbox_x":       bbox[0] if bbox else None,
        "bbox_y":       bbox[1] if bbox else None,
        "bbox_w":       bbox[2] if bbox else None,
        "bbox_h":       bbox[3] if bbox else None,
        "normalised":   1 if normalised else 0,
        "area":         area,
        "confidence":   confidence,
        "ann_type":     ann_type,
        "segmentation": json.dumps(segmentation) if segmentation else None,
        "keypoints":    json.dumps(keypoints) if keypoints else None,
        "metadata":     json.dumps(metadata) if metadata else None,
    }


# ── YOLO Parser ───────────────────────────────────────────────────────────────

class YOLOParser:
    """
    Reads YOLO darknet annotation files (.txt) + class map.
    Each line: <class_id> <cx> <cy> <w> <h>  (all normalised 0–1)
    """

    @staticmethod
    def load_class_map(dataset_root: Path) -> list[str]:
        """Attempt to load class names from data.yaml or classes.txt."""
        # Try data.yaml first
        for yaml_file in dataset_root.rglob("data.yaml"):
            try:
                import yaml
                with open(yaml_file, 'r', encoding='utf-8', errors='replace') as f:
                    data = yaml.safe_load(f)
                    if data and 'names' in data:
                        names = data['names']
                        if isinstance(names, list):
                            return names
                        elif isinstance(names, dict):
                            # Handle dict format: {0: 'class_a', 1: 'class_b'}
                            return [names[i] for i in sorted(names.keys())]
            except Exception:
                # Fallback to regex if yaml import fails or parsing fails
                try:
                    text = yaml_file.read_text(encoding="utf-8", errors="replace")
                    import re as _re
                    m = _re.search(r"names\s*:\s*\n((?:\s*-\s*.+\n?)+)", text)
                    if m:
                        return [line.strip().lstrip("- ").strip() for line in m.group(1).splitlines() if line.strip()]
                except Exception:
                    pass

        # Try classes.txt
        for cls_file in dataset_root.rglob("classes.txt"):
            try:
                lines = cls_file.read_text(encoding="utf-8", errors="replace").splitlines()
                return [l.strip() for l in lines if l.strip()]
            except Exception:
                pass

        return []

    @staticmethod
    def parse_file(
        txt_path: Path,
        image_id: str,
        dataset_id: str,
        class_map: list[str],
    ) -> list[dict]:
        annotations = []
        try:
            text = txt_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return annotations

        for line in text.splitlines():
            parts = line.strip().split()
            if len(parts) < 5:
                continue
            try:
                cls_id = int(parts[0])
                cx, cy, w, h = float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4])
                # YOLO cx,cy → top-left x,y
                x = cx - w / 2
                y = cy - h / 2
                label = class_map[cls_id] if cls_id < len(class_map) else str(cls_id)
                annotations.append(
                    _make_ann(image_id, dataset_id, label, (x, y, w, h), area=w * h)
                )
            except (ValueError, IndexError):
                continue

        return annotations

    @staticmethod
    def iter_dataset(
        dataset_root: Path,
        dataset_id: str,
        class_map: list[str],
    ) -> Iterator[tuple[str, str, str, list[dict]]]:
        """
        Yield (image_rel_path, image_id, split, annotations) for every image in the dataset.
        Walks train/valid/test directories.
        """
        # Supported subfolder names for splits
        split_map = {
            "train": ["train", "training"],
            "val": ["valid", "val", "validation"],
            "test": ["test", "testing"]
        }

        found_any = False
        for split_name, folder_names in split_map.items():
            for folder_name in folder_names:
                split_dir = dataset_root / folder_name
                images_dir = split_dir / "images"
                
                # Support both split/images and split/ (if images are direct)
                search_dir = images_dir if images_dir.exists() else split_dir
                if not search_dir.exists():
                    continue

                found_any = True
                labels_dir = split_dir / "labels"
                
                for img_path in sorted(search_dir.rglob("*")):
                    if img_path.suffix.lower() not in (".jpg", ".jpeg", ".png", ".bmp", ".webp"):
                        continue
                    
                    image_id = f"img-{uuid.uuid4().hex[:12]}"
                    
                    # Resolve label path
                    # 1. split/labels/img.txt
                    # 2. split/img.txt
                    # 3. img_path.with_suffix(".txt")
                    label_candidates = []
                    if labels_dir.exists():
                        label_candidates.append(labels_dir / img_path.with_suffix(".txt").name)
                    label_candidates.append(img_path.with_suffix(".txt"))

                    anns: list[dict] = []
                    for label_file in label_candidates:
                        if label_file.exists():
                            anns = YOLOParser.parse_file(label_file, image_id, dataset_id, class_map)
                            break

                    rel_path = str(img_path.relative_to(dataset_root))
                    yield rel_path, image_id, split_name, anns

        # Fallback: if no split folders found, scan the root
        if not found_any:
            for img_path in sorted(dataset_root.rglob("*")):
                if img_path.suffix.lower() not in (".jpg", ".jpeg", ".png", ".bmp", ".webp"):
                    continue
                # Skip files inside already processed folders if we had any
                image_id = f"img-{uuid.uuid4().hex[:12]}"
                label_file = img_path.with_suffix(".txt")
                anns = []
                if label_file.exists():
                    anns = YOLOParser.parse_file(label_file, image_id, dataset_id, class_map)
                
                rel_path = str(img_path.relative_to(dataset_root))
                yield rel_path, image_id, "train", anns


# ── COCO Parser ───────────────────────────────────────────────────────────────

class COCOParser:
    """
    Reads COCO JSON annotation files.
    Supports: instances_train.json, instances_val.json, _annotations.coco.json
    """

    @staticmethod
    def find_annotation_files(dataset_root: Path) -> list[Path]:
        patterns = ["instances_*.json", "_annotations.coco.json", "*.json"]
        found = []
        for pat in patterns:
            for f in dataset_root.rglob(pat):
                if "label" not in f.name.lower() and "class" not in f.name.lower():
                    found.append(f)
        return list(dict.fromkeys(found))   # deduplicate

    @staticmethod
    def parse_file(
        json_path: Path,
        dataset_id: str,
    ) -> tuple[list[str], list[tuple[str, str, str, list[dict]]]]:
        """
        Returns: (class_names, [(rel_image_path, image_id, split, annotations)])
        """
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            log.warning("coco_parse_error", file=str(json_path), error=str(e))
            return [], []

        categories = {c["id"]: c["name"] for c in data.get("categories", [])}
        class_names = list(categories.values())

        # Determine split from filename
        fname = json_path.stem.lower()
        if "train" in fname:
            split = "train"
        elif "val" in fname or "valid" in fname:
            split = "val"
        elif "test" in fname:
            split = "test"
        else:
            split = "train"

        # Build image map
        image_map: dict[int, dict] = {
            img["id"]: img for img in data.get("images", [])
        }

        # Group annotations by image
        ann_by_image: dict[int, list] = {}
        for ann in data.get("annotations", []):
            ann_by_image.setdefault(ann["image_id"], []).append(ann)

        results = []
        for coco_img_id, img_meta in image_map.items():
            image_id = f"img-{uuid.uuid4().hex[:12]}"
            rel_path = img_meta.get("file_name", "")
            anns = []
            for coco_ann in ann_by_image.get(coco_img_id, []):
                label = categories.get(coco_ann.get("category_id", -1), "unknown")
                bbox = coco_ann.get("bbox", [])
                if len(bbox) == 4:
                    # COCO: [x_topleft, y_topleft, w, h] in pixel coords
                    img_w = img_meta.get("width", 1) or 1
                    img_h = img_meta.get("height", 1) or 1
                    bx = bbox[0] / img_w
                    by = bbox[1] / img_h
                    bw = bbox[2] / img_w
                    bh = bbox[3] / img_h
                    area_pct = (bbox[2] * bbox[3]) / (img_w * img_h)
                    
                    # Extract segmentation if available
                    segmentation = coco_ann.get("segmentation")
                    # COCO segmentation can be a list of polygons or RLE
                    poly_data = None
                    if isinstance(segmentation, list) and len(segmentation) > 0:
                        # Normalize polygon coordinates
                        poly_data = []
                        for poly in segmentation:
                            normalized_poly = []
                            for i in range(0, len(poly), 2):
                                normalized_poly.append(poly[i] / img_w)
                                normalized_poly.append(poly[i+1] / img_h)
                            poly_data.append(normalized_poly)

                    anns.append(
                        _make_ann(
                            image_id, 
                            dataset_id, 
                            label, 
                            (bx, by, bw, bh), 
                            area=area_pct,
                            segmentation=poly_data,
                            ann_type="segmentation" if poly_data else "detection"
                        )
                    )
            results.append((rel_path, image_id, split, anns))

        return class_names, results


# ── VOC Parser ────────────────────────────────────────────────────────────────

class VOCParser:
    """Reads Pascal VOC XML annotation files."""

    @staticmethod
    def parse_file(
        xml_path: Path,
        image_id: str,
        dataset_id: str,
    ) -> tuple[str, int, int, list[dict]]:
        """Returns (filename, width, height, annotations)."""
        try:
            tree = ET.parse(str(xml_path))
        except ET.ParseError as e:
            log.warning("voc_parse_error", file=str(xml_path), error=str(e))
            return "", 0, 0, []

        root = tree.getroot()
        filename = root.findtext("filename") or ""
        size = root.find("size")
        img_w = int(size.findtext("width") or 1) if size is not None else 1
        img_h = int(size.findtext("height") or 1) if size is not None else 1

        anns = []
        for obj in root.findall("object"):
            label = obj.findtext("name") or "unknown"
            bndbox = obj.find("bndbox")
            if bndbox is None:
                continue
            xmin = float(bndbox.findtext("xmin") or 0)
            ymin = float(bndbox.findtext("ymin") or 0)
            xmax = float(bndbox.findtext("xmax") or 0)
            ymax = float(bndbox.findtext("ymax") or 0)
            # Normalise
            bx = xmin / img_w
            by = ymin / img_h
            bw = (xmax - xmin) / img_w
            bh = (ymax - ymin) / img_h
            anns.append(_make_ann(image_id, dataset_id, label, (bx, by, bw, bh)))

        return filename, img_w, img_h, anns

    @staticmethod
    def iter_dataset(
        dataset_root: Path,
        dataset_id: str,
    ) -> Iterator[tuple[str, str, str, int, int, list[dict]]]:
        """Yield (rel_path, image_id, split, w, h, annotations)."""
        for xml_path in sorted(dataset_root.rglob("*.xml")):
            image_id = f"img-{uuid.uuid4().hex[:12]}"
            filename, w, h, anns = VOCParser.parse_file(xml_path, image_id, dataset_id)
            split = "train"
            for part in xml_path.parts:
                if part in ("train", "training"):
                    split = "train"; break
                if part in ("val", "valid", "validation"):
                    split = "val"; break
                if part in ("test", "testing"):
                    split = "test"; break
            rel_path = filename or str(xml_path.with_suffix(".jpg").relative_to(dataset_root))
            yield rel_path, image_id, split, w, h, anns


# ── Roboflow TXT Parser ───────────────────────────────────────────────────────

class RoboflowTXTParser:
    """
    Reads Roboflow classification TXT formats.
    1. Folder-based: split/class_name/image.jpg
    2. Label-file: split/_annotations.txt (format: filename,class_name)
    """

    @staticmethod
    def iter_dataset(
        dataset_root: Path,
        dataset_id: str,
    ) -> Iterator[tuple[str, str, str, list[dict]]]:
        split_map = {
            "train": ["train", "training"],
            "val": ["valid", "val", "validation"],
            "test": ["test", "testing"]
        }

        found_any = False
        for split_name, folder_names in split_map.items():
            for folder_name in folder_names:
                split_dir = dataset_root / folder_name
                if not split_dir.exists():
                    continue

                found_any = True
                
                # Check for _annotations.txt (Roboflow's flat format)
                ann_file = split_dir / "_annotations.txt"
                if ann_file.exists():
                    try:
                        with open(ann_file, "r", encoding="utf-8") as f:
                            # Format is usually: filename,class_name
                            for line in f:
                                parts = line.strip().split(",")
                                if len(parts) >= 2:
                                    fname, label = parts[0], parts[1]
                                    img_path = split_dir / fname
                                    if img_path.exists():
                                        image_id = f"img-{uuid.uuid4().hex[:12]}"
                                        anns = [_make_ann(image_id, dataset_id, label, ann_type="classification")]
                                        rel_path = str(img_path.relative_to(dataset_root))
                                        yield rel_path, image_id, split_name, anns
                        continue # Processed via file, skip folder logic
                    except Exception:
                        pass

                # Fallback to Folder-based: split/class_name/image.jpg
                for class_dir in split_dir.iterdir():
                    if class_dir.is_dir() and class_dir.name.lower() not in ["images", "labels"]:
                        label = class_dir.name
                        for img_path in class_dir.rglob("*"):
                            if img_path.suffix.lower() in (".jpg", ".jpeg", ".png", ".bmp", ".webp"):
                                image_id = f"img-{uuid.uuid4().hex[:12]}"
                                anns = [_make_ann(image_id, dataset_id, label, ann_type="classification")]
                                rel_path = str(img_path.relative_to(dataset_root))
                                yield rel_path, image_id, split_name, anns

        # Fallback to root scan if no split folders found
        if not found_any:
            for img_path in sorted(dataset_root.rglob("*")):
                if img_path.suffix.lower() not in (".jpg", ".jpeg", ".png", ".bmp", ".webp"):
                    continue
                # Simple heuristic: parent folder is class name
                label = img_path.parent.name if img_path.parent != dataset_root else "unknown"
                image_id = f"img-{uuid.uuid4().hex[:12]}"
                anns = [_make_ann(image_id, dataset_id, label, ann_type="classification")]
                rel_path = str(img_path.relative_to(dataset_root))
                yield rel_path, image_id, "train", anns

class CSVParser:
    """
    Reads CSV files for NLP (classification, NER) or Tabular data.
    """

    @staticmethod
    def detect_delimiter(file_path: Path) -> str:
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                header = f.readline()
                if ';' in header: return ';'
                if '\t' in header: return '\t'
            return ','
        except Exception:
            return ','

    @staticmethod
    def parse_file(
        csv_path: Path,
        dataset_id: str,
        text_column: str = "text",
        label_column: str = "label",
    ) -> list[dict]:
        annotations = []
        delimiter = CSVParser.detect_delimiter(csv_path)
        try:
            with open(csv_path, mode='r', encoding='utf-8', errors='replace') as f:
                reader = csv.DictReader(f, delimiter=delimiter)
                for row in reader:
                    image_id = f"txt-{uuid.uuid4().hex[:12]}"
                    text = row.get(text_column, "")
                    label = row.get(label_column, "unknown")
                    if text:
                        annotations.append(
                            _make_ann(
                                image_id=image_id,
                                dataset_id=dataset_id,
                                label=label,
                                bbox=(0, 0, 0, 0),
                                ann_type="nlp_classification"
                            )
                        )
        except Exception as e:
            log.error("csv_parse_error", file=str(csv_path), error=str(e))
        return annotations


# ── Utilities ────────────────────────────────────────────────────────────────

def _img_dimensions(path: Path) -> tuple[int, int]:
    """Fast dimension detection via struct."""
    try:
        import struct
        with open(path, "rb") as f:
            data = f.read(24)
            if data[:8] == b"\x89PNG\r\n\x1a\n":
                return struct.unpack(">II", data[16:24])
            if data[:2] == b"\xff\xd8":
                f.seek(0)
                full = f.read(2048) # Read more for JPEG header
                i = 2
                while i < len(full) - 9:
                    if full[i] == 0xFF and full[i + 1] in (0xC0, 0xC1, 0xC2):
                        h, w = struct.unpack(">HH", full[i + 5:i + 9])
                        return int(w), int(h)
                    i += 1
    except: pass
    return 0, 0


# ── Format Detector ───────────────────────────────────────────────────────────

def detect_format(dataset_root: Path) -> str:
    """Heuristically detect the annotation format in a dataset directory."""
    # COCO: look for JSON with 'images' and 'annotations' keys
    for jf in dataset_root.rglob("*.json"):
        try:
            snippet = jf.read_text(encoding="utf-8", errors="replace")[:2048]
            if '"images"' in snippet and '"annotations"' in snippet:
                return "coco"
        except OSError:
            pass

    # VOC: look for XML files with <annotation> root
    for xf in dataset_root.rglob("*.xml"):
        try:
            snippet = xf.read_text(encoding="utf-8", errors="replace")[:512]
            if "<annotation>" in snippet:
                return "voc"
        except OSError:
            pass

    # YOLO: check for .txt label files and data.yaml
    if list(dataset_root.rglob("data.yaml")):
        return "yolo"
    
    txt_files = list(dataset_root.rglob("*.txt"))
    # Filter out common non-label files
    label_txts = [f for f in txt_files if f.name not in ("classes.txt", "obj.names", "README.txt", "LICENSE.txt", "README.roboflow.txt")]
    if label_txts:
        # Check if first line looks like YOLO (<int> <float> <float> <float> <float>)
        try:
            first_txt = label_txts[0]
            content = first_txt.read_text(encoding="utf-8").strip().split('\n')[0]
            if re.match(r"^\d+\s+[\d\.]+\s+[\d\.]+\s+[\d\.]+\s+[\d\.]+", content):
                return "yolo"
        except Exception:
            pass

    # Roboflow Classification TXT: check for split folders containing only subfolders (class names)
    # or check for _annotations.txt
    if list(dataset_root.rglob("_annotations.txt")):
        return "txt"

    # Check for folder-based classification (split/class_name/img.jpg)
    # If we see folders that aren't 'images' or 'labels' inside train/val/test
    for split in ["train", "valid", "test"]:
        split_dir = dataset_root / split
        if split_dir.exists() and split_dir.is_dir():
            subdirs = [d for d in split_dir.iterdir() if d.is_dir()]
            if subdirs and not any(d.name.lower() in ["images", "labels"] for d in subdirs):
                return "txt"

    # CSV/NLP: check for csv files
    if list(dataset_root.rglob("*.csv")):
        return "csv"

    return "custom"
