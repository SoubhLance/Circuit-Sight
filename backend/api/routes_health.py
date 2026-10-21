"""
CircuitSight - System Health & Diagnostics Routes
Provides operational status, hardware utilization, and environment diagnostics for YOLOv8 & EfficientNet-B0.
"""

import time
import torch
from fastapi import APIRouter, Depends

from api.deps import (
    get_model_manager,
    get_detector_manager,
    ModelManager,
    DetectorManager,
    APP_START_TIME,
    CLASSES,
)
from api.batch_manager import get_batch_manager, BatchManager
from schemas import HealthResponse, DetectorHealthInfo, ClassifierHealthInfo, BatchHealthInfo

router = APIRouter(prefix="", tags=["Health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="System Health & Hardware Status",
    description="Check API liveness, CUDA GPU acceleration availability, detector status, classifier status, and batch processing status.",
)
async def health_check(
    model_mgr: ModelManager = Depends(get_model_manager),
    detector_mgr: DetectorManager = Depends(get_detector_manager),
    batch_mgr: BatchManager = Depends(get_batch_manager),
):
    cuda_avail = torch.cuda.is_available()
    gpu_name = torch.cuda.get_device_name(0) if cuda_avail else None

    detector_info = DetectorHealthInfo(
        loaded=detector_mgr.is_loaded,
        model_name=detector_mgr.model_name,
        model_path=str(detector_mgr.model_path.name),
        classes=detector_mgr.classes,
        device=str(detector_mgr.device),
        imgsz=detector_mgr.metadata.get("img_size", 1024),
        map50=detector_mgr.metadata.get("map50"),
        map50_95=detector_mgr.metadata.get("map50_95"),
    )

    clf_device = str(model_mgr.predictor.device) if (model_mgr.predictor and model_mgr.is_loaded) else None
    classifier_info = ClassifierHealthInfo(
        loaded=model_mgr.is_loaded,
        model_name=model_mgr.architecture,
        model_path=model_mgr.checkpoint_name,
        device=clf_device,
    )

    batch_info = BatchHealthInfo(
        active_batches=batch_mgr.active_batch_count,
        max_concurrent_batches=2,
        storage_dir=str(batch_mgr.batches_root),
    )

    primary_model = detector_mgr.model_name if detector_mgr.is_loaded else "unloaded"
    checkpoint = str(detector_mgr.model_path.name) if detector_mgr.is_loaded else "none"

    return HealthResponse(
        status="healthy",
        device=str(detector_mgr.device),
        cuda_available=cuda_avail,
        gpu_name=gpu_name,
        active_model=primary_model,
        checkpoint=checkpoint,
        supported_classes=detector_mgr.classes,
        uptime_seconds=round(time.time() - APP_START_TIME, 2),
        detector=detector_info,
        detector_loaded=detector_mgr.is_loaded,
        detector_model_path=str(detector_mgr.model_path.name),
        detector_classes=detector_mgr.classes,
        classifier=classifier_info,
        classifier_loaded=model_mgr.is_loaded,
        batch=batch_info,
    )


@router.get(
    "/info",
    summary="Application & Pipeline Overview",
    description="Metadata regarding the CircuitSight PCB quality inspection detector-first pipeline.",
)
async def system_info(
    detector_mgr: DetectorManager = Depends(get_detector_manager),
    model_mgr: ModelManager = Depends(get_model_manager),
):
    return {
        "application": "CircuitSight",
        "title": "CircuitSight PCB Defect Detection API (YOLOv8 + EfficientNet-B0)",
        "description": "Deep Learning Automated Optical Inspection (AOI) for PCB Defect Detection and Localization",
        "version": "2.0.0",
        "dataset": "akhatova/pcb-defects (PCB_DATASET)",
        "defect_classes": detector_mgr.classes,
        "detector": {
            "model": detector_mgr.model_name,
            "checkpoint": str(detector_mgr.model_path.name),
            "loaded": detector_mgr.is_loaded,
            "metrics": detector_mgr.metadata,
        },
        "crop_classifier": {
            "model": model_mgr.architecture,
            "checkpoint": model_mgr.checkpoint_name,
            "loaded": model_mgr.is_loaded,
        },
        "features": [
            "Full board YOLOv8 multi-defect localization",
            "Optional two-stage EfficientNet-B0 crop verification (classify_crops)",
            "Annotated bounding box image generation (base64 PNG)",
            "Industrial severity ratings, risks, and remediation guidelines",
        ],
    }
