"""
CircuitSight - End-to-End Test Suite for Frontend & Backend Integration
Tests:
1. 10 images batch from backend/data/test_10_images:
   - status polling
   - results format & defect counts
   - ZIP download containing 10 annotated images + report.csv
2. 120 images batch from backend/data/yolo_dataset/images/test:
   - Chunking into 3 batches (50, 50, 20)
   - Combined progress tracking
   - Combined ZIP archive via /api/batch/zip?ids=a,b,c
3. Low-resolution Google board images (619x323 and 471x424):
   - Verifies warning: low resolution alert is generated
"""

import time
import zipfile
import io
from pathlib import Path
import requests

BASE_URL = "http://127.0.0.1:8000/api"

def test_10_images():
    print("\n==================== TEST 1: 10-IMAGE BATCH ====================")
    test_dir = Path("d:/CircuitSight/backend/data/test_10_images")
    image_files = sorted(list(test_dir.glob("*.jpg")) + list(test_dir.glob("*.png")))[:10]
    print(f"Found {len(image_files)} test images in {test_dir.name}")
    assert len(image_files) == 10, f"Expected 10 images, got {len(image_files)}"

    files = [("files", (f.name, open(f, "rb"), "image/jpeg")) for f in image_files]
    res = requests.post(f"{BASE_URL}/batch", files=files)
    assert res.status_code == 200, f"Submit failed: {res.text}"
    batch_id = res.json()["batch_id"]
    print(f"Batch submitted successfully: batch_id = {batch_id}")

    # Poll status
    while True:
        s_res = requests.get(f"{BASE_URL}/batch/{batch_id}/status")
        assert s_res.status_code == 200
        st = s_res.json()
        print(f"Status: {st['status']} ({st['processed']}/{st['total']} images processed)")
        if st["status"] in ("done", "failed"):
            break
        time.sleep(0.5)

    assert st["status"] == "done"
    print("Batch processing complete.")

    # Results
    r_res = requests.get(f"{BASE_URL}/batch/{batch_id}/results")
    assert r_res.status_code == 200
    results = r_res.json()
    assert results["total"] == 10
    print(f"Results summary: Total: {results['total']}, Total Defects: {results['total_defects']}")
    print(f"Per-class breakdown: {results['per_class_counts']}")

    # ZIP download
    z_res = requests.get(f"{BASE_URL}/batch/{batch_id}/zip")
    assert z_res.status_code == 200
    zip_bytes = io.BytesIO(z_res.content)
    with zipfile.ZipFile(zip_bytes, "r") as zf:
        namelist = zf.namelist()
        print(f"ZIP contents ({len(namelist)} files):")
        for name in namelist[:6]:
            print(f"  - {name}")
        if len(namelist) > 6:
            print(f"  ... and {len(namelist)-6} more")
        assert "report.csv" in namelist, "report.csv missing from ZIP!"
        assert "report.json" in namelist, "report.json missing from ZIP!"
        img_count = sum(1 for n in namelist if n.endswith(".jpg"))
        assert img_count == 10, f"Expected 10 annotated images in ZIP, got {img_count}"
        print(f"Verified: ZIP contains {img_count} annotated images, report.csv, and report.json.")

    return batch_id

def test_google_board_warnings():
    print("\n==================== TEST 2: LOW-RESOLUTION GOOGLE BOARD IMAGES ====================")
    gb_dir = Path("d:/CircuitSight/backend/data/google_board_test")
    gb_files = sorted(list(gb_dir.glob("*.jpg")))
    print(f"Testing {len(gb_files)} Google board images: {[f.name for f in gb_files]}")

    files = [("files", (f.name, open(f, "rb"), "image/jpeg")) for f in gb_files]
    res = requests.post(f"{BASE_URL}/batch", files=files)
    assert res.status_code == 200, f"Submit failed: {res.text}"
    batch_id = res.json()["batch_id"]

    # Poll status
    while True:
        s_res = requests.get(f"{BASE_URL}/batch/{batch_id}/status")
        st = s_res.json()
        if st["status"] in ("done", "failed"):
            break
        time.sleep(0.5)

    assert st["status"] == "done"

    # Check results for warning
    r_res = requests.get(f"{BASE_URL}/batch/{batch_id}/results")
    assert r_res.status_code == 200
    results = r_res.json()
    for img in results["images"]:
        warning = img.get("warning")
        w = img.get("width") or img.get("image_width")
        h = img.get("height") or img.get("image_height")
        print(f"Image {img['filename']} ({w}x{h}): Warning = '{warning}'")
        assert warning is not None and ("low-resolution" in warning.lower() or "low resolution" in warning.lower()), f"Expected low resolution warning for {img['filename']}"
    print("Verified: Low-resolution warnings correctly attached to both board images.")

