"""
CircuitSight - PCB Defect Prediction Engine
Loads trained model checkpoints (default: EfficientNet-B0) to classify PCB defects.

Supported Defect Classes:
    0: missing_hole
    1: mouse_bite
    2: open_circuit
    3: short
    4: spur
    5: spurious_copper
"""

import os
import io
import time
import base64
import argparse
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union, Any

import numpy as np
from PIL import Image
import torch
import torch.nn as nn
from torchvision import models, transforms
import cv2


# Defect Classes matching the training dataset
CLASSES = [
    "missing_hole",
    "mouse_bite",
    "open_circuit",
    "short",
    "spur",
    "spurious_copper",
]

CLASS_TO_IDX = {cls_name: i for i, cls_name in enumerate(CLASSES)}
IDX_TO_CLASS = {i: cls_name for i, cls_name in enumerate(CLASSES)}

# Rich industrial domain metadata for PCB quality assurance
DEFECT_CATALOG: Dict[str, Dict[str, str]] = {
    "missing_hole": {
        "name": "Missing Hole / Missing Via",
        "severity": "High",
        "description": "A required drilled component lead hole or conductive through-hole via is absent on the PCB.",
        "risk": "Component pins cannot be inserted; electrical layer-to-layer connectivity is broken.",
        "remediation": "Check drill CNC program and drill bit breakage detection. Re-drill if board unplated, or scrap board.",
    },
    "mouse_bite": {
        "name": "Mouse Bite",
        "severity": "Medium",
        "description": "A ragged bite-like erosion along the edge of a conductor trace or board border margin.",
        "risk": "Weakens trace mechanical strength; localized impedance changes and potential for trace burning under high current.",
        "remediation": "Inspect photoresist adhesion and chemical etching rate uniformity. Check router routing parameters.",
    },
    "open_circuit": {
        "name": "Open Circuit",
        "severity": "Critical",
        "description": "A complete physical break in a conductive copper trace causing a loss of electrical continuity.",
        "risk": "Complete signal interruption or unpowered circuitry; device failure in field.",
        "remediation": "Micro-welding / jumper wire repair for prototype units. For production, inspect photolithography mask dust and etching bath.",
    },
    "short": {
        "name": "Short Circuit",
        "severity": "Critical",
        "description": "An accidental conductive bridge connecting two or more distinct copper traces or pads.",
        "risk": "Excessive current flow, thermal breakdown, power rail shutdown, component burnout.",
        "remediation": "Mechanical or laser de-bridging if accessible. Audit exposure alignment and developer residue.",
    },
    "spur": {
        "name": "Spur",
        "severity": "Medium",
        "description": "A sharp, unwanted copper protrusion extending outwards from a trace without fully bridging.",
        "risk": "Reduces dielectric creepage distance; susceptible to electrical arcing and high-frequency capacitive crosstalk.",
        "remediation": "Examine optical artwork clarity and rinse stage chemistry after etching.",
    },
    "spurious_copper": {
        "name": "Spurious Copper",
        "severity": "Low-Medium",
        "description": "Isolated islands or specks of un-etched residual copper residing on dielectric board substrate.",
        "risk": "Can detach under vibration causing intermittent shorts, or induce stray capacitance.",
        "remediation": "Optimize copper etching bath temperature and agitation; inspect laminator cleanliness.",
    },
}


def crop_box(
    xmin: int,
    ymin: int,
    xmax: int,
    ymax: int,
    width: int,
    height: int,
    scale: float = 2.5,
    min_crop: int = 64,
) -> Tuple[int, int, int, int]:
    """
    Square crop around bounding box preserving context, clamped within image boundaries.
    Matches the bounding box extraction logic from build_dataset.py.
    """
    cx = (xmin + xmax) / 2.0
    cy = (ymin + ymax) / 2.0
    box_w = xmax - xmin
    box_h = ymax - ymin
    side = max(max(box_w, box_h) * scale, min_crop)
    side = min(side, width, height)
    left = min(max(cx - side / 2.0, 0), width - side)
    top = min(max(cy - side / 2.0, 0), height - side)
    return int(round(left)), int(round(top)), int(round(left + side)), int(round(top + side))


