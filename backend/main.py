"""
CircuitSight - RESTful FastAPI Backend
Automated Optical Inspection (AOI) Deep Learning Service for PCB Defect Detection and Localization.

Detector-First Architecture:
- Primary: YOLOv8 trained on full-board images for multi-defect localization.
- Secondary: Fine-tuned EfficientNet-B0 for optional crop classification.
"""

import sys
from pathlib import Path
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

# Ensure backend directory is in python sys.path
backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from api.deps import model_manager, detector_manager
from api.routes_detect import router as detect_router
from api.routes_defects import router as defects_router
from api.routes_health import router as health_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for warm-up and graceful resource cleanup.
    Pre-loads the YOLOv8 detector and EfficientNet-B0 crop classifier.
    Classifier failure is non-fatal: the detector continues to operate.
    """
    print("[CircuitSight] Initializing PCB Defect Classifier (EfficientNet-B0)...")
    try:
        loaded = model_manager.initialize()
        if loaded and model_manager.predictor:
            print(f"[CircuitSight] Crop classifier loaded on device: {model_manager.predictor.device}")
        else:
            print(f"[CircuitSight Warning] Crop classifier unavailable: {model_manager.load_error}")
    except Exception as exc:
        print(f"[CircuitSight Warning] Non-fatal classifier init error: {exc}")

    print("[CircuitSight] Initializing PCB Defect Detector (YOLOv8)...")
    try:
        detector_manager.initialize()
        app.state.detector_manager = detector_manager
        print(f"[CircuitSight] Detector '{detector_manager.model_filename}' loaded successfully on device: {detector_manager.device}")
    except Exception as exc:
        print(f"[CircuitSight Warning] Could not pre-load detector model: {exc}")

    yield

    print("[CircuitSight] Shutting down PCB Defect Service...")


# Initialize FastAPI App with OpenAPI metadata
app = FastAPI(
    title="CircuitSight PCB Defect Detection API (YOLOv8 + EfficientNet-B0)",
    description="""
## CircuitSight Automated Optical Inspection (AOI) Deep Learning Backend

A detector-first RESTful API for real-time localization and classification of Printed Circuit Board (PCB) manufacturing defects.

### Key Capabilities:
* **YOLOv8 Full-Board Detection**: Real-time multi-defect localization (`missing_hole`, `mouse_bite`, `open_circuit`, `short`, `spur`, `spurious_copper`) with bounding boxes and mAP@0.5 > 96%.
* **Two-Stage Pipeline**: YOLO detection on whole PCB photos with optional secondary fine-grained crop classification using EfficientNet-B0.
* **Annotated Visual Verification**: Export detection results with bounding boxes rendered as base64 PNGs.
* **Industrial Defect Taxonomy**: Built-in severity classifications, functional risk analyses, and manufacturing remediation standards.
    """,
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Enable Cross-Origin Resource Sharing (CORS) for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount only Detection, Defects, and Health Routers
app.include_router(detect_router, prefix="/api")
app.include_router(defects_router, prefix="/api")
app.include_router(health_router, prefix="/api")


@app.get("/", include_in_schema=False)
async def root():
    """Redirect root path to interactive Swagger documentation."""
    return RedirectResponse(url="/docs")


@app.get("/health", include_in_schema=False)
async def root_health():
    """Top-level health check alias."""
    return {
        "status": "healthy",
        "service": "CircuitSight PCB Defect Detection API (YOLOv8 + EfficientNet-B0)",
        "detector": {
            "loaded": detector_manager.is_loaded,
            "model_path": str(detector_manager.model_path.name),
            "classes": detector_manager.classes,
            "device": str(detector_manager.device),
        },
        "classifier": {
            "loaded": model_manager.is_loaded,
            "architecture": model_manager.architecture,
            "checkpoint": model_manager.checkpoint_name,
            "device": str(model_manager.predictor.device) if model_manager.predictor else None,
        },
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="CircuitSight FastAPI Server")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host interface (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind (default: 8000)")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload on code change")

    args = parser.parse_args()

    print(f"Starting CircuitSight API on http://{args.host}:{args.port}")
    uvicorn.run("main:app", host=args.host, port=args.port, reload=args.reload)
