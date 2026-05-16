from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Tuple, Iterator, Dict, Any, Optional
from models.dataset import UniversalDatasetItem, DatasetTask

class DatasetAdapter(ABC):
    """
    Base interface for all dataset format adapters.
    Following the senior architect pattern: decoupling format logic from import orchestration.
    """
    
    @abstractmethod
    def detect(self, dataset_path: Path) -> bool:
        """Return True if this adapter can handle the dataset at the given path."""
        pass

    @abstractmethod
    def get_task(self, dataset_path: Path) -> DatasetTask:
        """Identify the primary task type (detection, classification, etc.) for this dataset."""
        pass

    @abstractmethod
    def iter_items(self, dataset_id: str, dataset_path: Path) -> Iterator[Tuple[Dict[str, Any], List[Dict[str, Any]]]]:
        """
        Yield (image_record, annotations) for each item in the dataset.
        Memory-efficient streaming for large Roboflow datasets.
        """
        pass

    @abstractmethod
    def get_class_names(self, dataset_path: Path) -> List[str]:
        """Extract or derive the list of class names from the dataset."""
        pass

    def get_metadata(self, dataset_path: Path) -> Dict[str, Any]:
        """Optional: Extract additional format-specific metadata."""
        return {}
