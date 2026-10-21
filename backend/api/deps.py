"""
CircuitSight - Dependency & Model Manager
Manages the YOLOv8 detector and EfficientNet-B0 crop classifier singletons.
"""

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import torch
from prediction import PCBPredictor, DEFECT_CATALOG, CLASSES


APP_START_TIME = time.time()


class ModelManager:
    """
    Manages the secondary EfficientNet-B0 crop classifier lifecycle.
    Only loads models/efficientnet_b0_best.pth.
    Failure to load is non-fatal: the detector still operates.
    """

    def __init__(self, checkpoint_name: str = "efficientnet_b0_best.pth"):
        self.checkpoint_name = checkpoint_name
        self.architecture = "efficientnet_b0"
        self.backend_dir = Path(__file__).resolve().parent.parent
        self.model_path = self.backend_dir / "models" / checkpoint_name
        self.predictor: Optional[PCBPredictor] = None
        self.is_loaded: bool = False
        self.load_error: Optional[str] = None

    def initialize(self) -> bool:
        """
        Attempts to load the EfficientNet-B0 classifier checkpoint.
        Non-fatal: catches missing checkpoints or load errors without raising.
        """
        if not self.model_path.exists():
            self.is_loaded = False
            self.load_error = f"Checkpoint '{self.checkpoint_name}' not found at {self.model_path}"
            print(f"[CircuitSight Warning] {self.load_error}")
            return False

        try:
            self.predictor = PCBPredictor(
                model_path=self.model_path,
                architecture=self.architecture,
            )
            self.is_loaded = True
            self.load_error = None
            return True
        except Exception as exc:
            self.is_loaded = False
            self.load_error = str(exc)
            print(f"[CircuitSight Warning] Failed to initialize classifier: {exc}")
            return False

    def get_predictor(self) -> Optional[PCBPredictor]:
        if not self.is_loaded and self.load_error is None:
            self.initialize()
        return self.predictor


class DetectorManager:
    """
    Manages active YOLOv8 PCB Defect Detector lifecycle, warm-up, and inference.
    """

    def __init__(self, model_file: str = "yolov8_pcb_best.pt"):
        self.model_filename = model_file
        self.backend_dir = Path(__file__).resolve().parent.parent
        self.model_path = self.backend_dir / "models" / model_file
        self.metadata_path = self.backend_dir / "models" / model_file.replace(".pt", ".json")
        self.model: Optional[Any] = None
        self.is_loaded: bool = False
        self.device: str = "cuda" if torch.cuda.is_available() else "cpu"
        self.classes: List[str] = list(CLASSES)
        self.metadata: Dict[str, Any] = {}
        self.model_name: str = "yolov8s"
        self._load_metadata()

    def _load_metadata(self) -> None:
        if self.metadata_path.exists():
            try:
                with open(self.metadata_path, "r", encoding="utf-8") as f:
                    self.metadata = json.load(f)
                    if "classes" in self.metadata:
                        self.classes = self.metadata["classes"]
                    if "model" in self.metadata:
                        self.model_name = self.metadata["model"]
            except Exception as exc:
                print(f"[CircuitSight Warning] Could not load YOLO metadata: {exc}")

    def initialize(self) -> None:
        """Loads the YOLO detector checkpoint and performs dummy inference warm-up."""
        if not self.model_path.exists():
            raise FileNotFoundError(f"Detector checkpoint '{self.model_filename}' not found in backend/models/")

        from ultralytics import YOLO
        import numpy as np

        self.model = YOLO(str(self.model_path))
        self.device = "cuda" if torch.cuda.is_available() else "cpu"

        # Warm up detector with dummy image so initial request has 0 cold start penalty
        try:
            dummy = np.zeros((640, 640, 3), dtype=np.uint8)
            with torch.no_grad():
                self.model.predict(dummy, imgsz=640, device=self.device, verbose=False)
        except Exception as exc:
            print(f"[CircuitSight Warning] Detector warmup failed: {exc}")

        self.is_loaded = True

    def get_model(self) -> Any:
        if not self.is_loaded or self.model is None:
            self.initialize()
        return self.model

    def predict(
        self,
        image: Any,
        conf: float = 0.25,
        iou: float = 0.45,
        imgsz: int = 1024,
    ) -> Any:
        """Run YOLO inference with torch.no_grad on cuda if available."""
        model = self.get_model()
        with torch.no_grad():
            return model.predict(
                image,
                conf=conf,
                iou=iou,
                imgsz=imgsz,
                device=self.device,
                verbose=False,
            )


# Global singletons
model_manager = ModelManager()
detector_manager = DetectorManager()


def get_predictor() -> Optional[PCBPredictor]:
    """FastAPI Dependency for accessing active PCBPredictor (if loaded)."""
    return model_manager.get_predictor()


def get_model_manager() -> ModelManager:
    """FastAPI Dependency for accessing ModelManager state."""
    return model_manager


def get_detector() -> DetectorManager:
    """FastAPI Dependency for accessing initialized DetectorManager."""
    if not detector_manager.is_loaded:
        detector_manager.initialize()
    return detector_manager


def get_detector_manager() -> DetectorManager:
    """FastAPI Dependency for accessing DetectorManager state."""
    return detector_manager
