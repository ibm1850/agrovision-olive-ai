from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import torch
from PIL import Image
from torchvision import models, transforms

from backend.core.config import settings

SCENE_CLASSES = ["leaf", "orchard_branch", "fruit_closeup", "harvest_pile", "unknown"]


def normalize_scene_label(label: str) -> str:
    normalized = str(label or "").strip().lower()
    if normalized in {"leaf", "leaf_closeup"}:
        return "leaf"
    if normalized in {"branch_twig", "branch", "twig", "orchard_branch"}:
        return "orchard_branch"
    if normalized in {"fruit", "fruit_closeup", "olive", "olives"}:
        return "fruit_closeup"
    if normalized in {"harvest_pile", "pile"}:
        return "harvest_pile"
    return "unknown"


def _build_scene_model(model_name: str, num_classes: int) -> torch.nn.Module:
    model_name = (model_name or "mobilenet_v3_small").lower()
    if model_name == "resnet18":
        model = models.resnet18(weights=None)
        in_features = model.fc.in_features
        model.fc = torch.nn.Linear(in_features, num_classes)
        return model
    if model_name == "efficientnet_b0":
        model = models.efficientnet_b0(weights=None)
        in_features = model.classifier[1].in_features
        model.classifier[1] = torch.nn.Linear(in_features, num_classes)
        return model

    model = models.mobilenet_v3_small(weights=None)
    in_features = model.classifier[3].in_features
    model.classifier[3] = torch.nn.Linear(in_features, num_classes)
    return model