def build_model_architecture(
    architecture: str = "efficientnet_b0",
    num_classes: int = len(CLASSES),
) -> Tuple[nn.Module, Optional[nn.Module]]:
    """
    Constructs model backbone matching the training notebook specifications.
    Returns (model, target_layer_for_gradcam).
    """
    arch = architecture.lower()
    if "efficientnet" in arch:
        model = models.efficientnet_b0(weights=None)
        in_features = model.classifier[1].in_features
        model.classifier = nn.Sequential(
            nn.Dropout(p=0.3),
            nn.Linear(in_features, num_classes),
        )
        target_layer = model.features[-1]
    elif "mobilenet" in arch:
        model = models.mobilenet_v2(weights=None)
        in_features = model.classifier[1].in_features
        model.classifier = nn.Sequential(
            nn.Dropout(p=0.2),
            nn.Linear(in_features, num_classes),
        )
        target_layer = model.features[-1]
    elif "resnet" in arch:
        model = models.resnet50(weights=None)
        in_features = model.fc.in_features
        model.fc = nn.Linear(in_features, num_classes)
        target_layer = model.layer4[-1]
    else:
        raise ValueError(f"Unsupported architecture '{architecture}'. Use 'efficientnet_b0', 'mobilenetv2', or 'resnet50'.")

    return model, target_layer


