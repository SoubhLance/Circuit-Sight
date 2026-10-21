"""
Comprehensive Test Suite for CircuitSight Batch Detection Endpoint (/api/batch)
Tests:
1. Batch submission with 5 test images from backend/data/yolo_dataset/images/test.
2. Polling status until 'done'.
3. Retrieval and schema validation of batch results JSON.
4. Retrieval and verification of full annotated image and 480px thumbnail (valid JPEG).
5. Download and verification of streaming ZIP archive (annotated files, report.csv, report.json, README.txt).
6. Security: Zip entry names contain no '..', '\', or illegal path separators; zip-slip prevention.
7. Rejection of > 50 files with HTTP 400.
8. Rejection of .txt file renamed to .jpg (PIL verification failure) with HTTP 400.
9. Handling of duplicate filenames with automatic deduplication (_1, _2 suffix).
10. DELETE /api/batch/{batch_id} cleanup endpoint.
11. GET /api/health verification including Batch health diagnostics.
"""

import io
import sys
import time
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

# Ensure backend directory is in sys.path
backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from main import app
from api.batch_manager import batch_manager


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as test_client:
        yield test_client


def get_5_test_images():
    test_dir = backend_dir / "data" / "yolo_dataset" / "images" / "test"
    assert test_dir.exists(), f"Test images directory not found: {test_dir}"
    jpg_files = sorted(list(test_dir.glob("*.jpg")))
    assert len(jpg_files) >= 5, f"Expected at least 5 images in {test_dir}, found {len(jpg_files)}"
    return jpg_files[:5]


