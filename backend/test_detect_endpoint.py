"""
Test Suite for YOLOv8 Detection Endpoint (/api/detect) and Refactored Backend in CircuitSight.
"""

import base64
import io
import sys
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

# Ensure backend directory is in sys.path
backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from main import app


def run_tests():
    print("=" * 60)
    print("CircuitSight Refactored Detector-First Test Suite")
    print("=" * 60)

    # Use context manager to trigger lifespan startup and shutdown
    with TestClient(app) as client:
        # 1. Print all registered routes
        print("\n[Registered Routes]")
        for r in app.routes:
            if hasattr(r, "methods"):
                print(f"  {','.join(r.methods):12} {r.path}")
            elif hasattr(r, "include_context"):
                ctx = r.include_context
                for sr in ctx.included_router.routes:
                    if hasattr(sr, "methods"):
                        print(f"  {','.join(sr.methods):12} {ctx.prefix}{sr.path}")

        # 2. Verify /api/health includes detector status & classifier status
        print("\n[Test 1] Checking GET /api/health...")
        health_resp = client.get("/api/health")
        assert health_resp.status_code == 200, f"Expected 200, got {health_resp.status_code}: {health_resp.text}"
        health_data = health_resp.json()
        print(f"Health Response Status: {health_data['status']}")
        print(f"Primary Model: {health_data.get('active_model')}")
        print(f"Detector Status: {health_data.get('detector')}")
        print(f"Classifier Status: {health_data.get('classifier')}")

        assert "detector" in health_data, "Health response missing 'detector' key"
        det_info = health_data["detector"]
        assert det_info["loaded"] is True, f"Expected detector.loaded == True, got {det_info['loaded']}"
        assert "yolov8_pcb_best.pt" in det_info["model_path"], f"Unexpected model path: {det_info['model_path']}"
        assert "missing_hole" in det_info["classes"], f"Missing class in {det_info['classes']}"

        assert "classifier" in health_data, "Health response missing 'classifier' key"
        clf_info = health_data["classifier"]
        assert clf_info["model_name"] == "efficientnet_b0"
        print("PASS: /api/health returned valid detector and classifier metadata.")

        # 3. Confirm removed endpoints return 404 Not Found
        print("\n[Test 2] Confirming removed endpoints return 404...")
        removed_endpoints = [
            ("POST", "/api/predict"),
            ("POST", "/api/predict/json"),
            ("POST", "/api/predict/batch"),
            ("GET", "/api/models"),
            ("POST", "/api/models/active"),
            ("GET", "/api/models/benchmarks"),
        ]
        for method, endpoint in removed_endpoints:
            if method == "POST":
                r = client.post(endpoint, json={})
            else:
                r = client.get(endpoint)
            print(f"  {method} {endpoint} -> {r.status_code}")
            assert r.status_code == 404, f"Expected 404 for removed endpoint {endpoint}, got {r.status_code}"
        print("PASS: All removed routes return 404 Not Found.")

        # 4. Verify Swagger /openapi.json tags
        print("\n[Test 3] Verifying OpenAPI documentation tags...")
        openapi_resp = client.get("/openapi.json")
        assert openapi_resp.status_code == 200
        openapi_data = openapi_resp.json()
        assert openapi_data["info"]["title"] == "CircuitSight PCB Defect Detection API (YOLOv8 + EfficientNet-B0)"

        used_tags = set()
        for path_item in openapi_data.get("paths", {}).values():
            for operation in path_item.values():
                if isinstance(operation, dict) and "tags" in operation:
                    used_tags.update(operation["tags"])
        print(f"OpenAPI Documentation Tags: {sorted(list(used_tags))}")
        assert used_tags == {"Detection", "Defects", "Health"}, f"Unexpected tags in docs: {used_tags}"
        print("PASS: Swagger documentation lists exclusively Detection, Defects, Health.")

        # Load sample image bytes
        test_img_path = backend_dir / "dataset" / "PCB_DATASET" / "images" / "Missing_hole" / "01_missing_hole_01.jpg"
        assert test_img_path.exists(), f"Sample test image not found at: {test_img_path}"
        with open(test_img_path, "rb") as f:
            img_bytes = f.read()

        # 5. Test no params -> 200 with defaults applied
        print("\n[Test 4] POST /api/detect with NO optional params (Expect 200 with defaults)...")
        resp_no_params = client.post(
            "/api/detect",
            files={"file": (test_img_path.name, img_bytes, "image/jpeg")},
        )
        assert resp_no_params.status_code == 200, f"Expected 200, got {resp_no_params.status_code}: {resp_no_params.text}"
        data_no_params = resp_no_params.json()
        print(f"Settings Used (No params): {data_no_params.get('settings_used')}")
        assert data_no_params.get("settings_used") == {"conf": 0.25, "iou": 0.45, "imgsz": 1024}
        assert data_no_params["total_defects"] >= 1
        print("PASS: No params applied defaults (conf=0.25, iou=0.45, imgsz=1024).")

        # 6. Test conf=0 (and iou=0, imgsz=0 like Swagger placeholder) -> 200 with defaults applied
        print("\n[Test 5] POST /api/detect with conf=0, iou=0, imgsz=0 (Swagger UI placeholders)...")
        resp_zero = client.post(
            "/api/detect",
            files={"file": (test_img_path.name, img_bytes, "image/jpeg")},
            data={"conf": "0", "iou": "0", "imgsz": "0"},
        )
        assert resp_zero.status_code == 200, f"Expected 200, got {resp_zero.status_code}: {resp_zero.text}"
        data_zero = resp_zero.json()
        print(f"Settings Used (Zeros passed): {data_zero.get('settings_used')}")
        assert data_zero.get("settings_used") == {"conf": 0.25, "iou": 0.45, "imgsz": 1024}
        assert data_zero["total_defects"] >= 1
        print("PASS: Placeholder 0 values successfully fallback to defaults.")

        # 7. Test conf=1.5 -> 400 Bad Request
        print("\n[Test 6] POST /api/detect with conf=1.5 (Expect 400 Bad Request)...")
        resp_over = client.post(
            "/api/detect",
            files={"file": (test_img_path.name, img_bytes, "image/jpeg")},
            data={"conf": "1.5"},
        )
        print(f"Response status (conf=1.5): {resp_over.status_code}, detail: {resp_over.text}")
        assert resp_over.status_code == 400, f"Expected 400, got {resp_over.status_code}"
        print("PASS: conf=1.5 properly rejected with HTTP 400.")

        # 8. Test conf=0.99 -> 200 with 0 detections and warning present
        print("\n[Test 7] POST /api/detect with conf=0.99 (Expect 0 detections and warning)...")
        resp_high_conf = client.post(
            "/api/detect",
            files={"file": (test_img_path.name, img_bytes, "image/jpeg")},
            data={"conf": "0.99"},
        )
        assert resp_high_conf.status_code == 200, f"Expected 200, got {resp_high_conf.status_code}: {resp_high_conf.text}"
        data_high_conf = resp_high_conf.json()

        print(f"Total Defects (conf=0.99): {data_high_conf.get('total_defects')}")
        print(f"Warning Message: {data_high_conf.get('warning')}")
        assert data_high_conf["total_defects"] == 0, f"Expected 0 defects, got {data_high_conf['total_defects']}"
        assert len(data_high_conf["detections"]) == 0
        assert data_high_conf.get("warning") is not None, "Expected warning field to be present"
        expected_warning = "No defects detected above the confidence threshold. This is not a guarantee the board is defect-free."
        assert expected_warning in data_high_conf["warning"], f"Expected '{expected_warning}' in warning '{data_high_conf.get('warning')}'"
        assert data_high_conf["settings_used"]["conf"] == 0.99
        print("PASS: conf=0.99 returned 200 with 0 detections, warning, and settings_used.")

        # 9. Test classify_crops=True -> detections contain classifier_class and classifier_confidence
        print("\n[Test 8] POST /api/detect with classify_crops=true...")
        resp_crops = client.post(
            "/api/detect",
            files={"file": (test_img_path.name, img_bytes, "image/jpeg")},
            data={"conf": "0.25", "classify_crops": "true"},
        )
        assert resp_crops.status_code == 200, f"Expected 200, got {resp_crops.status_code}: {resp_crops.text}"
        data_crops = resp_crops.json()

        assert data_crops["total_defects"] >= 1, "Expected detections with classify_crops=true"
        for idx, det in enumerate(data_crops["detections"]):
            c_class = det.get("classifier_class")
            c_conf = det.get("classifier_confidence")
            print(f"Detection #{idx+1}: YOLO '{det['class_name']}' ({det['confidence']}) -> Classifier '{c_class}' ({c_conf})")
            assert c_class is not None, f"Expected classifier_class for detection #{idx+1}"
            assert c_conf is not None and c_conf > 0.0, f"Expected valid classifier_confidence for detection #{idx+1}"
        print("PASS: classify_crops populated classifier_class and classifier_confidence.")

        # 10. Test include_annotated_image=True -> base64 decodes to valid PNG
        print("\n[Test 9] POST /api/detect with include_annotated_image=true...")
        resp_annot = client.post(
            "/api/detect",
            files={"file": (test_img_path.name, img_bytes, "image/jpeg")},
            data={"conf": "0.25", "include_annotated_image": "true"},
        )
        assert resp_annot.status_code == 200, f"Expected 200, got {resp_annot.status_code}: {resp_annot.text}"
        data_annot = resp_annot.json()

        b64_img = data_annot.get("annotated_image_base64")
        assert b64_img is not None, "Expected annotated_image_base64 to be returned"
        png_bytes = base64.b64decode(b64_img)
        assert png_bytes[:8] == b"\x89PNG\r\n\x1a\n", "Decoded data does not have valid PNG header"
        annot_pil = Image.open(io.BytesIO(png_bytes))
        assert annot_pil.format == "PNG", f"Expected PNG format, got {annot_pil.format}"
        print(f"Annotated Image PNG verified! Dimensions: {annot_pil.size}, Bytes: {len(png_bytes)}")
        print("PASS: Annotated image successfully decoded to a valid PNG.")

        # 11. Test text file upload -> 400
        print("\n[Test 10] POST /api/detect with non-image text file (Expect 400)...")
        resp_text = client.post(
            "/api/detect",
            files={"file": ("log.txt", b"This is a text log, not a PCB board image.", "text/plain")},
        )
        print(f"Text file upload status code: {resp_text.status_code}, response: {resp_text.text}")
        assert resp_text.status_code == 400, f"Expected 400, got {resp_text.status_code}"
        print("PASS: Non-image file correctly rejected with HTTP 400.")

        # 12. Test low-resolution image warning (<800px on longest side)
        print("\n[Test 11] POST /api/detect with low-resolution image (Expect low-res warning)...")
        low_res_img = Image.new("RGB", (320, 240), color=(100, 150, 200))
        buf = io.BytesIO()
        low_res_img.save(buf, format="JPEG")
        low_res_bytes = buf.getvalue()

        resp_low_res = client.post(
            "/api/detect",
            files={"file": ("tiny_board.jpg", low_res_bytes, "image/jpeg")},
        )
        assert resp_low_res.status_code == 200
        data_low_res = resp_low_res.json()
        print(f"Low-Res Warning: {data_low_res.get('warning')}")
        assert data_low_res.get("warning") is not None
        expected_low_res_warning = "Low-resolution input. Detector was trained on ~3000px board photos, so results may be unreliable."
        assert expected_low_res_warning in data_low_res["warning"]
        print("PASS: Low-resolution image triggered the expected resolution warning.")

        # 13. Test defect catalog endpoints
        print("\n[Test 12] Testing defect catalog endpoints...")
        defects_list_resp = client.get("/api/defects")
        assert defects_list_resp.status_code == 200
        defects_list = defects_list_resp.json()
        assert len(defects_list) == 6, f"Expected 6 defect classes, got {len(defects_list)}"

        single_defect_resp = client.get("/api/defects/missing_hole")
        assert single_defect_resp.status_code == 200
        assert single_defect_resp.json()["class_id"] == "missing_hole"
        print("PASS: Defect catalog endpoints operational.")

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED SUCCESSFULLY!")
    print("=" * 60)


if __name__ == "__main__":
    run_tests()