class PCBPredictor:
    """
    Production-grade inference engine for PCB Defect Classification.
    """

    def __init__(
        self,
        model_path: Optional[Union[str, Path]] = None,
        architecture: str = "efficientnet_b0",
        device: Optional[str] = None,
        img_size: int = 224,
    ):
        # Resolve device
        if device is None:
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        else:
            self.device = torch.device(device)

        self.architecture = architecture
        self.img_size = img_size
        self.classes = CLASSES

        # Resolve model path
        if model_path is None:
            backend_dir = Path(__file__).resolve().parent
            default_path = backend_dir / "models" / "efficientnet_b0_best.pth"
            if not default_path.exists():
                # Try parent search
                alt_path = Path("backend/models/efficientnet_b0_best.pth")
                if alt_path.exists():
                    default_path = alt_path
            self.model_path = Path(default_path)
        else:
            self.model_path = Path(model_path)

        # Standard ImageNet eval transform used during training
        self.transform = transforms.Compose([
            transforms.Resize((self.img_size, self.img_size)),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225],
            ),
        ])

        # Load model and weights
        self.model, self.target_cam_layer = build_model_architecture(
            architecture=self.architecture,
            num_classes=len(self.classes),
        )

        self._load_checkpoint()
        self.model.to(self.device)
        self.model.eval()

    def _load_checkpoint(self) -> None:
        if not self.model_path.exists():
            raise FileNotFoundError(f"Model checkpoint not found at: {self.model_path.resolve()}")

        checkpoint = torch.load(self.model_path, map_location=self.device)
        if isinstance(checkpoint, dict) and "model_state_dict" in checkpoint:
            state_dict = checkpoint["model_state_dict"]
            if "classes" in checkpoint:
                self.classes = checkpoint["classes"]
            if "img_size" in checkpoint:
                self.img_size = checkpoint["img_size"]
            self.checkpoint_metadata = {
                "val_acc": checkpoint.get("val_acc"),
                "epoch": checkpoint.get("epoch"),
                "split_id": checkpoint.get("split_id"),
            }
        else:
            state_dict = checkpoint
            self.checkpoint_metadata = {}

        self.model.load_state_dict(state_dict)

    def load_image(
        self,
        image_input: Union[str, Path, bytes, io.BytesIO, Image.Image, np.ndarray],
    ) -> Image.Image:
        """
        Loads and standardizes input into an RGB PIL Image.
        """
        if isinstance(image_input, Image.Image):
            return image_input.convert("RGB")
        elif isinstance(image_input, (str, Path)):
            with open(image_input, "rb") as f:
                return Image.open(f).convert("RGB")
        elif isinstance(image_input, bytes):
            return Image.open(io.BytesIO(image_input)).convert("RGB")
        elif isinstance(image_input, io.BytesIO):
            return Image.open(image_input).convert("RGB")
        elif isinstance(image_input, np.ndarray):
            # Assume RGB or BGR
            if image_input.ndim == 3 and image_input.shape[2] == 3:
                return Image.fromarray(image_input).convert("RGB")
            elif image_input.ndim == 2:
                return Image.fromarray(image_input).convert("L").convert("RGB")
            else:
                raise ValueError(f"Unsupported numpy image shape: {image_input.shape}")
        else:
            raise TypeError(f"Unsupported image input type: {type(image_input)}")

    def preprocess(
        self,
        pil_image: Image.Image,
        bbox: Optional[Tuple[int, int, int, int]] = None,
    ) -> Tuple[torch.Tensor, Image.Image, Optional[Tuple[int, int, int, int]]]:
        """
        Preprocesses an image. If bbox=(xmin, ymin, xmax, ymax) is provided,
        crops the image context first.
        """
        crop_applied = None
        if bbox is not None:
            xmin, ymin, xmax, ymax = bbox
            W, H = pil_image.size
            crop_coords = crop_box(xmin, ymin, xmax, ymax, W, H)
            pil_image = pil_image.crop(crop_coords)
            crop_applied = crop_coords

        tensor = self.transform(pil_image)
        return tensor, pil_image, crop_applied

    def predict(
        self,
        image: Union[str, Path, bytes, io.BytesIO, Image.Image, np.ndarray],
        bbox: Optional[Tuple[int, int, int, int]] = None,
        top_k: int = 3,
        return_heatmap: bool = False,
    ) -> Dict[str, Any]:
        """
        Predict defect category on image or cropped ROI.
        """
        start_time = time.perf_counter()

        pil_image = self.load_image(image)
        tensor, processed_pil, crop_coords = self.preprocess(pil_image, bbox=bbox)
        batch_tensor = tensor.unsqueeze(0).to(self.device)

        with torch.no_grad():
            outputs = self.model(batch_tensor)
            probabilities = torch.softmax(outputs, dim=1)[0].cpu().numpy()

        pred_idx = int(np.argmax(probabilities))
        pred_class = self.classes[pred_idx]
        pred_confidence = float(probabilities[pred_idx])

        # Probabilities dictionary
        prob_dict = {
            self.classes[i]: round(float(prob), 5)
            for i, prob in enumerate(probabilities)
        }

        # Top-K predictions
        sorted_indices = np.argsort(probabilities)[::-1][:top_k]
        top_k_list = [
            {
                "class": self.classes[idx],
                "confidence": round(float(probabilities[idx]), 5),
                "rank": rank + 1,
            }
            for rank, idx in enumerate(sorted_indices)
        ]

        inference_time_ms = round((time.perf_counter() - start_time) * 1000.0, 2)

        # Defect catalog metadata
        catalog_info = DEFECT_CATALOG.get(
            pred_class,
            {
                "name": pred_class.replace("_", " ").title(),
                "severity": "Unknown",
                "description": "Defect classification.",
                "risk": "Requires inspection.",
                "remediation": "Standard PCB inspection procedure.",
            },
        )

        heatmap_b64 = None
        if return_heatmap and self.target_cam_layer is not None:
            try:
                heatmap_b64 = self.generate_gradcam(
                    batch_tensor=batch_tensor,
                    processed_pil=processed_pil,
                    target_class_idx=pred_idx,
                )
            except Exception as cam_err:
                heatmap_b64 = None

        return {
            "predicted_class": pred_class,
            "confidence": round(pred_confidence, 5),
            "defect_details": catalog_info,
            "probabilities": prob_dict,
            "top_k": top_k_list,
            "inference_time_ms": inference_time_ms,
            "model_name": self.architecture,
            "model_checkpoint": self.model_path.name,
            "device": str(self.device),
            "crop_coords": crop_coords,
            "heatmap_base64": heatmap_b64,
        }

    def predict_batch(
        self,
        images: List[Union[str, Path, bytes, io.BytesIO, Image.Image, np.ndarray]],
        top_k: int = 3,
    ) -> List[Dict[str, Any]]:
        """
        Batch prediction for multiple images.
        """
        results = []
        for img in images:
            res = self.predict(img, top_k=top_k, return_heatmap=False)
            results.append(res)
        return results

    def generate_gradcam(
        self,
        batch_tensor: torch.Tensor,
        processed_pil: Image.Image,
        target_class_idx: int,
    ) -> str:
        """
        Generates Grad-CAM visual heatmap overlaid on the inspected image patch,
        returning a base64 encoded PNG data URI string.
        """
        gradients = []
        activations = []

        def f_hook(module, inp, out):
            activations.append(out)

        def b_hook(module, grad_in, grad_out):
            gradients.append(grad_out[0])

        h1 = self.target_cam_layer.register_forward_hook(f_hook)
        h2 = self.target_cam_layer.register_full_backward_hook(b_hook)

        # Forward pass with gradient tracking
        tensor_var = batch_tensor.clone().requires_grad_(True)
        self.model.zero_grad()
        out = self.model(tensor_var)
        score = out[0, target_class_idx]
        score.backward()

        h1.remove()
        h2.remove()

        grads = gradients[0].detach()
        acts = activations[0].detach()

        # Channel weights via Global Average Pooling
        weights = torch.mean(grads, dim=(2, 3), keepdim=True)
        cam = torch.sum(weights * acts, dim=1).squeeze().cpu().numpy()
        cam = np.maximum(cam, 0)

        # Normalize 0..1
        if cam.max() > 0:
            cam = cam / (cam.max() + 1e-8)

        # Resize CAM to image size and apply colormap
        cam_resized = cv2.resize(cam, (self.img_size, self.img_size))
        heatmap = cv2.applyColorMap(np.uint8(255 * cam_resized), cv2.COLORMAP_JET)
        heatmap = cv2.cvtColor(heatmap, cv2.COLOR_BGR2RGB)

        # Overlay with original patch resized to img_size
        orig_resized = np.array(processed_pil.resize((self.img_size, self.img_size)))
        overlay = np.uint8(0.6 * orig_resized + 0.4 * heatmap)

        # Encode to PNG base64
        pil_overlay = Image.fromarray(overlay)
        buf = io.BytesIO()
        pil_overlay.save(buf, format="PNG")
        b64_str = base64.b64encode(buf.getvalue()).decode("utf-8")
        return f"data:image/png;base64,{b64_str}"


