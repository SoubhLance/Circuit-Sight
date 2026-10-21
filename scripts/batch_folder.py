#!/usr/bin/env python3
"""
CircuitSight - CLI Batch Folder Detection Script
Uploads a directory of PCB images in chunks of 50 to the CircuitSight FastAPI backend,
tracks overall progress, merges defect metrics, and downloads the inspection report ZIP.
"""

import argparse
import io
import json
import os
import sys
import time
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import List, Tuple

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp"}


def find_image_files(folder_path: Path) -> List[Path]:
    """Recursively collects all valid PCB images in folder_path."""
    images: List[Path] = []
    for root, _, files in os.walk(folder_path):
        for f in files:
            p = Path(root) / f
            if p.suffix.lower() in ALLOWED_EXTENSIONS:
                images.append(p)
    return sorted(images)


def build_multipart_body(
    files: List[Path],
    fields: dict,
    boundary: str,
) -> bytes:
    """Builds multipart/form-data payload without third-party dependencies."""
    body = io.BytesIO()

    # Add text fields
    for key, value in fields.items():
        body.write(f"--{boundary}\r\n".encode("utf-8"))
        body.write(f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode("utf-8"))
        body.write(f"{value}\r\n".encode("utf-8"))

    # Add image files
    for file_path in files:
        filename = file_path.name
        content_type = "image/jpeg"
        if file_path.suffix.lower() == ".png":
            content_type = "image/png"
        elif file_path.suffix.lower() == ".bmp":
            content_type = "image/bmp"

        with open(file_path, "rb") as f:
            data = f.read()

        body.write(f"--{boundary}\r\n".encode("utf-8"))
        body.write(
            f'Content-Disposition: form-data; name="files"; filename="{filename}"\r\n'.encode("utf-8")
        )
        body.write(f"Content-Type: {content_type}\r\n\r\n".encode("utf-8"))
        body.write(data)
        body.write(b"\r\n")

    body.write(f"--{boundary}--\r\n".encode("utf-8"))
    return body.getvalue()


def post_batch(
    api_url: str,
    files: List[Path],
    conf: float,
    iou: float,
    imgsz: int,
    classify_crops: bool,
) -> dict:
    """Submits a chunk of up to 50 files to POST /api/batch."""
    endpoint = f"{api_url.rstrip('/')}/api/batch"
    boundary = f"----WebKitFormBoundary{uuid.uuid4().hex}"

    fields = {
        "conf": str(conf),
        "iou": str(iou),
        "imgsz": str(imgsz),
        "classify_crops": "true" if classify_crops else "false",
    }

    body = build_multipart_body(files, fields, boundary)
    headers = {
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "Content-Length": str(len(body)),
    }

    req = urllib.request.Request(endpoint, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_text = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {e.code} Error submitting batch: {error_text}")


def poll_status(api_url: str, batch_id: str, poll_interval: float = 1.0) -> dict:
    """Polls GET /api/batch/{batch_id}/status until completed."""
    endpoint = f"{api_url.rstrip('/')}/api/batch/{batch_id}/status"

    while True:
        req = urllib.request.Request(endpoint, method="GET")
        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                st = data.get("status")
                if st in ("done", "failed"):
                    return data
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"Failed to poll status for {batch_id}: HTTP {e.code}")

        time.sleep(poll_interval)


def download_zip(api_url: str, batch_ids: List[str], dest_path: Path) -> None:
    """Downloads batch zip (combined or single) to destination path."""
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    if len(batch_ids) == 1:
        endpoint = f"{api_url.rstrip('/')}/api/batch/{batch_ids[0]}/zip"
    else:
        query_str = urllib.parse.urlencode({"ids": ",".join(batch_ids)})
        endpoint = f"{api_url.rstrip('/')}/api/batch/zip?{query_str}"

    req = urllib.request.Request(endpoint, method="GET")
    with urllib.request.urlopen(req) as resp, open(dest_path, "wb") as out_f:
        while True:
            chunk = resp.read(65536)
            if not chunk:
                break
            out_f.write(chunk)


def main():
    parser = argparse.ArgumentParser(
        description="CircuitSight Batch PCB Defect Detection Folder Runner"
    )
    parser.add_argument("folder", type=str, help="Path to directory containing PCB board images")
    parser.add_argument("--api", type=str, default="http://127.0.0.1:8000", help="FastAPI backend host URL")
    parser.add_argument("--conf", type=float, default=0.25, help="Confidence threshold (0.01 to 0.99)")
    parser.add_argument("--iou", type=float, default=0.45, help="IoU NMS threshold (0.01 to 0.99)")
    parser.add_argument("--imgsz", type=int, default=1024, help="Inference image resolution")
    parser.add_argument("--classify-crops", action="store_true", help="Enable EfficientNet-B0 crop classifier")
    parser.add_argument("--output", type=str, default="./batch_results", help="Directory to save downloaded ZIP report")

    args = parser.parse_args()
    folder_path = Path(args.folder).resolve()

    if not folder_path.exists() or not folder_path.is_dir():
        print(f"Error: Folder '{folder_path}' does not exist or is not a directory.")
        sys.exit(1)

    images = find_image_files(folder_path)
    total_images = len(images)
    folder_name = folder_path.name
    print(f"Found {total_images} images in folder '{folder_name}'.")

    if total_images == 0:
        print("No valid image files (JPG, PNG, BMP) found in folder.")
        sys.exit(0)

    # Chunk into batches of up to 50 files
    chunk_size = 50
    chunks = [images[i : i + chunk_size] for i in range(0, total_images, chunk_size)]
    total_batches = len(chunks)
    print(f"Splitting into {total_batches} batch(es) of up to {chunk_size} images each...")

    batch_ids: List[str] = []
    processed_count = 0

    for batch_idx, chunk in enumerate(chunks, 1):
        print(f"\n[Batch {batch_idx}/{total_batches}] Submitting {len(chunk)} images...")
        submit_res = post_batch(
            api_url=args.api,
            files=chunk,
            conf=args.conf,
            iou=args.iou,
            imgsz=args.imgsz,
            classify_crops=args.classify_crops,
        )
        b_id = submit_res["batch_id"]
        batch_ids.append(b_id)
        print(f"[Batch {batch_idx}/{total_batches}] Batch ID: {b_id} (processing)")

        # Poll status
        final_status = poll_status(args.api, b_id)
        processed_in_batch = final_status.get("processed", len(chunk))
        processed_count += processed_in_batch
        status_label = final_status.get("status", "done")

        print(
            f"Progress: batch {batch_idx}/{total_batches}, {processed_count}/{total_images} images ({status_label})"
        )

    # Download combined report ZIP
    out_dir = Path(args.output).resolve()
    zip_dest = out_dir / f"circuit_sight_{folder_name}_report.zip"
    print(f"\nDownloading consolidated ZIP report archive...")
    download_zip(args.api, batch_ids, zip_dest)
    print(f"Inspection report ZIP successfully saved to: {zip_dest}")
    print("Done!")


if __name__ == "__main__":
    main()
