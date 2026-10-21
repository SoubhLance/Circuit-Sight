"""
CircuitSight - Batch Detection Endpoints
Provides endpoints for asynchronous multi-PCB defect batch detection,
status polling, granular result retrieval, individual image/thumbnail streaming,
zip report downloads, and manual cleanup.
"""

import io
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from PIL import Image

from api.batch_manager import (
    BATCH_EXPIRY_SECONDS,
    MAX_CONCURRENT_BATCHES,
    batch_manager,
    get_batch_manager,
    BatchManager,
)
from api.deps import (
    get_detector,
    get_predictor,
    DetectorManager,
    PCBPredictor,
)
from schemas import (
    BatchDeleteResponse,
    BatchInitResponse,
    BatchResultsResponse,
    BatchStatusResponse,
)


router = APIRouter(prefix="/batch", tags=["Batch"])

MAX_FILES_PER_BATCH = 50
MAX_SINGLE_FILE_BYTES = 25 * 1024 * 1024  # 25 MB
MAX_TOTAL_BATCH_BYTES = 400 * 1024 * 1024  # 400 MB
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp"}
ALLOWED_PIL_FORMATS = {"JPEG", "PNG", "BMP"}


@router.post(
    "",
    response_model=BatchInitResponse,
    status_code=status.HTTP_200_OK,
    summary="Submit Batch PCB Defect Detection Job",
    description=(
        "Upload up to 50 PCB images for background YOLOv8 batch detection. "
        "Validates file sizes, extensions, and image headers upfront. "
        "Returns immediately with batch_id and status 'processing'. "
        "Note: Swagger UI cannot multi-select; use the web app or scripts/batch_folder.py for folders."
    ),
)
async def submit_batch(
    request: Request,
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(..., description="PCB board images (max 50)"),
    conf: Optional[float] = Form(None, description="Confidence threshold (0.01 to 0.99, default 0.25)"),
    iou: Optional[float] = Form(None, description="IoU NMS threshold (0.01 to 0.99, default 0.45)"),
    imgsz: Optional[int] = Form(None, description="Inference image resolution (default 1024)"),
    classify_crops: Optional[bool] = Form(None, description="Run secondary EfficientNet-B0 crop classifier"),
    batch_mgr: BatchManager = Depends(get_batch_manager),
    detector_mgr: DetectorManager = Depends(get_detector),
    predictor: Optional[PCBPredictor] = Depends(get_predictor),
):
    q_params = request.query_params

    # 1. Concurrency limit check (Max 2 active batches)
    if not batch_mgr.can_accept_batch():
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many concurrent batches in progress. Maximum allowed is {MAX_CONCURRENT_BATCHES}.",
        )

    # 2. File count validation
    if not files or len(files) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No files uploaded. At least 1 image is required for batch processing.",
        )

    if len(files) > MAX_FILES_PER_BATCH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Batch exceeds maximum allowed limit of {MAX_FILES_PER_BATCH} files "
                f"(received {len(files)} files)."
            ),
        )

    # 3. Resolve and validate conf parameter
    raw_conf = conf
    if raw_conf is None and "conf" in q_params:
        try:
            raw_conf = float(q_params["conf"])
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid confidence threshold '{q_params['conf']}'. Must be a number.",
            )

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
        conf_applied = 0.01
    else:
        conf_applied = float(raw_conf)

    # 4. Resolve and validate iou parameter
    raw_iou = iou
    if raw_iou is None and "iou" in q_params:
        try:
            raw_iou = float(q_params["iou"])
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid IoU threshold '{q_params['iou']}'. Must be a number.",
            )

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

    # 5. Resolve and validate imgsz parameter
    raw_imgsz = imgsz
    if raw_imgsz is None and "imgsz" in q_params:
        try:
            raw_imgsz = int(q_params["imgsz"])
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid image size '{q_params['imgsz']}'. Must be an integer.",
            )

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

    # 6. Resolve classify_crops
    if classify_crops is None:
        if "classify_crops" in q_params:
            classify_crops = q_params["classify_crops"].strip().lower() in ("true", "1", "yes")
        else:
            classify_crops = False

    if classify_crops and predictor is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Crop classifier is unavailable (EfficientNet-B0 checkpoint not loaded). "
                "Run batch detection with classify_crops=false or restore models/efficientnet_b0_best.pth."
            ),
        )

    settings_used = {
        "conf": conf_applied,
        "iou": iou_applied,
        "imgsz": imgsz_applied,
        "classify_crops": classify_crops,
    }

    # 7. Validate all files (extension, size, and PIL image format verification)
    total_batch_bytes = 0
    rejected_files: List[str] = []
    has_size_error = False
    valid_file_data: List[Tuple[str, bytes]] = []

    for idx, f in enumerate(files):
        orig_filename = f.filename or f"image_{idx}"
        ext = Path(orig_filename).suffix.lower()

        # Check extension
        if ext not in ALLOWED_EXTENSIONS:
            rejected_files.append(
                f"File '{orig_filename}': Unsupported extension '{ext}'. Only jpg, jpeg, png, bmp are allowed."
            )
            continue

        # Read content
        try:
            content = await f.read()
        except Exception as read_exc:
            rejected_files.append(f"File '{orig_filename}': Could not read upload ({read_exc}).")
            continue

        if not content:
            rejected_files.append(f"File '{orig_filename}': File is empty.")
            continue

        file_size = len(content)
        total_batch_bytes += file_size

        # Check single file size limit
        if file_size > MAX_SINGLE_FILE_BYTES:
            has_size_error = True
            mb = file_size / (1024 * 1024)
            rejected_files.append(
                f"File '{orig_filename}': Size ({mb:.1f} MB) exceeds maximum allowed file limit of 25 MB."
            )
            continue

        # Check total batch size limit
        if total_batch_bytes > MAX_TOTAL_BATCH_BYTES:
            has_size_error = True
            tot_mb = total_batch_bytes / (1024 * 1024)
            rejected_files.append(
                f"Total batch size ({tot_mb:.1f} MB) exceeds maximum allowed limit of 400 MB."
            )
            break

        # PIL image format verification (not just extension)
        try:
            with Image.open(io.BytesIO(content)) as pil_test:
                pil_fmt = pil_test.format
                if pil_fmt not in ALLOWED_PIL_FORMATS:
                    rejected_files.append(
                        f"File '{orig_filename}': Header format '{pil_fmt}' is not a valid JPEG, PNG, or BMP image."
                    )
                    continue

                w, h = pil_test.size
                if w <= 0 or h <= 0:
                    rejected_files.append(f"File '{orig_filename}': Invalid image dimensions {w}x{h}.")
                    continue
        except Exception as pil_exc:
            rejected_files.append(
                f"File '{orig_filename}': Invalid or unparseable image content ({pil_exc})."
            )
            continue

        valid_file_data.append((orig_filename, content))

    # If any file was rejected, abort with 413 or 400
    if rejected_files:
        status_code = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE if has_size_error else status.HTTP_400_BAD_REQUEST
        error_detail = "Batch validation failed. " + "; ".join(rejected_files)
        raise HTTPException(status_code=status_code, detail=error_detail)

    # 8. Create batch, sanitize filenames, and stage files on disk
    import uuid
    batch_id = str(uuid.uuid4())

    raw_names = [item[0] for item in valid_file_data]
    sanitized_names = batch_mgr.sanitize_filenames(raw_names)

    batch_dir = batch_mgr.init_batch(
        batch_id=batch_id,
        total_files=len(valid_file_data),
        settings_used=settings_used,
    )
    staging_dir = batch_dir / "_staging"

    staging_items: List[Tuple[int, str, str, Path]] = []
    for idx, (orig_name, content) in enumerate(valid_file_data):
        san_name = sanitized_names[idx]
        stg_path = staging_dir / f"{idx}_{san_name}"
        with open(stg_path, "wb") as stg_file:
            stg_file.write(content)
        staging_items.append((idx, orig_name, san_name, stg_path))

    # 9. Dispatch background worker in threadpool (non-blocking)
    background_tasks.add_task(
        run_in_threadpool,
        batch_mgr.run_batch_sync,
        batch_id,
        staging_items,
        settings_used,
        detector_mgr,
        predictor,
    )

    return BatchInitResponse(
        batch_id=batch_id,
        total=len(staging_items),
        status="processing",
    )


