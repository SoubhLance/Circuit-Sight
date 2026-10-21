"""
CircuitSight - PCB Defect Detection Routes
Endpoints for YOLOv8 full-board object detection with optional EfficientNet-B0 crop classification.
"""

import base64
import io
import time
from pathlib import Path
from typing import Dict, List, Optional

import cv2
import numpy as np
from PIL import Image
import torch
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status

from api.deps import get_detector, get_predictor, DetectorManager, PCBPredictor
from prediction import DEFECT_CATALOG, crop_box
from schemas import DefectDetails, DetectionItem, DetectionResponse


router = APIRouter(prefix="/detect", tags=["Detection"])

MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB limit
DISALLOWED_EXTENSIONS = {
    ".txt", ".csv", ".json", ".pdf", ".zip", ".tar", ".gz",
    ".py", ".md", ".html", ".js", ".xml", ".yaml", ".yml", ".doc", ".docx"
}


@router.post(
    "",
    response_model=DetectionResponse,
    summary="Detect PCB Manufacturing Defects via YOLOv8",
    description=(
        "Upload a full PCB image to detect manufacturing defects (missing_hole, mouse_bite, "
        "open_circuit, short, spur, spurious_copper) with bounding boxes and optional secondary classification."
    ),
)
async def detect_defects(
    request: Request,
    file: UploadFile = File(..., description="PCB full board image file (PNG, JPG, BMP)"),
    conf: Optional[float] = Form(None, description="Confidence threshold (0.01 to 0.99, default 0.25)"),
    iou: Optional[float] = Form(None, description="IoU NMS threshold (0.01 to 0.99, default 0.45)"),
    imgsz: Optional[int] = Form(None, description="Inference image resolution (default 1024)"),
    classify_crops: Optional[bool] = Form(None, description="Run secondary EfficientNet-B0 classifier on crops"),
    include_annotated_image: Optional[bool] = Form(None, description="Return base64 encoded PNG with bounding boxes"),
    detector_mgr: DetectorManager = Depends(get_detector),
    predictor: Optional[PCBPredictor] = Depends(get_predictor),
):
    q_params = request.query_params

    # 1. Resolve raw_conf (Form takes precedence, fallback to Query)
    raw_conf = conf
    if raw_conf is None and "conf" in q_params:
        try:
            raw_conf = float(q_params["conf"])
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid confidence threshold '{q_params['conf']}'. Must be a number.",
            )

    # Treat None or <= 0 as "not provided" and use default: 0.25
    if raw_conf is None or raw_conf == 0:
        conf_applied = 0.25
    elif raw_conf < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid confidence threshold '{raw_conf}'. Cannot be negative.",
        )
    elif raw_conf > 0.99:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid confidence threshold '{raw_conf}'. Must be between 0.01 and 0.99.",
        )
    elif 0 < raw_conf < 0.01:
        # Clamp 0 < conf < 0.01 to 0.01
        conf_applied = 0.01
    else:
        conf_applied = float(raw_conf)

    # 2. Resolve raw_iou
    raw_iou = iou
    if raw_iou is None and "iou" in q_params:
        try:
            raw_iou = float(q_params["iou"])
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid IoU threshold '{q_params['iou']}'. Must be a number.",
            )

    # Treat None or <= 0 as "not provided" and use default: 0.45
    if raw_iou is None or raw_iou == 0:
        iou_applied = 0.45
    elif raw_iou < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid IoU threshold '{raw_iou}'. Cannot be negative.",
        )
    elif raw_iou > 0.99:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid IoU threshold '{raw_iou}'. Must be between 0.01 and 0.99.",
        )
    elif 0 < raw_iou < 0.01:
        iou_applied = 0.01
    else:
        iou_applied = float(raw_iou)

    # 3. Resolve raw_imgsz
    raw_imgsz = imgsz
    if raw_imgsz is None and "imgsz" in q_params:
        try:
            raw_imgsz = int(q_params["imgsz"])
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid image size '{q_params['imgsz']}'. Must be an integer.",
            )

    # Treat None or <= 0 as "not provided" and use default: 1024
    if raw_imgsz is None or raw_imgsz == 0:
        imgsz_applied = 1024
    elif raw_imgsz < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid image size '{raw_imgsz}'. Cannot be negative.",
        )
    elif raw_imgsz > 4096:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid image size '{raw_imgsz}'. Must be <= 4096.",
        )
    elif 0 < raw_imgsz < 32:
        imgsz_applied = 32
    else:
        imgsz_applied = int(raw_imgsz)

    # Resolve classify_crops
    if classify_crops is None:
        if "classify_crops" in q_params:
            classify_crops = q_params["classify_crops"].strip().lower() in ("true", "1", "yes")
        else:
            classify_crops = False

    # Resolve include_annotated_image
    if include_annotated_image is None:
        if "include_annotated_image" in q_params:
            include_annotated_image = q_params["include_annotated_image"].strip().lower() in ("true", "1", "yes")
        else:
            include_annotated_image = False

    # Applied settings summary
    settings_used = {
        "conf": conf_applied,
        "iou": iou_applied,
        "imgsz": imgsz_applied,
    }

    # 4. Check crop classifier availability if classify_crops is requested
    if classify_crops and predictor is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Crop classifier is unavailable (EfficientNet-B0 checkpoint not loaded). "
                "Run detection with classify_crops=false or restore models/efficientnet_b0_best.pth."
            ),
        )

    # 5. Content-Type and File Extension validation (Reject non-image files)
    if file.content_type and not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Uploaded file '{file.filename}' is not an image (Content-Type: '{file.content_type}').",
        )

    filename = file.filename or ""
    suffix = Path(filename).suffix.lower()
    if suffix in DISALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File '{filename}' with extension '{suffix}' is not an allowed image format.",
        )

    # 6. Read contents and check file size
    try:
        contents = await file.read()
    except Exception as read_exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read upload: {str(read_exc)}",
        )

    if not contents:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty file received. Please upload a valid PCB board image.",
        )

    if len(contents) > MAX_FILE_SIZE_BYTES:
        size_mb = len(contents) / (1024 * 1024)
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size ({size_mb:.1f} MB) exceeds maximum allowed limit of 50 MB.",
        )

    # 7. Decode Image with PIL
    try:
        pil_image = Image.open(io.BytesIO(contents)).convert("RGB")
    except Exception as img_exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Uploaded file could not be parsed as an image: {str(img_exc)}",
        )

    img_width, img_height = pil_image.size
    if img_width <= 0 or img_height <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid image dimensions: {img_width}x{img_height}.",
        )

    # 8. Run YOLOv8 Detection
    start_time = time.perf_counter()
    try:
        with torch.no_grad():
            results = detector_mgr.predict(
                pil_image,
                conf=conf_applied,
                iou=iou_applied,
                imgsz=imgsz_applied,
            )
    except Exception as infer_exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"YOLO detector inference failed: {str(infer_exc)}",
        )

    inference_time_ms = round((time.perf_counter() - start_time) * 1000.0, 2)

    # 9. Extract detection results
    yolo_result = results[0]
    detections: List[DetectionItem] = []
    defect_summary: Dict[str, int] = {}

    if yolo_result.boxes is not None and len(yolo_result.boxes) > 0:
        for box in yolo_result.boxes:
            cls_idx = int(box.cls[0].item())
            class_name = yolo_result.names.get(
                cls_idx,
                detector_mgr.classes[cls_idx] if cls_idx < len(detector_mgr.classes) else f"class_{cls_idx}",
            )
            box_conf = round(float(box.conf[0].item()), 4)

            # Clamp coordinates to original image bounds
            xyxy = box.xyxy[0].tolist()
            x1 = max(0, min(img_width, int(round(xyxy[0]))))
            y1 = max(0, min(img_height, int(round(xyxy[1]))))
            x2 = max(0, min(img_width, int(round(xyxy[2]))))
            y2 = max(0, min(img_height, int(round(xyxy[3]))))
            bbox = [x1, y1, x2, y2]

            # Defect catalog domain details
            cat_entry = DEFECT_CATALOG.get(
                class_name,
                {
                    "name": class_name.replace("_", " ").title(),
                    "severity": "Medium",
                    "description": "Detected PCB anomaly requiring optical inspection.",
                    "risk": "Requires QA audit.",
                    "remediation": "Inspect PCB manufacturing layer.",
                },
            )
            defect_details = DefectDetails(
                name=cat_entry.get("name", class_name.replace("_", " ").title()),
                severity=cat_entry.get("severity", "Medium"),
                description=cat_entry.get("description", ""),
                risk=cat_entry.get("risk", ""),
                remediation=cat_entry.get("remediation", ""),
            )

            # Secondary classification on cropped ROI if requested and available
            classifier_class = None
            classifier_confidence = None
            if classify_crops and predictor is not None:
                try:
                    c_xmin, c_ymin, c_xmax, c_ymax = crop_box(
                        xmin=x1,
                        ymin=y1,
                        xmax=x2,
                        ymax=y2,
                        width=img_width,
                        height=img_height,
                        scale=2.5,
                        min_crop=64,
                    )
                    crop_patch = pil_image.crop((c_xmin, c_ymin, c_xmax, c_ymax))
                    clf_pred = predictor.predict(crop_patch, return_heatmap=False)
                    classifier_class = clf_pred["predicted_class"]
                    classifier_confidence = clf_pred["confidence"]
                except Exception as clf_exc:
                    print(f"[CircuitSight Warning] Crop classification error: {clf_exc}")
                    classifier_class = None
                    classifier_confidence = None

            detections.append(
                DetectionItem(
                    class_name=class_name,
                    confidence=box_conf,
                    bbox=bbox,
                    defect_details=defect_details,
                    classifier_class=classifier_class,
                    classifier_confidence=classifier_confidence,
                )
            )
            defect_summary[class_name] = defect_summary.get(class_name, 0) + 1

    total_defects = len(detections)

    # 10. Warnings construction
    warnings: List[str] = []
    longest_side = max(img_width, img_height)
    if longest_side < 800:
        warnings.append(
            "Low-resolution input. Detector was trained on ~3000px board photos, so results may be unreliable."
        )

    if total_defects == 0:
        warnings.append(
            "No defects detected above the confidence threshold. This is not a guarantee the board is defect-free."
        )

    warning_str = " ".join(warnings) if warnings else None

    # 11. Annotated boxed image generation (base64 PNG)
    annotated_image_base64: Optional[str] = None
    if include_annotated_image:
        try:
            pl = yolo_result.plot(line_width=2, font_size=12)  # Returns BGR numpy uint8 image
            success, encoded_buf = cv2.imencode(".png", pl)
            if success:
                annotated_image_base64 = base64.b64encode(encoded_buf.tobytes()).decode("utf-8")
        except Exception as plot_exc:
            print(f"[CircuitSight Warning] Could not render annotated image: {plot_exc}")
            annotated_image_base64 = None

    return DetectionResponse(
        success=True,
        image_width=img_width,
        image_height=img_height,
        total_defects=total_defects,
        defect_summary=defect_summary,
        detections=detections,
        inference_time_ms=inference_time_ms,
        model_name=detector_mgr.metadata.get("model", detector_mgr.model_name),
        device=str(detector_mgr.device),
        warning=warning_str,
        annotated_image_base64=annotated_image_base64,
        settings_used=settings_used,
    )
