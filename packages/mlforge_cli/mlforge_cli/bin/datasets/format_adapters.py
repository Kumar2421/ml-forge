from pathlib import Path
import json
import re
from typing import Any, List, Tuple, Iterator, Dict
from .base_adapter import DatasetAdapter
from models.dataset import UniversalDatasetItem, DatasetContentType, UniversalAnnotation, UniversalAnnotationType, DatasetTask
from .annotation_parser import YOLOParser, COCOParser, VOCParser, RoboflowTXTParser, _img_dimensions

class YOLOAdapter(DatasetAdapter):
    def detect(self, dataset_path: Path) -> bool:
        if list(dataset_path.rglob("data.yaml")):
            return True
        txt_files = list(dataset_path.rglob("*.txt"))
        label_txts = [f for f in txt_files if f.name not in ("classes.txt", "obj.names", "README.txt", "LICENSE.txt", "README.roboflow.txt")]
        if label_txts:
            try:
                content = label_txts[0].read_text(encoding="utf-8").strip().split('\n')[0]
                if re.match(r"^\d+\s+[\d\.]+\s+[\d\.]+\s+[\d\.]+\s+[\d\.]+", content):
                    return True
            except: pass
        return False

    def get_task(self, dataset_path: Path) -> DatasetTask:
        return DatasetTask.detection

    def get_class_names(self, dataset_path: Path) -> List[str]:
        return YOLOParser.load_class_map(dataset_path)

    def iter_items(self, dataset_id: str, dataset_path: Path) -> Iterator[Tuple[Dict[str, Any], List[Dict[str, Any]]]]:
        class_map = self.get_class_names(dataset_path)
        for rel_path, image_id, split, anns in YOLOParser.iter_dataset(dataset_path, dataset_id, class_map):
            abs_path = dataset_path / rel_path
            w, h = _img_dimensions(abs_path)
            img_rec = {
                "id": image_id, "filename": Path(rel_path).name,
                "rel_path": str(rel_path), "width": w, "height": h,
                "split": split, "ann_count": len(anns),
            }
            yield img_rec, anns

class COCOAdapter(DatasetAdapter):
    def detect(self, dataset_path: Path) -> bool:
        for jf in dataset_path.rglob("*.json"):
            try:
                snippet = jf.read_text(encoding="utf-8", errors="replace")[:2048]
                if '"images"' in snippet and '"annotations"' in snippet:
                    return True
            except: pass
        return False

    def get_task(self, dataset_path: Path) -> DatasetTask:
        return DatasetTask.segmentation # Roboflow COCO often implies segmentation

    def get_class_names(self, dataset_path: Path) -> List[str]:
        ann_files = COCOParser.find_annotation_files(dataset_path)
        all_classes = []
        for ann_file in ann_files:
            classes, _ = COCOParser.parse_file(ann_file, "dummy")
            all_classes = list(dict.fromkeys(all_classes + classes))
        return all_classes

    def iter_items(self, dataset_id: str, dataset_path: Path) -> Iterator[Tuple[Dict[str, Any], List[Dict[str, Any]]]]:
        ann_files = COCOParser.find_annotation_files(dataset_path)
        for ann_file in ann_files:
            _, coco_results = COCOParser.parse_file(ann_file, dataset_id)
            for rel_path, image_id, split, anns in coco_results:
                abs_path = dataset_path / rel_path
                w, h = _img_dimensions(abs_path)
                img_rec = {
                    "id": image_id, "filename": Path(rel_path).name,
                    "rel_path": str(rel_path), "width": w, "height": h,
                    "split": split, "ann_count": len(anns),
                }
                yield img_rec, anns

class VOCAdapter(DatasetAdapter):
    def detect(self, dataset_path: Path) -> bool:
        for xf in dataset_path.rglob("*.xml"):
            try:
                snippet = xf.read_text(encoding="utf-8", errors="replace")[:512]
                if "<annotation>" in snippet:
                    return True
            except: pass
        return False

    def get_task(self, dataset_path: Path) -> DatasetTask:
        return DatasetTask.detection

    def get_class_names(self, dataset_path: Path) -> List[str]:
        classes = set()
        for _, _, _, _, _, anns in VOCParser.iter_dataset(dataset_path, "dummy"):
            for ann in anns:
                classes.add(ann["label"])
        return sorted(list(classes))

    def iter_items(self, dataset_id: str, dataset_path: Path) -> Iterator[Tuple[Dict[str, Any], List[Dict[str, Any]]]]:
        for rel_path, image_id, split, w, h, anns in VOCParser.iter_dataset(dataset_path, dataset_id):
            img_rec = {
                "id": image_id, "filename": Path(rel_path).name,
                "rel_path": str(rel_path), "width": w, "height": h,
                "split": split, "ann_count": len(anns),
            }
            yield img_rec, anns

