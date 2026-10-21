"""
CircuitSight - Batch Detection Manager
Handles batch lifecycle, concurrency limits, chunked GPU inference,
annotated and thumbnail rendering, safe zip creation, and automatic disk cleanup.
"""

import asyncio
import csv
import io
import json
import os
import re
import shutil
import threading
import time
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import cv2
import numpy as np
from PIL import Image
import torch

from prediction import DEFECT_CATALOG, crop_box


MAX_CONCURRENT_BATCHES = 2
BATCH_EXPIRY_SECONDS = 3600  # 60 minutes


class BatchManager:
    """
    Manages batch jobs: staging, GPU chunked inference, disk storage,
    report packaging, status tracking, and scheduled cleanup.
    """

    def __init__(self):
        self.backend_dir = Path(__file__).resolve().parent.parent
        self.batches_root = self.backend_dir / "tmp" / "batches"
        self.batches_root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self.active_batches: Set[str] = set()
        self.batch_states: Dict[str, Dict[str, Any]] = {}

    @property
    def active_batch_count(self) -> int:
        with self._lock:
            return len(self.active_batches)

    def can_accept_batch(self) -> bool:
        with self._lock:
            return len(self.active_batches) < MAX_CONCURRENT_BATCHES

    def get_batch_dir(self, batch_id: str) -> Path:
        return self.batches_root / batch_id

    def sanitize_filenames(self, filenames: List[str]) -> List[str]:
        """
        Sanitizes filenames to prevent zip-slip and directory traversal.
        Extracts basename only, strips invalid characters and path separators,
        and dedupes with _1, _2 suffixes. Output filenames end in .jpg.
        """
        existing: Set[str] = set()
        sanitized_list: List[str] = []

        for name in filenames:
            # Basename only, normalize separators
            raw_base = os.path.basename(name.replace("\\", "/"))
            # Strip control characters, null bytes, path traversal
            cleaned = re.sub(r"[\x00-\x1f\x7f]", "", raw_base)
            cleaned = cleaned.replace("..", "").lstrip(".\\/")
            if not cleaned:
                cleaned = "board"

            p = Path(cleaned)
            stem = p.stem
            stem = re.sub(r"[^a-zA-Z0-9_\-\.]", "_", stem)
            if not stem:
                stem = "board"

            candidate = f"{stem}.jpg"
            counter = 1
            base_stem = stem
            while candidate.lower() in existing:
                candidate = f"{base_stem}_{counter}.jpg"
                counter += 1

            existing.add(candidate.lower())
            sanitized_list.append(candidate)

        return sanitized_list

    def init_batch(
        self,
        batch_id: str,
        total_files: int,
        settings_used: Dict[str, Any],
    ) -> Path:
        """Creates directory structure and registers active batch."""
        batch_dir = self.get_batch_dir(batch_id)
        staging_dir = batch_dir / "_staging"
        annotated_dir = batch_dir / "annotated"
        thumbs_dir = batch_dir / "thumbs"

        staging_dir.mkdir(parents=True, exist_ok=True)
        annotated_dir.mkdir(parents=True, exist_ok=True)
        thumbs_dir.mkdir(parents=True, exist_ok=True)

        with self._lock:
            self.active_batches.add(batch_id)
            self.batch_states[batch_id] = {
                "batch_id": batch_id,
                "status": "processing",
                "processed": 0,
                "total": total_files,
                "errors": [],
                "images": [],
                "settings_used": settings_used,
                "created_at": time.time(),
                "created_iso": datetime.now(timezone.utc).isoformat(),
            }

        return batch_dir

    def run_batch_sync(
        self,
        batch_id: str,
        items: List[Tuple[int, str, str, Path]],  # index, orig_name, sanitized_name, staging_path
        settings: Dict[str, Any],
        detector_mgr: Any,
        predictor: Optional[Any],
    ) -> None:
        """
        Executes GPU inference in chunks of 4 images, generates quality 90 annotated JPEGs,
        480px-wide thumbnail JPEGs, produces report.csv, report.json, README.txt, and report.zip.
        """
        batch_dir = self.get_batch_dir(batch_id)
        annotated_dir = batch_dir / "annotated"
        thumbs_dir = batch_dir / "thumbs"
        staging_dir = batch_dir / "_staging"

        conf = settings.get("conf", 0.25)
        iou = settings.get("iou", 0.45)
        imgsz = settings.get("imgsz", 1024)
        classify_crops = settings.get("classify_crops", False)

        chunk_size = 4
        all_results: List[Dict[str, Any]] = [None] * len(items)  # type: ignore

        try:
            for start_idx in range(0, len(items), chunk_size):
                chunk = items[start_idx : start_idx + chunk_size]
                chunk_pil_images: List[Image.Image] = []
                loaded_indices: List[int] = []

                # Load chunk images
                for item in chunk:
                    idx, orig_name, san_name, stg_path = item
                    try:
                        pil_img = Image.open(stg_path).convert("RGB")
                        chunk_pil_images.append(pil_img)
                        loaded_indices.append(idx)
                    except Exception as load_exc:
                        err_msg = f"Failed to load image for inference: {load_exc}"
                        all_results[idx] = {
                            "index": idx,
                            "filename": san_name,
                            "width": 0,
                            "height": 0,
                            "total_defects": 0,
                            "defect_summary": {},
                            "detections": [],
                            "thumb_url": None,
                            "image_url": None,
                            "warning": None,
                            "error": err_msg,
                        }
                        self._record_error(batch_id, idx, san_name, err_msg)
                        stg_path.unlink(missing_ok=True)

                if not chunk_pil_images:
                    continue

                # Run GPU inference with fallback for single image failure
                chunk_results = None
                try:
                    with torch.no_grad():
                        chunk_results = detector_mgr.predict(
                            chunk_pil_images,
                            conf=conf,
                            iou=iou,
                            imgsz=imgsz,
                        )
                except Exception as batch_infer_exc:
                    print(f"[CircuitSight] Chunk inference error, falling back to per-image inference: {batch_infer_exc}")

                # Process results per image
                for i, img_idx in enumerate(loaded_indices):
                    _, orig_name, san_name, stg_path = items[img_idx]
                    pil_img = chunk_pil_images[i]
                    img_w, img_h = pil_img.size

                    try:
                        if chunk_results is not None and i < len(chunk_results):
                            yolo_res = chunk_results[i]
                        else:
                            with torch.no_grad():
                                single_infer = detector_mgr.predict(
                                    pil_img,
                                    conf=conf,
                                    iou=iou,
                                    imgsz=imgsz,
                                )
                                yolo_res = single_infer[0]

                        # Extract detections
                        detections: List[Dict[str, Any]] = []
                        defect_summary: Dict[str, int] = {}

                        if yolo_res.boxes is not None and len(yolo_res.boxes) > 0:
                            for box in yolo_res.boxes:
                                cls_idx = int(box.cls[0].item())
                                class_name = yolo_res.names.get(
                                    cls_idx,
                                    detector_mgr.classes[cls_idx]
                                    if cls_idx < len(detector_mgr.classes)
                                    else f"class_{cls_idx}",
                                )
                                box_conf = round(float(box.conf[0].item()), 4)

                                xyxy = box.xyxy[0].tolist()
                                x1 = max(0, min(img_w, int(round(xyxy[0]))))
                                y1 = max(0, min(img_h, int(round(xyxy[1]))))
                                x2 = max(0, min(img_w, int(round(xyxy[2]))))
                                y2 = max(0, min(img_h, int(round(xyxy[3]))))
                                bbox = [x1, y1, x2, y2]

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
                                defect_details = {
                                    "name": cat_entry.get("name", class_name.replace("_", " ").title()),
                                    "severity": cat_entry.get("severity", "Medium"),
                                    "description": cat_entry.get("description", ""),
                                    "risk": cat_entry.get("risk", ""),
                                    "remediation": cat_entry.get("remediation", ""),
                                }

                                # Optional crop classifier
                                classifier_class = None
                                classifier_confidence = None
                                if classify_crops and predictor is not None:
                                    try:
                                        c_xmin, c_ymin, c_xmax, c_ymax = crop_box(
                                            xmin=x1,
                                            ymin=y1,
                                            xmax=x2,
                                            ymax=y2,
                                            width=img_w,
                                            height=img_h,
                                            scale=2.5,
                                            min_crop=64,
                                        )
                                        crop_patch = pil_img.crop((c_xmin, c_ymin, c_xmax, c_ymax))
                                        clf_pred = predictor.predict(crop_patch, return_heatmap=False)
                                        classifier_class = clf_pred["predicted_class"]
                                        classifier_confidence = clf_pred["confidence"]
                                    except Exception as clf_exc:
                                        print(f"[CircuitSight] Batch crop classification error: {clf_exc}")

                                detections.append({
                                    "class_name": class_name,
                                    "confidence": box_conf,
                                    "bbox": bbox,
                                    "defect_details": defect_details,
                                    "classifier_class": classifier_class,
                                    "classifier_confidence": classifier_confidence,
                                })
                                defect_summary[class_name] = defect_summary.get(class_name, 0) + 1

                        # Plot bounding boxes and annotations
                        annot_bgr = yolo_res.plot(line_width=2, font_size=12)
                        annot_file_path = annotated_dir / san_name
                        cv2.imwrite(str(annot_file_path), annot_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 90])

                        # Create 480px-wide thumbnail
                        thumb_w = 480
                        thumb_h = max(1, int(round(img_h * (thumb_w / max(1, img_w)))))
                        thumb_bgr = cv2.resize(annot_bgr, (thumb_w, thumb_h), interpolation=cv2.INTER_AREA)
                        thumb_file_path = thumbs_dir / f"{img_idx}.jpg"
                        cv2.imwrite(str(thumb_file_path), thumb_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 85])

                        # Warnings
                        warnings: List[str] = []
                        if max(img_w, img_h) < 800:
                            warnings.append(
                                "Low-resolution input. Detector was trained on ~3000px board photos, so results may be unreliable."
                            )
                        if len(detections) == 0:
                            warnings.append(
                                "No defects detected above the confidence threshold. This is not a guarantee the board is defect-free."
                            )
                        warning_str = " ".join(warnings) if warnings else None

                        all_results[img_idx] = {
                            "index": img_idx,
                            "filename": san_name,
                            "width": img_w,
                            "height": img_h,
                            "total_defects": len(detections),
                            "defect_summary": defect_summary,
                            "detections": detections,
                            "thumb_url": f"/api/batch/{batch_id}/thumb/{img_idx}",
                            "image_url": f"/api/batch/{batch_id}/image/{img_idx}",
                            "warning": warning_str,
                            "error": None,
                        }

                    except Exception as img_process_exc:
                        err_msg = f"Error processing image #{img_idx}: {img_process_exc}"
                        all_results[img_idx] = {
                            "index": img_idx,
                            "filename": san_name,
                            "width": img_w,
                            "height": img_h,
                            "total_defects": 0,
                            "defect_summary": {},
                            "detections": [],
                            "thumb_url": None,
                            "image_url": None,
                            "warning": None,
                            "error": err_msg,
                        }
                        self._record_error(batch_id, img_idx, san_name, err_msg)

                    finally:
                        stg_path.unlink(missing_ok=True)
                        with self._lock:
                            if batch_id in self.batch_states:
                                self.batch_states[batch_id]["processed"] += 1

            # Cleanup staging dir
            shutil.rmtree(staging_dir, ignore_errors=True)

            # Generate aggregate metrics
            valid_results = [r for r in all_results if r is not None]
            images_with_defects = sum(1 for r in valid_results if r.get("total_defects", 0) > 0)
            images_without_defects = sum(
                1 for r in valid_results if r.get("total_defects", 0) == 0 and not r.get("error")
            )
            total_defects = sum(r.get("total_defects", 0) for r in valid_results)

            per_class_counts: Dict[str, int] = {}
            for r in valid_results:
                for cls_name, count in r.get("defect_summary", {}).items():
                    per_class_counts[cls_name] = per_class_counts.get(cls_name, 0) + count

            batch_status = "done" if any(not r.get("error") for r in valid_results) else "failed"

            # Create report files on disk
            self._write_reports(
                batch_id=batch_id,
                batch_dir=batch_dir,
                results=valid_results,
                settings=settings,
                images_with_defects=images_with_defects,
                images_without_defects=images_without_defects,
                total_defects=total_defects,
                per_class_counts=per_class_counts,
                detector_mgr=detector_mgr,
            )

            # Update in-memory state
            with self._lock:
                if batch_id in self.batch_states:
                    st = self.batch_states[batch_id]
                    st["status"] = batch_status
                    st["images_with_detections"] = images_with_defects
                    st["images_without_detections"] = images_without_defects
                    st["total_defects"] = total_defects
                    st["per_class_counts"] = per_class_counts
                    st["images"] = valid_results

        except Exception as batch_fatal_exc:
            print(f"[CircuitSight] Fatal batch failure for {batch_id}: {batch_fatal_exc}")
            with self._lock:
                if batch_id in self.batch_states:
                    self.batch_states[batch_id]["status"] = "failed"
                    self.batch_states[batch_id]["errors"].append(f"Fatal batch error: {batch_fatal_exc}")
        finally:
            with self._lock:
                self.active_batches.discard(batch_id)

    def _record_error(self, batch_id: str, index: int, filename: str, error: str) -> None:
        with self._lock:
            if batch_id in self.batch_states:
                self.batch_states[batch_id]["errors"].append({
                    "index": index,
                    "filename": filename,
                    "error": error,
                })

    def _write_reports(
        self,
        batch_id: str,
        batch_dir: Path,
        results: List[Dict[str, Any]],
        settings: Dict[str, Any],
        images_with_defects: int,
        images_without_defects: int,
        total_defects: int,
        per_class_counts: Dict[str, int],
        detector_mgr: Any,
    ) -> None:
        """Generates README.txt, report.csv, report.json, report.zip, and results.json."""
        conf = settings.get("conf", 0.25)
        iou = settings.get("iou", 0.45)
        imgsz = settings.get("imgsz", 1024)

        # 1. README.txt
        readme_path = batch_dir / "README.txt"
        readme_content = f"""CircuitSight - PCB Defect Detection Batch Report
=====================================================
Batch ID: {batch_id}
Generated: {datetime.now(timezone.utc).isoformat()}
Detector Model: {getattr(detector_mgr, 'model_name', 'yolov8s')}
Inference Resolution: {imgsz}px
Confidence Threshold: {conf}
IoU NMS Threshold: {iou}

Summary:
- Total Images Processed: {len(results)}
- Boards With Defects: {images_with_defects}
- Boards Without Detected Defects: {images_without_defects}
- Total Defects Localized: {total_defects}

CRITICAL INSPECTION NOTICE:
"No defects detected above the confidence threshold" indicates that the model did not
detect manufacturing anomalies meeting the configured confidence threshold ({conf}).
This is NOT a guarantee that the printed circuit board is defect-free. All safety-critical
assemblies must undergo complete secondary electrical testing and manual QA verification.
"""
        with open(readme_path, "w", encoding="utf-8") as f:
            f.write(readme_content)

        # 2. report.csv
        csv_path = batch_dir / "report.csv"
        fieldnames = [
            "filename",
            "width",
            "height",
            "total_defects",
            "missing_hole",
            "mouse_bite",
            "open_circuit",
            "short",
            "spur",
            "spurious_copper",
            "max_confidence",
        ]
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in results:
                ds = r.get("defect_summary", {})
                dets = r.get("detections", [])
                max_conf = max([d["confidence"] for d in dets], default=0.0) if dets else 0.0
                row = {
                    "filename": r.get("filename", ""),
                    "width": r.get("width", 0),
                    "height": r.get("height", 0),
                    "total_defects": r.get("total_defects", 0),
                    "missing_hole": ds.get("missing_hole", 0),
                    "mouse_bite": ds.get("mouse_bite", 0),
                    "open_circuit": ds.get("open_circuit", 0),
                    "short": ds.get("short", 0),
                    "spur": ds.get("spur", 0),
                    "spurious_copper": ds.get("spurious_copper", 0),
                    "max_confidence": round(max_conf, 4),
                }
                writer.writerow(row)

        # 3. report.json
        report_json_path = batch_dir / "report.json"
        report_data = {
            "batch_id": batch_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "settings_used": settings,
            "summary": {
                "total_images": len(results),
                "images_with_detections": images_with_defects,
                "images_without_detections": images_without_defects,
                "total_defects": total_defects,
                "per_class_counts": per_class_counts,
            },
            "results": results,
        }
        with open(report_json_path, "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2)

        # 4. results.json (complete endpoint representation for persistent reload)
        results_path = batch_dir / "results.json"
        with self._lock:
            current_st = self.batch_states.get(batch_id, {})
            errors = current_st.get("errors", [])

        full_results = {
            "batch_id": batch_id,
            "status": "done" if any(not r.get("error") for r in results) else "failed",
            "processed": len(results),
            "total": len(results),
            "images_with_detections": images_with_defects,
            "images_without_detections": images_without_defects,
            "total_defects": total_defects,
            "per_class_counts": per_class_counts,
            "images": results,
            "settings_used": settings,
            "errors": errors,
        }
        with open(results_path, "w", encoding="utf-8") as f:
            json.dump(full_results, f, indent=2)

        # 5. report.zip (built on disk so 50 large images do not sit in RAM)
        zip_path = batch_dir / "report.zip"
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            # Add top-level reports
            zf.write(readme_path, arcname="README.txt")
            zf.write(csv_path, arcname="report.csv")
            zf.write(report_json_path, arcname="report.json")

            # Add annotated full-size JPEGs
            annotated_dir = batch_dir / "annotated"
            if annotated_dir.exists():
                for img_file in annotated_dir.iterdir():
                    if img_file.is_file() and img_file.suffix.lower() == ".jpg":
                        # Entry name uses standard relative path: annotated/<filename>.jpg
                        # Contains no '..', no '\', and no leading '/'
                        safe_entry_name = f"annotated/{img_file.name}"
                        zf.write(img_file, arcname=safe_entry_name)

    def get_status(self, batch_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            if batch_id in self.batch_states:
                st = self.batch_states[batch_id]
                return {
                    "status": st["status"],
                    "processed": st["processed"],
                    "total": st["total"],
                    "errors": st.get("errors", []),
                }

        # Check disk if not in memory
        batch_dir = self.get_batch_dir(batch_id)
        results_file = batch_dir / "results.json"
        if results_file.exists():
            try:
                with open(results_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return {
                        "status": data.get("status", "done"),
                        "processed": data.get("processed", len(data.get("images", []))),
                        "total": data.get("total", len(data.get("images", []))),
                        "errors": data.get("errors", []),
                    }
            except Exception:
                pass

        if batch_dir.exists():
            return {
                "status": "processing",
                "processed": 0,
                "total": 0,
                "errors": [],
            }

        return None

    def get_results(self, batch_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            if batch_id in self.batch_states:
                st = self.batch_states[batch_id]
                if st.get("images") or st.get("status") in ("done", "failed"):
                    return {
                        "batch_id": batch_id,
                        "status": st["status"],
                        "processed": st["processed"],
                        "total": st["total"],
                        "images_with_detections": st.get("images_with_detections", 0),
                        "images_without_detections": st.get("images_without_detections", 0),
                        "total_defects": st.get("total_defects", 0),
                        "per_class_counts": st.get("per_class_counts", {}),
                        "images": st.get("images", []),
                        "settings_used": st.get("settings_used", {}),
                        "errors": st.get("errors", []),
                    }

        batch_dir = self.get_batch_dir(batch_id)
        results_file = batch_dir / "results.json"
        if results_file.exists():
            try:
                with open(results_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"[CircuitSight] Error reading results.json for {batch_id}: {e}")

        if batch_dir.exists():
            with self._lock:
                st = self.batch_states.get(batch_id, {})
                return {
                    "batch_id": batch_id,
                    "status": st.get("status", "processing"),
                    "processed": st.get("processed", 0),
                    "total": st.get("total", 0),
                    "images_with_detections": 0,
                    "images_without_detections": 0,
                    "total_defects": 0,
                    "per_class_counts": {},
                    "images": [],
                    "settings_used": st.get("settings_used", {}),
                    "errors": st.get("errors", []),
                }

        return None

    def get_annotated_image_path(self, batch_id: str, index: int) -> Optional[Path]:
        batch_dir = self.get_batch_dir(batch_id)
        if not batch_dir.exists():
            return None

        # Look up filename by index in results
        results = self.get_results(batch_id)
        if results and "images" in results:
            for img in results["images"]:
                if img.get("index") == index:
                    fn = img.get("filename")
                    if fn:
                        p = batch_dir / "annotated" / fn
                        if p.exists():
                            return p

        # Fallback search in annotated directory
        annotated_dir = batch_dir / "annotated"
        if annotated_dir.exists():
            files = sorted(list(annotated_dir.iterdir()))
            if 0 <= index < len(files) and files[index].is_file():
                return files[index]

        return None

    def get_thumb_path(self, batch_id: str, index: int) -> Optional[Path]:
        batch_dir = self.get_batch_dir(batch_id)
        thumb_path = batch_dir / "thumbs" / f"{index}.jpg"
        if thumb_path.exists():
            return thumb_path
        return None

    def get_zip_path(self, batch_id: str) -> Optional[Path]:
        batch_dir = self.get_batch_dir(batch_id)
        zip_path = batch_dir / "report.zip"
        if zip_path.exists():
            return zip_path
        return None

    def get_combined_zip_path(self, batch_ids: List[str]) -> Path:
        """
        Creates a combined ZIP report for multiple completed batches.
        Merges README.txt, report.csv, report.json, and annotated images.
        """
        if not batch_ids:
            raise ValueError("No batch IDs provided.")

        clean_ids = [b.strip() for b in batch_ids if b.strip()]
        if len(clean_ids) == 1:
            zp = self.get_zip_path(clean_ids[0])
            if zp and zp.exists():
                return zp
            raise FileNotFoundError(f"Report archive for batch '{clean_ids[0]}' not found.")

        # Hash or concatenate IDs for unique zip filename
        combined_name = f"combined_{'_'.join([b[:8] for b in clean_ids])}.zip"
        combined_zip_path = self.batches_root / combined_name

        all_batch_results = []
        all_annotated_files: List[Tuple[str, Path]] = []
        seen_names: Set[str] = set()

        for b_id in clean_ids:
            st = self.get_status(b_id)
            if not st:
                raise FileNotFoundError(f"Batch '{b_id}' not found.")
            if st["status"] == "processing":
                raise ValueError(f"Batch '{b_id}' is still processing.")

            res = self.get_results(b_id)
            if res:
                all_batch_results.append(res)

            batch_annot_dir = self.get_batch_dir(b_id) / "annotated"
            if batch_annot_dir.exists():
                for f in sorted(list(batch_annot_dir.iterdir())):
                    if f.is_file() and f.suffix.lower() == ".jpg":
                        entry_name = f.name
                        counter = 1
                        stem = f.stem
                        while entry_name.lower() in seen_names:
                            entry_name = f"{stem}_{counter}.jpg"
                            counter += 1
                        seen_names.add(entry_name.lower())
                        all_annotated_files.append((entry_name, f))

        # Generate combined zip on disk
        with zipfile.ZipFile(combined_zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            # 1. Annotated files
            for entry_name, file_path in all_annotated_files:
                zf.write(file_path, arcname=f"annotated/{entry_name}")

            # 2. Combined README
            total_imgs = sum(b.get("total", len(b.get("images", []))) for b in all_batch_results)
            tot_defects = sum(b.get("total_defects", 0) for b in all_batch_results)
            with_def = sum(b.get("images_with_detections", 0) for b in all_batch_results)
            without_def = sum(b.get("images_without_detections", 0) for b in all_batch_results)

            readme_text = f"""CircuitSight - PCB Defect Detection Combined Batch Report
============================================================
Batch IDs: {', '.join(clean_ids)}
Generated: {datetime.now(timezone.utc).isoformat()}
Total Batches: {len(clean_ids)}
Total Images: {total_imgs}
Boards With Detections: {with_def}
Boards Without Detected Defects: {without_def}
Total Defects: {tot_defects}

CRITICAL INSPECTION NOTICE:
"No defects detected above the confidence threshold" indicates that the model did not
detect manufacturing anomalies meeting the configured confidence threshold.
This is NOT a guarantee that the printed circuit board is defect-free. All safety-critical
assemblies must undergo complete secondary electrical testing and manual QA verification.
"""
            zf.writestr("README.txt", readme_text)

            # 3. Combined report.csv
            fieldnames = [
                "batch_id",
                "filename",
                "width",
                "height",
                "total_defects",
                "missing_hole",
                "mouse_bite",
                "open_circuit",
                "short",
                "spur",
                "spurious_copper",
                "max_confidence",
            ]
            csv_buf = io.StringIO()
            writer = csv.DictWriter(csv_buf, fieldnames=fieldnames)
            writer.writeheader()
            for b in all_batch_results:
                b_id = b.get("batch_id", "")
                for r in b.get("images", []):
                    ds = r.get("defect_summary", {})
                    dets = r.get("detections", [])
                    max_conf = max([d["confidence"] for d in dets], default=0.0) if dets else 0.0
                    writer.writerow({
                        "batch_id": b_id,
                        "filename": r.get("filename", ""),
                        "width": r.get("width", 0),
                        "height": r.get("height", 0),
                        "total_defects": r.get("total_defects", 0),
                        "missing_hole": ds.get("missing_hole", 0),
                        "mouse_bite": ds.get("mouse_bite", 0),
                        "open_circuit": ds.get("open_circuit", 0),
                        "short": ds.get("short", 0),
                        "spur": ds.get("spur", 0),
                        "spurious_copper": ds.get("spurious_copper", 0),
                        "max_confidence": round(max_conf, 4),
                    })
            zf.writestr("report.csv", csv_buf.getvalue())

            # 4. Combined report.json
            combined_json = {
                "batch_ids": clean_ids,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "summary": {
                    "total_batches": len(clean_ids),
                    "total_images": total_imgs,
                    "images_with_detections": with_def,
                    "images_without_detections": without_def,
                    "total_defects": tot_defects,
                },
                "batches": all_batch_results,
            }
            zf.writestr("report.json", json.dumps(combined_json, indent=2))

        return combined_zip_path

    def delete_batch(self, batch_id: str) -> bool:
        batch_dir = self.get_batch_dir(batch_id)
        existed = False
        if batch_dir.exists():
            shutil.rmtree(batch_dir, ignore_errors=True)
            existed = True

        with self._lock:
            self.active_batches.discard(batch_id)
            if batch_id in self.batch_states:
                del self.batch_states[batch_id]
                existed = True

        return existed

    def cleanup_expired_batches(self, max_age_seconds: int = BATCH_EXPIRY_SECONDS) -> int:
        """Deletes batch folders older than max_age_seconds (60 minutes)."""
        if not self.batches_root.exists():
            return 0

        now = time.time()
        deleted_count = 0
        try:
            for batch_folder in self.batches_root.iterdir():
                if batch_folder.is_dir():
                    try:
                        mtime = batch_folder.stat().st_mtime
                        if (now - mtime) > max_age_seconds:
                            b_id = batch_folder.name
                            shutil.rmtree(batch_folder, ignore_errors=True)
                            with self._lock:
                                self.active_batches.discard(b_id)
                                self.batch_states.pop(b_id, None)
                            deleted_count += 1
                    except Exception as folder_exc:
                        print(f"[CircuitSight] Error cleaning up batch folder {batch_folder}: {folder_exc}")
        except Exception as exc:
            print(f"[CircuitSight] Error scanning batch directories for cleanup: {exc}")

        return deleted_count

    async def periodic_cleanup_loop(self, interval_seconds: int = 300) -> None:
        """Periodic background task that cleans up expired batch folders."""
        while True:
            try:
                await asyncio.sleep(interval_seconds)
                deleted = self.cleanup_expired_batches()
                if deleted > 0:
                    print(f"[CircuitSight] Cleaned up {deleted} expired batch folders.")
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[CircuitSight Warning] Periodic batch cleanup error: {e}")


# Global Singleton
batch_manager = BatchManager()


def get_batch_manager() -> BatchManager:
    return batch_manager
