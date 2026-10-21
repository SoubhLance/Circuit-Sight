#!/usr/bin/env python3
"""
CircuitSight - Test Split Detector Evaluation Script
===================================================
Evaluates the YOLOv8 PCB Defect Detector against ground-truth YOLO labels on the test split.

Requirements:
- Evaluates each image in backend/data/yolo_dataset/images/test (all classes)
- Runs detector at confidence threshold 0.25
- Compares with YOLO label files in backend/data/yolo_dataset/labels/test using IoU >= 0.5 and matching class
- Prints per-class TP, FP, FN, Precision, Recall
- Prints the 10 images with the most false positives
- Prints the average number of detections per image for each class folder
- Does not change model files or pip install any package
"""

import argparse
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import torch
from PIL import Image
from ultralytics import YOLO

# Standard 6 PCB defect classes
DEFAULT_CLASSES = [
    "missing_hole",
    "mouse_bite",
    "open_circuit",
    "short",
    "spur",
    "spurious_copper",
]


def resolve_paths() -> Tuple[Path, Path, Path, Path]:
    """Resolves project root, dataset directories, and model checkpoint."""
    script_dir = Path(__file__).resolve().parent
    # Project root is either parent of backend (if script in backend/scripts) or script_dir.parents[1]
    backend_dir = script_dir.parent if script_dir.name == "scripts" else script_dir
    project_root = backend_dir.parent

    # Try standard paths
    dataset_candidates = [
        backend_dir / "data" / "yolo_dataset",
        project_root / "backend" / "data" / "yolo_dataset",
        project_root / "data" / "yolo_dataset",
    ]
    data_dir = next((d for d in dataset_candidates if d.exists()), dataset_candidates[0])

    images_dir = data_dir / "images" / "test"
    labels_dir = data_dir / "labels" / "test"

    model_candidates = [
        backend_dir / "models" / "yolov8_pcb_best.pt",
        project_root / "backend" / "models" / "yolov8_pcb_best.pt",
        project_root / "models" / "yolov8_pcb_best.pt",
    ]
    model_path = next((m for m in model_candidates if m.exists()), model_candidates[0])

    return project_root, images_dir, labels_dir, model_path


def compute_iou(box1: List[float], box2: List[float]) -> float:
    """
    Computes Intersection over Union (IoU) between two bounding boxes.
    Box format: [x1, y1, x2, y2]
    """
    x1 = max(box1[0], box2[0])
    y1 = max(box1[1], box2[1])
    x2 = min(box1[2], box2[2])
    y2 = min(box1[3], box2[3])

    inter_w = max(0.0, x2 - x1)
    inter_h = max(0.0, y2 - y1)
    inter_area = inter_w * inter_h

    area1 = max(0.0, box1[2] - box1[0]) * max(0.0, box1[3] - box1[1])
    area2 = max(0.0, box2[2] - box2[0]) * max(0.0, box2[3] - box2[1])
    union_area = area1 + area2 - inter_area

    if union_area <= 0.0:
        return 0.0
    return inter_area / union_area


def parse_yolo_labels(
    label_path: Path, img_width: int, img_height: int
) -> List[Tuple[int, List[float]]]:
    """
    Parses YOLO ground truth labels from a .txt file.
    Each line format: class_id x_center y_center width height (normalized)
    Returns: List of (class_id, [x1, y1, x2, y2] in pixels)
    """
    boxes = []
    if not label_path.exists():
        return boxes

    with open(label_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) != 5:
                continue
            cls_id = int(parts[0])
            xc = float(parts[1]) * img_width
            yc = float(parts[2]) * img_height
            w = float(parts[3]) * img_width
            h = float(parts[4]) * img_height

            x1 = max(0.0, xc - w / 2.0)
            y1 = max(0.0, yc - h / 2.0)
            x2 = min(float(img_width), xc + w / 2.0)
            y2 = min(float(img_height), yc + h / 2.0)

            boxes.append((cls_id, [x1, y1, x2, y2]))

    return boxes


def get_class_folder_name(img_path: Path, test_dir: Path) -> str:
    """
    Extracts the logical class folder name for an image.
    Supports both subfolder structure (e.g. test/missing_hole/08_...)
    and flat dataset naming with double-underscore prefix (e.g. missing_hole__08_...).
    """
    rel = img_path.relative_to(test_dir)
    if len(rel.parts) > 1:
        return rel.parts[0]

    name = img_path.name
    if "__" in name:
        return name.split("__")[0]

    for c in DEFAULT_CLASSES:
        if c in name:
            return c

    return "general"