def test_batch_e2e_flow(client):
    """
    Upload 5 real test images, poll until completion, verify results,
    inspect annotated image and thumbnail, download and validate zip archive.
    """
    image_paths = get_5_test_images()
    files_payload = []
    file_handles = []

    try:
        for p in image_paths:
            fh = open(p, "rb")
            file_handles.append(fh)
            files_payload.append(("files", (p.name, fh.read(), "image/jpeg")))

        # 1. Submit batch
        submit_resp = client.post(
            "/api/batch",
            files=files_payload,
            data={"conf": "0.25", "iou": "0.45", "imgsz": "1024"},
        )
        assert submit_resp.status_code == 200, f"Submit failed: {submit_resp.text}"
        submit_data = submit_resp.json()
        assert "batch_id" in submit_data
        batch_id = submit_data["batch_id"]
        assert submit_data["total"] == 5
        assert submit_data["status"] == "processing"

        # 2. Poll status until done
        max_attempts = 60
        status_data = None
        for _ in range(max_attempts):
            poll_resp = client.get(f"/api/batch/{batch_id}/status")
            assert poll_resp.status_code == 200
            status_data = poll_resp.json()
            if status_data["status"] in ("done", "failed"):
                break
            time.sleep(1.0)

        assert status_data is not None
        assert status_data["status"] == "done", f"Batch ended in unexpected status: {status_data}"
        assert status_data["processed"] == 5
        assert status_data["total"] == 5

        # 3. Fetch results
        results_resp = client.get(f"/api/batch/{batch_id}/results")
        assert results_resp.status_code == 200
        results = results_resp.json()
        assert results["batch_id"] == batch_id
        assert results["status"] == "done"
        assert results["processed"] == 5
        assert len(results["images"]) == 5
        assert "images_with_detections" in results
        assert "images_without_detections" in results
        assert "total_defects" in results
        assert "per_class_counts" in results

        # Verify wording rule: No occurrences of "clean" or "OK" as board assessment
        assert "clean" not in str(results).lower()
        assert " ok " not in f" {str(results).lower()} "

        # Check per-image fields
        first_img = results["images"][0]
        assert first_img["index"] == 0
        assert first_img["filename"].endswith(".jpg")
        assert first_img["width"] > 0
        assert first_img["height"] > 0
        assert first_img["thumb_url"] == f"/api/batch/{batch_id}/thumb/0"
        assert first_img["image_url"] == f"/api/batch/{batch_id}/image/0"

        # 4. Fetch full annotated JPEG and verify quality & format
        img_resp = client.get(f"/api/batch/{batch_id}/image/0")
        assert img_resp.status_code == 200
        assert img_resp.headers["content-type"] == "image/jpeg"
        full_pil = Image.open(io.BytesIO(img_resp.content))
        assert full_pil.format == "JPEG"
        assert full_pil.size == (first_img["width"], first_img["height"])

        # Fetch thumbnail and verify width == 480px
        thumb_resp = client.get(f"/api/batch/{batch_id}/thumb/0")
        assert thumb_resp.status_code == 200
        assert thumb_resp.headers["content-type"] == "image/jpeg"
        thumb_pil = Image.open(io.BytesIO(thumb_resp.content))
        assert thumb_pil.format == "JPEG"
        assert thumb_pil.size[0] == 480

        # 5. Fetch ZIP report
        zip_resp = client.get(f"/api/batch/{batch_id}/zip")
        assert zip_resp.status_code == 200
        assert zip_resp.headers["content-type"] == "application/zip"

        with zipfile.ZipFile(io.BytesIO(zip_resp.content), "r") as zf:
            namelist = zf.namelist()

            # Verify required files in zip
            assert "README.txt" in namelist
            assert "report.csv" in namelist
            assert "report.json" in namelist

            # Check annotated directory in zip
            annotated_entries = [name for name in namelist if name.startswith("annotated/")]
            assert len(annotated_entries) == 5

            # Security: verify entries contain no '..', '\', or root '/'
            for name in namelist:
                assert ".." not in name, f"Zip-slip vulnerability in entry: {name}"
                assert "\\" not in name, f"Backslash found in zip entry: {name}"
                assert not name.startswith("/"), f"Root path found in zip entry: {name}"
                if "/" in name:
                    assert name.startswith("annotated/"), f"Unexpected subdirectory in zip: {name}"
                    # No secondary subdirectory
                    assert "/" not in name[len("annotated/"):], f"Nested directory found: {name}"

            # Verify README.txt wording requirement
            readme_text = zf.read("README.txt").decode("utf-8")
            assert "No defects detected above the confidence threshold" in readme_text
            assert "clean" not in readme_text.lower()
            assert " ok " not in f" {readme_text.lower()} "

            # Verify report.csv header and row count
            csv_text = zf.read("report.csv").decode("utf-8")
            csv_lines = [line.strip() for line in csv_text.splitlines() if line.strip()]
            assert len(csv_lines) == 6  # Header + 5 images
            header = csv_lines[0].split(",")
            assert "filename" in header
            assert "total_defects" in header
            assert "max_confidence" in header

        # 6. Test manual DELETE
        del_resp = client.delete(f"/api/batch/{batch_id}")
        assert del_resp.status_code == 200
        del_data = del_resp.json()
        assert del_data["batch_id"] == batch_id
        assert del_data["deleted"] is True

        # Subsequent GET should return 404
        assert client.get(f"/api/batch/{batch_id}/status").status_code == 404

    finally:
        for fh in file_handles:
            try:
                fh.close()
            except Exception:
                pass


def test_reject_more_than_50_files(client):
    """Batch size limit: upload 51 files and verify HTTP 400."""
    small_img = Image.new("RGB", (64, 64), color="red")
    buf = io.BytesIO()
    small_img.save(buf, format="JPEG")
    img_bytes = buf.getvalue()

    files = [("files", (f"board_{i}.jpg", img_bytes, "image/jpeg")) for i in range(51)]
    resp = client.post("/api/batch", files=files)
    assert resp.status_code == 400
    detail = resp.json().get("detail", "")
    assert "50" in detail
    assert "exceeds" in detail.lower()