class SceneClassifierService:
    def __init__(self) -> None:
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.preprocess = transforms.Compose(
            [
                transforms.Resize((224, 224)),
                transforms.ToTensor(),
                transforms.Normalize(
                    mean=[0.485, 0.456, 0.406],
                    std=[0.229, 0.224, 0.225],
                ),
            ]
        )
        self.model: torch.nn.Module | None = None
        self.class_names: list[str] = SCENE_CLASSES.copy()
        self.model_name = "heuristic"
        self._load_model(settings.scene_classifier_model_path)

    def _load_model(self, model_path: Path) -> None:
        if not model_path.exists():
            return
        try:
            checkpoint = torch.load(model_path, map_location=self.device)
            if not isinstance(checkpoint, dict) or "state_dict" not in checkpoint:
                return
            class_names = checkpoint.get("class_names", SCENE_CLASSES)
            model_name = checkpoint.get("model_name", "mobilenet_v3_small")
            model = _build_scene_model(str(model_name), num_classes=len(class_names))
            model.load_state_dict(checkpoint["state_dict"])
            model.to(self.device)
            model.eval()
            self.model = model
            self.class_names = list(class_names)
            self.model_name = str(model_name)
        except Exception:
            self.model = None
            self.class_names = SCENE_CLASSES.copy()
            self.model_name = "heuristic"

    def classify(self, image_bytes: bytes) -> dict[str, Any]:
        image = self._decode_image(image_bytes)
        image_np = np.array(image.resize((512, 512)).convert("RGB"))
        if self.model is not None:
            tensor = self.preprocess(image).unsqueeze(0).to(self.device)
            with torch.no_grad():
                logits = self.model(tensor)
                probs = torch.softmax(logits, dim=1)
            idx = int(torch.argmax(probs, dim=1).item())
            confidence = float(probs[0, idx].item())
            raw_label = self.class_names[idx] if idx < len(self.class_names) else "unknown"
            label = normalize_scene_label(raw_label)
            label, confidence = self._postprocess_scene_label(label, confidence, image_np)
            return {
                "scene_type": label,
                "confidence": round(float(np.clip(confidence, 0.0, 1.0)), 4),
                "model_name": self.model_name,
            }
        return self._heuristic_classify(image)

    def _decode_image(self, image_bytes: bytes) -> Image.Image:
        arr = np.frombuffer(image_bytes, dtype=np.uint8)
        bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if bgr is not None:
            rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
            return Image.fromarray(rgb)
        return Image.open(io.BytesIO(image_bytes)).convert("RGB")

    def _heuristic_classify(self, image: Image.Image) -> dict[str, Any]:
        image_np = np.array(image.resize((512, 512)).convert("RGB"))
        hsv = cv2.cvtColor(image_np, cv2.COLOR_RGB2HSV)

        h = hsv[:, :, 0].astype(np.float32)
        s = hsv[:, :, 1].astype(np.float32)
        v = hsv[:, :, 2].astype(np.float32)

        leaf_green = ((h >= 30) & (h <= 95) & (s > 30) & (v > 35))
        leaf_soft = ((h >= 28) & (h <= 100) & (s > 20) & (v > 28))
        fruit_green = ((h >= 22) & (h <= 95) & (s > 40) & (v > 45))
        fruit_yellow = ((h >= 10) & (h <= 38) & (s > 45) & (v > 65))
        fruit_dark = (v < 70) & (s < 170)
        fruit_mask = (fruit_green | fruit_yellow | fruit_dark).astype(np.uint8)

        green_ratio = float(np.mean(leaf_green))
        leaf_soft_ratio = float(np.mean(leaf_soft))
        fruit_ratio = float(np.mean(fruit_mask > 0))
        branch_like = float(np.mean((h >= 8) & (h <= 25) & (s > 20) & (v > 25)))

        num_labels, _, stats, _ = cv2.connectedComponentsWithStats(fruit_mask, connectivity=8)
        comp_areas = [
            int(stats[idx, cv2.CC_STAT_AREA])
            for idx in range(1, num_labels)
            if 90 <= int(stats[idx, cv2.CC_STAT_AREA]) <= 40000
        ]
        component_count = len(comp_areas)
        largest_component = max(comp_areas) if comp_areas else 0
        largest_ratio = float(largest_component / (image_np.shape[0] * image_np.shape[1]))

        if component_count >= 3 and fruit_ratio > 0.04 and branch_like > 0.06:
            label = "orchard_branch"
            confidence = 0.76
        elif fruit_ratio > 0.30 and component_count >= 10 and branch_like < 0.035 and green_ratio < 0.25:
            label = "harvest_pile"
            confidence = 0.78
        elif component_count in {1, 2, 3} and largest_ratio > 0.025 and fruit_ratio > 0.03:
            label = "fruit_closeup"
            confidence = 0.72
        elif green_ratio > 0.42 and fruit_ratio < 0.04:
            label = "leaf"
            confidence = 0.7
        elif leaf_soft_ratio > 0.28 and fruit_ratio < 0.12 and branch_like < 0.15:
            label = "leaf"
            confidence = 0.62
        else:
            label = "unknown"
            confidence = 0.45

        label, confidence = self._postprocess_scene_label(label, confidence, image_np)
        return {"scene_type": label, "confidence": round(float(np.clip(confidence, 0.0, 1.0)), 4), "model_name": "heuristic"}

    def _postprocess_scene_label(self, label: str, confidence: float, image_np: np.ndarray) -> tuple[str, float]:
        """Reduce false harvest_pile predictions for on-tree branch images."""
        hsv = cv2.cvtColor(image_np, cv2.COLOR_RGB2HSV)
        h = hsv[:, :, 0].astype(np.float32)
        s = hsv[:, :, 1].astype(np.float32)
        v = hsv[:, :, 2].astype(np.float32)

        branch_like = float(np.mean((h >= 8) & (h <= 25) & (s > 20) & (v > 25)))
        leaf_like = float(np.mean((h >= 30) & (h <= 95) & (s > 25) & (v > 35)))

        # If the classifier says pile but branch/leaf context is strong, this is likely on-tree.
        if label == "harvest_pile" and (branch_like > 0.055 or leaf_like > 0.25):
            return "orchard_branch", min(0.82, max(0.62, float(confidence) * 0.92))

        return label, float(confidence)