class CreateMLAdapter(DatasetAdapter):
    def detect(self, dataset_path: Path) -> bool:
        for jf in dataset_path.rglob("*.json"):
            try:
                snippet = jf.read_text(encoding="utf-8", errors="replace")[:1024]
                if '"image"' in snippet and '"annotations"' in snippet and "[" in snippet:
                    return True
            except: pass
        return False

    def get_task(self, dataset_path: Path) -> DatasetTask:
        return DatasetTask.detection

    def get_class_names(self, dataset_path: Path) -> List[str]:
        classes = set()
        for jf in dataset_path.rglob("*.json"):
            try:
                data = json.loads(jf.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    for item in data:
                        for ann in item.get("annotations", []):
                            if "label" in ann: classes.add(ann["label"])
            except: pass
        return sorted(list(classes))

    def iter_items(self, dataset_id: str, dataset_path: Path) -> Iterator[Tuple[Dict[str, Any], List[Dict[str, Any]]]]:
        from .annotation_parser import _make_ann
        for jf in dataset_path.rglob("*.json"):
            try:
                data = json.loads(jf.read_text(encoding="utf-8"))
                if not isinstance(data, list): continue
                
                # Determine split from path
                split = "train"
                if "val" in jf.parts or "valid" in jf.parts: split = "val"
                elif "test" in jf.parts: split = "test"

                for item in data:
                    rel_img_path = item.get("image")
                    if not rel_img_path: continue
                    
                    # Try to find the image relative to JSON or root
                    img_path = jf.parent / rel_img_path
                    if not img_path.exists():
                        img_path = dataset_path / rel_img_path
                    
                    if img_path.exists():
                        image_id = f"img-{uuid.uuid4().hex[:12]}"
                        w, h = _img_dimensions(img_path)
                        
                        anns = []
                        for ca in item.get("annotations", []):
                            label = ca.get("label", "unknown")
                            coord = ca.get("coordinates", {})
                            # CreateML coords are usually center-based pixels: {x, y, width, height}
                            if "x" in coord and "y" in coord and w > 0 and h > 0:
                                cx, cy, bw, bh = coord["x"], coord["y"], coord["width"], coord["height"]
                                # Convert to top-left normalized
                                nx = (cx - bw/2) / w
                                ny = (cy - bh/2) / h
                                nw = bw / w
                                nh = bh / h
                                anns.append(_make_ann(image_id, dataset_id, label, (nx, ny, nw, nh)))
                        
                        img_rec = {
                            "id": image_id, "filename": img_path.name,
                            "rel_path": str(img_path.relative_to(dataset_path)),
                            "width": w, "height": h, "split": split, "ann_count": len(anns)
                        }
                        yield img_rec, anns
            except: pass

class NLPAdapter(DatasetAdapter):
    def detect(self, dataset_path: Path) -> bool:
        return any(dataset_path.rglob("*.csv")) or any(dataset_path.rglob("*.tsv"))

    def get_task(self, dataset_path: Path) -> DatasetTask:
        return DatasetTask.nlp

    def get_class_names(self, dataset_path: Path) -> List[str]:
        # Implementation for NLP class names
        return []

    def iter_items(self, dataset_id: str, dataset_path: Path) -> Iterator[Tuple[Dict[str, Any], List[Dict[str, Any]]]]:
        # Implementation for NLP items
        yield {}, []

class TabularAdapter(DatasetAdapter):
    def detect(self, dataset_path: Path) -> bool:
        return False # Placeholder

    def get_task(self, dataset_path: Path) -> DatasetTask:
        return DatasetTask.classification

    def get_class_names(self, dataset_path: Path) -> List[str]:
        return []

    def iter_items(self, dataset_id: str, dataset_path: Path) -> Iterator[Tuple[Dict[str, Any], List[Dict[str, Any]]]]:
        yield {}, []

class RoboflowClassificationAdapter(DatasetAdapter):
    def detect(self, dataset_path: Path) -> bool:
        # Check for _annotations.txt or folder-based classification
        if list(dataset_path.rglob("_annotations.txt")): return True
        for split in ["train", "valid", "test"]:
            split_dir = dataset_path / split
            if split_dir.exists() and split_dir.is_dir():
                subdirs = [d for d in split_dir.iterdir() if d.is_dir()]
                if subdirs and not any(d.name.lower() in ["images", "labels"] for d in subdirs):
                    return True
        return False

    def get_task(self, dataset_path: Path) -> DatasetTask:
        return DatasetTask.classification

    def get_class_names(self, dataset_path: Path) -> List[str]:
        classes = set()
        for _, _, _, anns in RoboflowTXTParser.iter_dataset(dataset_path, "dummy"):
            for ann in anns: classes.add(ann["label"])
        return sorted(list(classes))

    def iter_items(self, dataset_id: str, dataset_path: Path) -> Iterator[Tuple[Dict[str, Any], List[Dict[str, Any]]]]:
        for rel_path, image_id, split, anns in RoboflowTXTParser.iter_dataset(dataset_path, dataset_id):
            abs_path = dataset_path / rel_path
            w, h = _img_dimensions(abs_path)
            img_rec = {
                "id": image_id, "filename": Path(rel_path).name,
                "rel_path": str(rel_path), "width": w, "height": h,
                "split": split, "ann_count": len(anns),
            }
            yield img_rec, anns