def evaluate_test_split(
    images_dir: Path,
    labels_dir: Path,
    model_path: Path,
    conf_thresh: float = 0.25,
    iou_thresh: float = 0.5,
    imgsz: int = 1024,
    device: Optional[str] = None,
) -> None:
    """Runs detector on all test images, compares against YOLO ground truth, and prints results."""
    if not images_dir.exists():
        print(f"Error: Images directory not found: {images_dir}", file=sys.stderr)
        sys.exit(1)
    if not labels_dir.exists():
        print(f"Error: Labels directory not found: {labels_dir}", file=sys.stderr)
        sys.exit(1)
    if not model_path.exists():
        print(f"Error: Model checkpoint not found: {model_path}", file=sys.stderr)
        sys.exit(1)

    # Determine compute device
    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"

    device_name = torch.cuda.get_device_name(0) if device == "cuda" else "CPU"

    # Load YOLO model
    print("=" * 86)
    print("CircuitSight - PCB Defect Detection Test Split Evaluation")
    print("=" * 86)
    print(f"Loading YOLOv8 detector: {model_path.name}")
    print(f"Device: {device.upper()} ({device_name})")
    print(f"Confidence Threshold: {conf_thresh:.2f}")
    print(f"IoU Matching Threshold: {iou_thresh:.2f}")
    print(f"Inference Image Size: {imgsz}px")
    print(f"Test Images Directory: {images_dir}")
    print(f"Test Labels Directory: {labels_dir}")
    print("=" * 86)

    t_start_load = time.time()
    model = YOLO(str(model_path))

    # Read class mapping from model or fallback
    class_names = getattr(model, "names", None)
    if not class_names or not isinstance(class_names, dict):
        class_names = {i: name for i, name in enumerate(DEFAULT_CLASSES)}
    num_classes = len(class_names)

    # Gather test images
    img_extensions = {".jpg", ".jpeg", ".png", ".bmp"}
    image_paths = sorted([
        p for p in images_dir.rglob("*") if p.suffix.lower() in img_extensions
    ])

    if not image_paths:
        print(f"Error: No image files found in {images_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(image_paths)} test images across classes.")
    print("Running detector inference and computing IoU matching...")

    # Statistics accumulators
    # Per-class counts
    tp_per_class = defaultdict(int)
    fp_per_class = defaultdict(int)
    fn_per_class = defaultdict(int)
    gt_per_class = defaultdict(int)
    dets_per_class = defaultdict(int)

    # Per-image statistics for identifying highest FP images
    # image_fp_data: List of dicts { 'filename': str, 'path': Path, 'total_fp': int, 'total_gt': int, 'total_dets': int, 'fp_by_class': dict }
    image_fp_data = []

    # Per class folder statistics
    # folder_stats: dict of folder_name -> { 'image_count': int, 'total_dets': int, 'total_gt': int }
    folder_stats = defaultdict(lambda: {"image_count": 0, "total_dets": 0, "total_gt": 0})

    t_eval_start = time.time()

    for idx, img_path in enumerate(image_paths):
        # Progress indicator
        if (idx + 1) % 20 == 0 or idx == len(image_paths) - 1:
            print(f"  Processed {idx + 1}/{len(image_paths)} images ({(idx + 1)/len(image_paths)*100:.1f}%)...")

        # Get image dimensions
        with Image.open(img_path) as im:
            img_w, img_h = im.size

        # Load ground truth boxes for this image
        lbl_file = labels_dir / f"{img_path.stem}.txt"
        gt_boxes = parse_yolo_labels(lbl_file, img_w, img_h)

        # Count GT boxes
        gt_by_class = defaultdict(list)
        for cls_id, box in gt_boxes:
            gt_by_class[cls_id].append(box)
            gt_per_class[cls_id] += 1

        # Run model inference
        results = model.predict(
            str(img_path),
            conf=conf_thresh,
            imgsz=imgsz,
            device=device,
            verbose=False,
        )[0]

        # Extract predictions
        det_by_class = defaultdict(list)
        total_image_dets = len(results.boxes)

        for b in results.boxes:
            cls_id = int(b.cls[0].item())
            conf = float(b.conf[0].item())
            xyxy = b.xyxy[0].tolist()
            det_by_class[cls_id].append((conf, xyxy))
            dets_per_class[cls_id] += 1

        # Update class folder statistics
        folder_name = get_class_folder_name(img_path, images_dir)
        folder_stats[folder_name]["image_count"] += 1
        folder_stats[folder_name]["total_dets"] += total_image_dets
        folder_stats[folder_name]["total_gt"] += len(gt_boxes)

        # Match predictions with ground truth per class using greedy IoU >= 0.5
        image_fp_count = 0
        image_fp_by_class = defaultdict(int)

        # Iterate over all possible classes (0 to num_classes - 1)
        all_active_classes = set(gt_by_class.keys()).union(set(det_by_class.keys()))

        for cls_id in all_active_classes:
            gts = gt_by_class.get(cls_id, [])
            dets = det_by_class.get(cls_id, [])

            # Sort detections descending by confidence
            dets.sort(key=lambda x: x[0], reverse=True)

            matched_gt_indices: Set[int] = set()

            for conf, det_box in dets:
                best_iou = 0.0
                best_gt_idx = -1

                for gt_idx, gt_box in enumerate(gts):
                    if gt_idx in matched_gt_indices:
                        continue
                    iou = compute_iou(det_box, gt_box)
                    if iou > best_iou:
                        best_iou = iou
                        best_gt_idx = gt_idx

                if best_iou >= iou_thresh and best_gt_idx >= 0:
                    tp_per_class[cls_id] += 1
                    matched_gt_indices.add(best_gt_idx)
                else:
                    fp_per_class[cls_id] += 1
                    image_fp_count += 1
                    image_fp_by_class[class_names.get(cls_id, str(cls_id))] += 1

            # Unmatched ground truth boxes are False Negatives (FN)
            fn_count = len(gts) - len(matched_gt_indices)
            fn_per_class[cls_id] += fn_count

        # Record per-image false positive data
        image_fp_data.append({
            "filename": img_path.name,
            "path": img_path,
            "total_fp": image_fp_count,
            "total_gt": len(gt_boxes),
            "total_dets": total_image_dets,
            "fp_by_class": dict(image_fp_by_class),
            "folder": folder_name,
        })

    eval_duration = time.time() - t_eval_start

    # =========================================================================
    # Output 1: Per-Class Performance Table
    # =========================================================================
    print("\n" + "=" * 86)
    print("1. PER-CLASS DETECTION PERFORMANCE (Confidence >= 0.25, IoU >= 0.50)")
    print("=" * 86)
    header = f"{'Class':<18} {'GT':>6} {'Dets':>6} {'TP':>6} {'FP':>6} {'FN':>6} {'Precision':>11} {'Recall':>10} {'F1-Score':>10}"
    print(header)
    print("-" * 86)

    total_gt = 0
    total_dets = 0
    total_tp = 0
    total_fp = 0
    total_fn = 0

    for cls_id in range(num_classes):
        c_name = class_names.get(cls_id, f"class_{cls_id}")
        gt = gt_per_class[cls_id]
        dets = dets_per_class[cls_id]
        tp = tp_per_class[cls_id]
        fp = fp_per_class[cls_id]
        fn = fn_per_class[cls_id]

        prec = (tp / (tp + fp)) * 100.0 if (tp + fp) > 0 else 0.0
        rec = (tp / (tp + fn)) * 100.0 if (tp + fn) > 0 else 0.0
        f1 = (2 * prec * rec / (prec + rec)) if (prec + rec) > 0 else 0.0

        total_gt += gt
        total_dets += dets
        total_tp += tp
        total_fp += fp
        total_fn += fn

        print(
            f"{c_name:<18} {gt:>6} {dets:>6} {tp:>6} {fp:>6} {fn:>6} {prec:>10.2f}% {rec:>9.2f}% {f1:>9.2f}%"
        )

    print("-" * 86)
    tot_prec = (total_tp / (total_tp + total_fp)) * 100.0 if (total_tp + total_fp) > 0 else 0.0
    tot_rec = (total_tp / (total_tp + total_fn)) * 100.0 if (total_tp + total_fn) > 0 else 0.0
    tot_f1 = (2 * tot_prec * tot_rec / (tot_prec + tot_rec)) if (tot_prec + tot_rec) > 0 else 0.0

    print(
        f"{'OVERALL / TOTAL':<18} {total_gt:>6} {total_dets:>6} {total_tp:>6} {total_fp:>6} {total_fn:>6} {tot_prec:>10.2f}% {tot_rec:>9.2f}% {tot_f1:>9.2f}%"
    )
    print("=" * 86)

    # =========================================================================
    # Output 2: Average Number of Detections per Image for Each Class Folder
    # =========================================================================
    print("\n" + "=" * 86)
    print("2. AVERAGE NUMBER OF DETECTIONS PER IMAGE BY CLASS FOLDER")
    print("=" * 86)
    folder_header = f"{'Class Folder':<22} {'Images':>8} {'Total Dets':>12} {'Avg Dets/Image':>16} {'Total GT':>10} {'Avg GT/Image':>14}"
    print(folder_header)
    print("-" * 86)

    # Sort class folders according to DEFAULT_CLASSES order if present, else alphabetical
    def folder_sort_key(f_name: str) -> int:
        if f_name in DEFAULT_CLASSES:
            return DEFAULT_CLASSES.index(f_name)
        return 999

    sorted_folders = sorted(folder_stats.keys(), key=folder_sort_key)

    sum_folder_imgs = 0
    sum_folder_dets = 0
    sum_folder_gt = 0

    for f_name in sorted_folders:
        data = folder_stats[f_name]
        n_imgs = data["image_count"]
        n_dets = data["total_dets"]
        n_gt = data["total_gt"]
        avg_dets = n_dets / n_imgs if n_imgs > 0 else 0.0
        avg_gt = n_gt / n_imgs if n_imgs > 0 else 0.0

        sum_folder_imgs += n_imgs
        sum_folder_dets += n_dets
        sum_folder_gt += n_gt

        print(
            f"{f_name:<22} {n_imgs:>8} {n_dets:>12} {avg_dets:>16.2f} {n_gt:>10} {avg_gt:>14.2f}"
        )

    print("-" * 86)
    overall_avg_dets = sum_folder_dets / sum_folder_imgs if sum_folder_imgs > 0 else 0.0
    overall_avg_gt = sum_folder_gt / sum_folder_imgs if sum_folder_imgs > 0 else 0.0
    print(
        f"{'ALL FOLDERS':<22} {sum_folder_imgs:>8} {sum_folder_dets:>12} {overall_avg_dets:>16.2f} {sum_folder_gt:>10} {overall_avg_gt:>14.2f}"
    )
    print("=" * 86)

    # =========================================================================
    # Output 3: Top 10 Images with the Most False Positives
    # =========================================================================
    print("\n" + "=" * 86)
    print("3. TOP 10 IMAGES WITH THE MOST FALSE POSITIVES")
    print("=" * 86)

    # Sort by total_fp descending, breaking ties by filename
    top_fp_images = sorted(image_fp_data, key=lambda x: (x["total_fp"], x["filename"]), reverse=True)[:10]

    fp_header = f"{'Rank':<5} {'Image Filename':<44} {'FPs':>5} {'GT':>5} {'Dets':>6}  {'FP Breakdown by Class'}"
    print(fp_header)
    print("-" * 86)

    for rank, item in enumerate(top_fp_images, 1):
        fn = item["filename"]
        # Format breakdown string
        breakdown_str = ", ".join(f"{cls}: {cnt}" for cls, cnt in sorted(item["fp_by_class"].items()))
        if not breakdown_str:
            breakdown_str = "None (0 FPs)"

        print(
            f"{rank:>3}.  {fn:<44} {item['total_fp']:>5} {item['total_gt']:>5} {item['total_dets']:>6}  {breakdown_str}"
        )

    print("=" * 86)
    print(f"Evaluation completed in {eval_duration:.2f}s ({len(image_paths)/eval_duration:.1f} images/sec).")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="CircuitSight - Check and evaluate test split detector performance."
    )
    default_root, default_images, default_labels, default_model = resolve_paths()

    parser.add_argument(
        "--images-dir",
        type=Path,
        default=default_images,
        help=f"Directory of test images (default: {default_images})",
    )
    parser.add_argument(
        "--labels-dir",
        type=Path,
        default=default_labels,
        help=f"Directory of test YOLO labels (default: {default_labels})",
    )
    parser.add_argument(
        "--model-path",
        type=Path,
        default=default_model,
        help=f"Path to YOLOv8 weights (.pt) (default: {default_model})",
    )
    parser.add_argument(
        "--conf",
        type=float,
        default=0.25,
        help="Detection confidence threshold (default: 0.25)",
    )
    parser.add_argument(
        "--iou-thresh",
        type=float,
        default=0.50,
        help="IoU matching threshold for TP (default: 0.50)",
    )
    parser.add_argument(
        "--imgsz",
        type=int,
        default=1024,
        help="Inference image size (default: 1024)",
    )
    parser.add_argument(
        "--device",
        type=str,
        default=None,
        help="Inference device: 'cuda', 'cpu', or None for auto (default: auto)",
    )

    args = parser.parse_args()

    evaluate_test_split(
        images_dir=args.images_dir,
        labels_dir=args.labels_dir,
        model_path=args.model_path,
        conf_thresh=args.conf,
        iou_thresh=args.iou_thresh,
        imgsz=args.imgsz,
        device=args.device,
    )


if __name__ == "__main__":
    main()