def test_120_images_chunking():
    print("\n==================== TEST 3: 120-IMAGE CHUNKING (3 BATCHES) ====================")
    test_dir = Path("d:/CircuitSight/backend/data/yolo_dataset/images/test")
    all_files = sorted(list(test_dir.glob("*.jpg")) + list(test_dir.glob("*.png")))[:120]
    total_count = len(all_files)
    print(f"Total images to process: {total_count}")
    assert total_count == 120, f"Expected 120 images, got {total_count}"

    chunk_size = 50
    chunks = [all_files[i:i + chunk_size] for i in range(0, total_count, chunk_size)]
    print(f"Auto-split into {len(chunks)} chunks: {[len(c) for c in chunks]} images")

    batch_ids = []
    processed_total = 0
    all_results = []

    for idx, chunk in enumerate(chunks):
        batch_num = idx + 1
        print(f"\nSubmitting Batch Chunk {batch_num}/{len(chunks)} ({len(chunk)} images)...")
        files = [("files", (f.name, open(f, "rb"), "image/jpeg")) for f in chunk]
        res = requests.post(f"{BASE_URL}/batch", files=files)
        assert res.status_code == 200, f"Submit failed: {res.text}"
        batch_id = res.json()["batch_id"]
        batch_ids.append(batch_id)

        # Monitor progress as frontend does
        while True:
            s_res = requests.get(f"{BASE_URL}/batch/{batch_id}/status")
            st = s_res.json()
            cur_processed = processed_total + st["processed"]
            print(f"  Combined Progress: batch {batch_num}/{len(chunks)}, {cur_processed}/{total_count} images")
            if st["status"] in ("done", "failed"):
                processed_total += st["processed"]
                break
            time.sleep(0.8)

        # Get results
        r_res = requests.get(f"{BASE_URL}/batch/{batch_id}/results")
        b_res = r_res.json()
        all_results.extend(b_res["images"])

    print(f"\nAll 3 batches complete! Total images gathered in merged gallery: {len(all_results)}")
    assert len(all_results) == 120

    # Test Combined ZIP endpoint: GET /api/batch/zip?ids=id1,id2,id3
    ids_param = ",".join(batch_ids)
    print(f"\nTesting Combined ZIP download from /api/batch/zip?ids={ids_param}...")
    zip_res = requests.get(f"{BASE_URL}/batch/zip?ids={ids_param}")
    assert zip_res.status_code == 200
    zip_bytes = io.BytesIO(zip_res.content)
    with zipfile.ZipFile(zip_bytes, "r") as zf:
        namelist = zf.namelist()
        img_count = sum(1 for n in namelist if n.endswith(".jpg"))
        print(f"Combined ZIP contains {len(namelist)} total files, including {img_count} annotated images.")
        assert img_count == 120, f"Expected 120 annotated images in combined ZIP, got {img_count}"
        assert "report.csv" in namelist
        assert "report.json" in namelist
        assert "README.txt" in namelist
    print("Verified: Combined ZIP archive successfully created and validated for 120 images across 3 batches.")

if __name__ == "__main__":
    t0 = time.time()
    test_10_images()
    test_google_board_warnings()
    test_120_images_chunking()
    print(f"\n>>> ALL END-TO-END INTEGRATION TESTS PASSED in {time.time()-t0:.2f}s! <<<")