def main():
    """
    CLI command line interface for direct testing.
    """
    parser = argparse.ArgumentParser(description="CircuitSight PCB Defect Predictor")
    parser.add_argument("image", type=str, help="Path to PCB image file")
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Path to .pth checkpoint (default: backend/models/efficientnet_b0_best.pth)",
    )
    parser.add_argument(
        "--arch",
        type=str,
        default="efficientnet_b0",
        help="Model architecture ('efficientnet_b0', 'mobilenetv2', 'resnet50')",
    )
    parser.add_argument(
        "--device",
        type=str,
        default=None,
        help="Compute device ('cuda' or 'cpu')",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=3,
        help="Number of top predictions to display (default: 3)",
    )
    parser.add_argument(
        "--heatmap",
        action="store_true",
        help="Generate Grad-CAM activation heatmap",
    )
    parser.add_argument(
        "--bbox",
        type=int,
        nargs=4,
        metavar=("XMIN", "YMIN", "XMAX", "YMAX"),
        default=None,
        help="Bounding box coordinates to crop defect region",
    )

    args = parser.parse_args()

    predictor = PCBPredictor(
        model_path=args.model,
        architecture=args.arch,
        device=args.device,
    )

    bbox = tuple(args.bbox) if args.bbox else None
    result = predictor.predict(
        image=args.image,
        bbox=bbox,
        top_k=args.top_k,
        return_heatmap=args.heatmap,
    )

    print("=" * 60)
    print(" CircuitSight - PCB Defect Inspection Result")
    print("=" * 60)
    print(f"Image File       : {args.image}")
    print(f"Predicted Class  : {result['predicted_class']}")
    print(f"Confidence       : {result['confidence'] * 100:.2f}%")
    print(f"Severity         : {result['defect_details']['severity']}")
    print(f"Description      : {result['defect_details']['description']}")
    print(f"Remediation      : {result['defect_details']['remediation']}")
    print(f"Inference Time   : {result['inference_time_ms']} ms")
    print(f"Model / Device   : {result['model_name']} ({result['device']})")
    print("-" * 60)
    print("Class Probabilities:")
    for cls_name, prob in sorted(result["probabilities"].items(), key=lambda x: x[1], reverse=True):
        bar = "#" * int(prob * 30)
        print(f"  {cls_name:16}: {prob*100:6.2f}% {bar}")
    print("=" * 60)


if __name__ == "__main__":
    main()