@router.get(
    "/{batch_id}/status",
    response_model=BatchStatusResponse,
    summary="Get Batch Processing Status",
    description="Check processing progress, total images, and any individual image errors.",
)
async def get_batch_status(
    batch_id: str,
    batch_mgr: BatchManager = Depends(get_batch_manager),
):
    status_info = batch_mgr.get_status(batch_id)
    if not status_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Batch '{batch_id}' not found.",
        )
    return BatchStatusResponse(
        status=status_info["status"],
        processed=status_info["processed"],
        total=status_info["total"],
        errors=status_info.get("errors", []),
    )


@router.get(
    "/{batch_id}/results",
    response_model=BatchResultsResponse,
    summary="Get Detailed Batch Inspection Results",
    description="Retrieve per-image detections and aggregate batch defect statistics.",
)
async def get_batch_results(
    batch_id: str,
    batch_mgr: BatchManager = Depends(get_batch_manager),
):
    results_info = batch_mgr.get_results(batch_id)
    if not results_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Batch '{batch_id}' not found.",
        )
    return BatchResultsResponse(**results_info)


@router.get(
    "/{batch_id}/image/{index}",
    summary="Retrieve Full Annotated Image",
    description="Fetch the full-size quality 90 annotated JPEG for a specific image index in the batch.",
)
async def get_batch_image(
    batch_id: str,
    index: int,
    batch_mgr: BatchManager = Depends(get_batch_manager),
):
    img_path = batch_mgr.get_annotated_image_path(batch_id, index)
    if not img_path or not img_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Annotated image at index {index} for batch '{batch_id}' not found.",
        )
    return FileResponse(img_path, media_type="image/jpeg", filename=img_path.name)