def test_reject_fake_jpg_text_file(client):
    """Content verification: a text file renamed to .jpg is rejected with 400."""
    fake_content = b"This is plain text with a fraudulent .jpg extension."
    files = [("files", ("fraudulent.jpg", fake_content, "image/jpeg"))]
    resp = client.post("/api/batch", files=files)
    assert resp.status_code == 400
    detail = resp.json().get("detail", "")
    assert "fraudulent.jpg" in detail
    assert "Invalid or unparseable image content" in detail or "valid" in detail.lower()


def test_duplicate_filenames_deduplicated(client):
    """Duplicate filenames in a batch are safely deduplicated (_1, _2 suffix)."""
    image_paths = get_5_test_images()
    with open(image_paths[0], "rb") as f:
        img_bytes = f.read()

    # Upload two files with the exact same name
    files = [
        ("files", ("circuit_board.jpg", img_bytes, "image/jpeg")),
        ("files", ("circuit_board.jpg", img_bytes, "image/jpeg")),
    ]
    resp = client.post("/api/batch", files=files)
    assert resp.status_code == 200
    batch_id = resp.json()["batch_id"]

    # Wait for completion
    for _ in range(30):
        st = client.get(f"/api/batch/{batch_id}/status").json()
        if st["status"] in ("done", "failed"):
            break
        time.sleep(1.0)

    res = client.get(f"/api/batch/{batch_id}/results").json()
    filenames = [item["filename"] for item in res["images"]]
    assert len(filenames) == 2
    assert filenames[0] != filenames[1]
    assert filenames[0] == "circuit_board.jpg"
    assert filenames[1] == "circuit_board_1.jpg"

    # Cleanup
    client.delete(f"/api/batch/{batch_id}")


def test_openapi_spec_format_binary_and_note(client):
    """Verify OpenAPI schema shows items with type: string and format: binary, plus the swagger note."""
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    data = resp.json()
    post_batch_op = data["paths"]["/api/batch"]["post"]

    # Check note in description
    description = post_batch_op.get("description", "")
    assert "Swagger UI cannot multi-select; use the web app or scripts/batch_folder.py for folders." in description

    # Check requestBody schema for files array
    body_schema = data["components"]["schemas"]["Body_submit_batch_api_batch_post"]
    files_prop = body_schema["properties"]["files"]
    assert files_prop["type"] == "array"
    assert files_prop["items"]["type"] == "string"
    assert files_prop["items"]["format"] == "binary"


def test_combined_zip_endpoint(client):
    """Verify GET /api/batch/zip?ids=... downloads valid combined zip report."""
    image_paths = get_5_test_images()
    with open(image_paths[0], "rb") as f:
        img_bytes = f.read()

    files = [("files", ("board_a.jpg", img_bytes, "image/jpeg"))]
    resp = client.post("/api/batch", files=files)
    assert resp.status_code == 200
    b_id = resp.json()["batch_id"]

    for _ in range(30):
        st = client.get(f"/api/batch/{b_id}/status").json()
        if st["status"] in ("done", "failed"):
            break
        time.sleep(0.5)

    # Call combined zip endpoint
    zip_resp = client.get(f"/api/batch/zip?ids={b_id}")
    assert zip_resp.status_code == 200
    assert zip_resp.headers["content-type"] == "application/zip"

    with zipfile.ZipFile(io.BytesIO(zip_resp.content), "r") as zf:
        names = zf.namelist()
        assert "README.txt" in names
        assert "report.csv" in names
        assert "report.json" in names
        assert any(n.startswith("annotated/") for n in names)

    # Cleanup
    client.delete(f"/api/batch/{b_id}")


def test_health_includes_batch(client):
    """Verify /api/health endpoint includes batch manager status and capacity."""
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "batch" in data
    batch_info = data["batch"]
    assert "active_batches" in batch_info
    assert batch_info["max_concurrent_batches"] == 2
    assert "storage_dir" in batch_info


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

