"""
CircuitSight - Pydantic Data Schemas
Defines request and response schemas for the detector-first FastAPI backend.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class DefectDetails(BaseModel):
    name: str = Field(..., description="Human-readable defect title")
    severity: str = Field(..., description="Industrial risk severity (Low, Medium, High, Critical)")
    description: str = Field(..., description="Technical explanation of the defect")
    risk: str = Field(..., description="Functional risk to the circuit board")
    remediation: str = Field(..., description="Recommended engineering and rework action")


class DefectCatalogItem(DefectDetails):
    class_id: str = Field(..., description="Unique machine-readable defect label")


class DetectionItem(BaseModel):
    class_name: str = Field(..., description="Detected defect class label")
    confidence: float = Field(..., description="Detection confidence score (0.0 to 1.0)")
    bbox: List[int] = Field(..., description="Bounding box [x1, y1, x2, y2] in original pixel coordinates")
    defect_details: DefectDetails = Field(..., description="Domain information about the defect class")
    classifier_class: Optional[str] = Field(None, description="Second-opinion classification from EfficientNet-B0")
    classifier_confidence: Optional[float] = Field(None, description="Confidence of EfficientNet-B0 classification")


class DetectionResponse(BaseModel):
    success: bool = Field(True, description="Whether detection succeeded")
    image_width: int = Field(..., description="Original image width in pixels")
    image_height: int = Field(..., description="Original image height in pixels")
    total_defects: int = Field(..., description="Total number of detected defects")
    defect_summary: Dict[str, int] = Field(..., description="Defect counts grouped by class")
    detections: List[DetectionItem] = Field(..., description="List of detected defect objects")
    inference_time_ms: float = Field(..., description="Detection inference latency in milliseconds")
    model_name: str = Field(..., description="Detector model name (e.g. yolov8s)")
    device: str = Field(..., description="Inference compute device ('cuda' or 'cpu')")
    warning: Optional[str] = Field(None, description="Operational warnings or quality disclaimers")
    annotated_image_base64: Optional[str] = Field(None, description="Base64 encoded PNG of image with drawn bounding boxes")
    settings_used: Optional[Dict[str, Any]] = Field(None, description="Inference settings applied for detection")



class DetectorHealthInfo(BaseModel):
    loaded: bool = Field(..., description="Whether YOLO detector model is loaded into memory")
    model_name: str = Field(..., description="Backbone architecture or model name")
    model_path: str = Field(..., description="Path or filename of detector checkpoint")
    classes: List[str] = Field(..., description="List of defect classes detected")
    device: str = Field(..., description="Compute device used for detection ('cuda' or 'cpu')")
    imgsz: Optional[int] = Field(1024, description="Inference image resolution")
    map50: Optional[float] = Field(None, description="Validation mAP@0.5 metric")
    map50_95: Optional[float] = Field(None, description="Validation mAP@0.5:0.95 metric")


class ClassifierHealthInfo(BaseModel):
    loaded: bool = Field(..., description="Whether EfficientNet-B0 crop classifier is loaded")
    model_name: str = Field("efficientnet_b0", description="Classifier architecture")
    model_path: str = Field("efficientnet_b0_best.pth", description="Checkpoint filename")
    device: Optional[str] = Field(None, description="Compute device used for classification")


class BatchImageResult(BaseModel):
    index: int = Field(..., description="0-based index of the image in the uploaded batch")
    filename: str = Field(..., description="Sanitized unique filename")
    width: int = Field(0, description="Original image width in pixels")
    height: int = Field(0, description="Original image height in pixels")
    total_defects: int = Field(0, description="Total defect count detected on this board")
    defect_summary: Dict[str, int] = Field(default_factory=dict, description="Defect counts grouped by class")
    detections: List[DetectionItem] = Field(default_factory=list, description="List of detected defect objects")
    thumb_url: Optional[str] = Field(None, description="URL path to thumbnail JPEG")
    image_url: Optional[str] = Field(None, description="URL path to full annotated JPEG")
    warning: Optional[str] = Field(None, description="Operational warning (e.g. no defects detected above confidence threshold)")
    error: Optional[str] = Field(None, description="Error message if inference/processing failed on this image")


class BatchStatusResponse(BaseModel):
    status: str = Field(..., description="Batch execution status ('processing', 'done', or 'failed')")
    processed: int = Field(..., description="Number of images processed so far")
    total: int = Field(..., description="Total images in batch")
    errors: List[Any] = Field(default_factory=list, description="List of errors encountered during batch processing")


class BatchInitResponse(BaseModel):
    batch_id: str = Field(..., description="Unique UUID identifying the batch job")
    total: int = Field(..., description="Total number of images accepted for processing")
    status: str = Field("processing", description="Initial status of the batch job")


class BatchResultsResponse(BaseModel):
    batch_id: str = Field(..., description="Unique UUID identifying the batch job")
    status: str = Field(..., description="Batch execution status ('processing', 'done', or 'failed')")
    processed: int = Field(..., description="Number of images processed so far")
    total: int = Field(..., description="Total number of images in batch")
    images_with_detections: int = Field(0, description="Number of boards with >= 1 defect")
    images_without_detections: int = Field(0, description="Number of boards with no defects detected above confidence threshold")
    total_defects: int = Field(0, description="Total number of defects detected across all batch boards")
    per_class_counts: Dict[str, int] = Field(default_factory=dict, description="Aggregate defect counts grouped by class")
    images: List[BatchImageResult] = Field(default_factory=list, description="Per-image detection results")
    settings_used: Optional[Dict[str, Any]] = Field(None, description="Inference settings applied to this batch")
    errors: List[Any] = Field(default_factory=list, description="List of errors encountered across the batch")


class BatchDeleteResponse(BaseModel):
    batch_id: str = Field(..., description="UUID of the batch")
    deleted: bool = Field(True, description="Whether the batch files and directory were removed")


class BatchHealthInfo(BaseModel):
    active_batches: int = Field(0, description="Number of batches currently processing")
    max_concurrent_batches: int = Field(2, description="Maximum allowed concurrent batches")
    storage_dir: str = Field(..., description="Batch temporary filesystem directory path")


class HealthResponse(BaseModel):
    status: str
    device: str
    cuda_available: bool
    gpu_name: Optional[str] = None
    active_model: str = Field(..., description="Active primary model architecture or status")
    checkpoint: str = Field(..., description="Active checkpoint name")
    supported_classes: List[str]
    uptime_seconds: float
    detector: Optional[DetectorHealthInfo] = None
    detector_loaded: Optional[bool] = None
    detector_model_path: Optional[str] = None
    detector_classes: Optional[List[str]] = None
    classifier: Optional[ClassifierHealthInfo] = None
    classifier_loaded: Optional[bool] = None
    batch: Optional[BatchHealthInfo] = None