@router.get(
    "/{batch_id}/thumb/{index}",
    summary="Retrieve Thumbnail Image",
    description="Fetch the 480px-wide JPEG thumbnail for a specific image index in the batch.",
)
async def get_batch_thumb(
    batch_id: str,
    index: int,
    batch_mgr: BatchManager = Depends(get_batch_manager),
):
    thumb_path = batch_mgr.get_thumb_path(batch_id, index)
    if not thumb_path or not thumb_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Thumbnail at index {index} for batch '{batch_id}' not found.",
        )
    return FileResponse(thumb_path, media_type="image/jpeg", filename=f"thumb_{index}.jpg")


@router.get(
    "/zip",
    summary="Download Combined Batch Report ZIP Archive",
    description=(
        "Streams a combined ZIP containing annotated images, report.csv, report.json, and README.txt "
        "for one or more batches specified in query param `ids` (e.g., ?ids=id1,id2,id3)."
    ),
)
async def get_combined_batch_zip(
    ids: str = Query(..., description="Comma-separated batch IDs, e.g. 'id1,id2'"),
    batch_mgr: BatchManager = Depends(get_batch_manager),
):
    id_list = [i.strip() for i in ids.split(",") if i.strip()]
    if not id_list:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Query parameter 'ids' cannot be empty.",
        )

    try:
        zip_path = batch_mgr.get_combined_zip_path(id_list)
    except FileNotFoundError as fnf:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(fnf))
    except ValueError as val_err:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(val_err))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate combined zip: {exc}",
        )

    return FileResponse(
        zip_path,
        media_type="application/zip",
        filename="circuit_sight_combined_report.zip",
    )


@router.get(
    "/{batch_id}/zip",
    summary="Download Batch Report ZIP Archive",
    description=(
        "Streams a pre-generated ZIP containing: annotated/<filename>.jpg for every image, "
        "report.csv, report.json, and README.txt stating the confidence threshold used."
    ),
)
async def get_batch_zip(
    batch_id: str,
    batch_mgr: BatchManager = Depends(get_batch_manager),
):
    status_info = batch_mgr.get_status(batch_id)
    if not status_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Batch '{batch_id}' not found.",
        )

    if status_info["status"] == "processing":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Batch is still processing. Please wait for completion before downloading the zip report.",
        )

    zip_path = batch_mgr.get_zip_path(batch_id)
    if not zip_path or not zip_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report archive for batch '{batch_id}' was not generated or has been removed.",
        )

    return FileResponse(
        zip_path,
        media_type="application/zip",
        filename=f"circuit_sight_batch_{batch_id}.zip",
    )


@router.delete(
    "/{batch_id}",
    response_model=BatchDeleteResponse,
    summary="Delete Batch",
    description="Manually removes the batch directory and its contents from the server filesystem.",
)
async def delete_batch(
    batch_id: str,
    batch_mgr: BatchManager = Depends(get_batch_manager),
):
    deleted = batch_mgr.delete_batch(batch_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Batch '{batch_id}' not found.",
        )
    return BatchDeleteResponse(batch_id=batch_id, deleted=True)
