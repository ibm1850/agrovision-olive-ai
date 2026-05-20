from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
import torch
from PIL import Image, ImageOps
from torchvision import models, transforms

from backend.core.config import settings
from backend.services.image_io import decode_image_rgb
from utils.gradcam import generate_gradcam_base64, generate_heuristic_heatmap_base64

try:
    import timm
except Exception:
    timm = None
    extra_paths = [
        Path("C:/Users/Win11/Downloads/pytorch-image-models-main"),
        Path("C:/Users/Win11/Downloads/ConvNeXt-main"),
    ]
    for path in extra_paths:
        if path.exists():
            path_str = str(path.resolve())
            if path_str not in sys.path:
                sys.path.insert(0, path_str)
    try:
        import timm  # type: ignore[no-redef]
    except Exception:
        timm = None

try:
    from ultralytics import YOLO
except Exception:
    YOLO = None

UNKNOWN_VARIETY = "Unknown (leaf morphology insufficient for cultivar identification)"
LEAF_LEVEL_ONLY = "Leaf-level analysis only"
SINGLE_LEAF_NOTE = (
    "Diagnosis based on single leaf image. Upload multiple leaves and a tree photo for better accuracy."
)
UNCERTAIN_DIAGNOSIS = "Diagnosis uncertain - upload clearer leaf image"
HARVEST_NOT_AVAILABLE = "Cannot be estimated from leaf disease image"

SUPPORTED_DISEASE_CLASSES = [
    "Healthy leaf",
    "Olive Peacock Spot (Spilocaea oleaginea)",
    "Olive Anthracnose",
    "Aculus Olearius (olive mite damage)",
    "Olive Scab / Tuberculosis",
]

DEFAULT_VARIETIES = ["Chemlali", "Chetoui", "Arbequina", "Picholine", "Koroneiki"]
YOLO_ROI_LABEL_HINTS = ("leaf", "olive", "fruit", "lesion", "spot", "disease", "branch")
CONVNEXT_TIMM_MODELS = {
    "convnext_tiny": "hf_hub:timm/convnext_tiny.in12k_ft_in1k",
    "convnext_small": "hf_hub:timm/convnext_small.in12k_ft_in1k",
}


@dataclass
class LoadedClassifier:
    model: torch.nn.Module
    class_names: list[str]
    model_name: str


def _build_transfer_model(model_name: str, num_classes: int) -> torch.nn.Module:
    model_name = model_name.lower().strip()
    if model_name in CONVNEXT_TIMM_MODELS or model_name.startswith("hf_hub:timm/convnext"):
        if timm is None:
            raise RuntimeError(
                "ConvNeXt model requested but timm is not available. Install timm first."
            )
        timm_id = CONVNEXT_TIMM_MODELS.get(model_name, model_name)
        return timm.create_model(
            timm_id,
            pretrained=False,
            num_classes=num_classes,
        )

    if model_name == "mobilenet_v2":
        model = models.mobilenet_v2(weights=None)
        in_features = model.classifier[1].in_features
        model.classifier[1] = torch.nn.Linear(in_features, num_classes)
        return model

    model = models.efficientnet_b0(weights=None)
    in_features = model.classifier[1].in_features
    model.classifier[1] = torch.nn.Linear(in_features, num_classes)
    return model


class VisionService:
    def __init__(self) -> None:
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.pre_detector = self._load_pre_detector(settings.pre_detection_model_path)
        self.pre_detector_name = (
            settings.pre_detection_model_path.name if self.pre_detector is not None else None
        )
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

        self.variety_classifier = self._load_classifier(
            settings.variety_model_path,
            default_classes=DEFAULT_VARIETIES,
        )
        self.disease_classifier = self._load_classifier(
            settings.disease_model_path,
            default_classes=[
                "healthy",
                "olive_peacock_spot",
                "olive_anthracnose",
                "aculus_olearius",
                "olive_scab_tuberculosis",
            ],
        )

    def _load_classifier(self, model_path: Path, default_classes: list[str]) -> LoadedClassifier | None:
        if not model_path.exists():
            return None

        checkpoint = torch.load(model_path, map_location=self.device)
        if not isinstance(checkpoint, dict):
            return None

        state_dict = checkpoint.get("state_dict")
        class_names = checkpoint.get("class_names", default_classes)
        model_name = checkpoint.get("model_name", "efficientnet_b0")
        if state_dict is None:
            return None

        model = _build_transfer_model(model_name, num_classes=len(class_names))
        model.load_state_dict(state_dict)
        model.to(self.device)
        model.eval()
        return LoadedClassifier(model=model, class_names=list(class_names), model_name=model_name)

    def _load_pre_detector(self, model_path: Path):
        if YOLO is None:
            return None
        if not model_path.exists() or not model_path.is_file():
            return None
        # Avoid generic COCO YOLO checkpoints for leaf ROI.
        # They detect unrelated objects and can crop away the leaf region.
        if model_path.name.lower() in {"yolov8n.pt", "yolov8s.pt", "yolov8m.pt", "yolov8l.pt", "yolov8x.pt"}:
            return None
        try:
            return YOLO(str(model_path))
        except Exception:
            return None

    def _extract_roi_with_pre_detector(self, image_np: np.ndarray) -> tuple[np.ndarray, dict[str, object]]:
        if self.pre_detector is None:
            return image_np, {"roi_used": False, "label": None, "confidence": 0.0}

        image_h, image_w = image_np.shape[:2]
        image_area = float(max(1, image_h * image_w))
        try:
            results = self.pre_detector.predict(
                source=image_np,
                conf=float(np.clip(settings.pre_detection_conf, 0.01, 0.99)),
                iou=float(np.clip(settings.pre_detection_iou, 0.01, 0.99)),
                imgsz=640,
                verbose=False,
            )
        except Exception:
            return image_np, {"roi_used": False, "label": None, "confidence": 0.0}

        if not results or results[0].boxes is None or len(results[0].boxes) == 0:
            return image_np, {"roi_used": False, "label": None, "confidence": 0.0}

        boxes = results[0].boxes
        xyxy = boxes.xyxy.cpu().numpy()
        confs = boxes.conf.cpu().numpy()
        class_ids = boxes.cls.cpu().numpy().astype(int) if boxes.cls is not None else np.zeros(len(xyxy), dtype=int)
        names_raw = results[0].names if hasattr(results[0], "names") else {}
        names = names_raw if isinstance(names_raw, dict) else {}

        best_idx = None
        best_score = -1.0
        best_label = None

        for idx, (box, conf_score, cls_id) in enumerate(zip(xyxy, confs, class_ids)):
            x1, y1, x2, y2 = [int(max(0, round(v))) for v in box.tolist()]
            width = max(0, x2 - x1)
            height = max(0, y2 - y1)
            if width <= 0 or height <= 0:
                continue
            area = float(width * height)
            if area < image_area * 0.004:
                continue
            if area > image_area * 0.95:
                continue
            aspect = float(width) / float(height)
            if aspect < 0.15 or aspect > 6.0:
                continue

            label = str(names.get(int(cls_id), str(cls_id))).lower()
            label_hint = 0.25 if any(token in label for token in YOLO_ROI_LABEL_HINTS) else 0.0
            score = float(conf_score) + label_hint + min(0.15, area / image_area)

            if score > best_score:
                best_idx = idx
                best_score = score
                best_label = label

        if best_idx is None:
            return image_np, {"roi_used": False, "label": None, "confidence": 0.0}

        x1, y1, x2, y2 = [int(max(0, round(v))) for v in xyxy[best_idx].tolist()]
        pad_w = int(max(8, (x2 - x1) * 0.08))
        pad_h = int(max(8, (y2 - y1) * 0.08))
        x1 = max(0, x1 - pad_w)
        y1 = max(0, y1 - pad_h)
        x2 = min(image_w, x2 + pad_w)
        y2 = min(image_h, y2 + pad_h)
        if x2 <= x1 or y2 <= y1:
            return image_np, {"roi_used": False, "label": None, "confidence": 0.0}

        roi = image_np[y1:y2, x1:x2]
        if roi.size == 0:
            return image_np, {"roi_used": False, "label": None, "confidence": 0.0}

        return roi, {
            "roi_used": True,
            "label": best_label,
            "confidence": float(np.clip(float(confs[best_idx]), 0.0, 1.0)),
        }

    def analyze_image(self, image_bytes: bytes, image_name: str = "upload.jpg") -> dict[str, object]:
        image_np = decode_image_rgb(image_bytes)
        roi_np, roi_meta = self._extract_roi_with_pre_detector(image_np)
        image = Image.fromarray(roi_np)
        features = self._extract_leaf_features(image)
        lesion_count = int(features["lesion_count"])
        lesion_area_ratio = float(features["lesion_area_ratio"])
        infection_percentage = float(np.clip(lesion_area_ratio * 100.0, 0, 100))

        variety, variety_conf = self._predict_variety(image)
        disease_label, confidence, healthy_prediction, input_tensor, target_idx = self._predict_disease(
            image=image,
            features=features,
        )

        leaf_severity, leaf_health_status = self._estimate_leaf_severity(
            disease_label=disease_label,
            lesion_count=lesion_count,
            infection_percentage=infection_percentage,
        )
        leaf_health_score = self._leaf_health_score(infection_percentage=infection_percentage)

        if healthy_prediction:
            # Do not force healthy predictions to look highly confident.
            confidence = float(np.clip(confidence, 0.50, 0.96))
        else:
            confidence = float(np.clip(confidence, 0.45, 0.93))

        notes = [LEAF_LEVEL_ONLY, SINGLE_LEAF_NOTE]
        if confidence < 0.70:
            disease_output = UNCERTAIN_DIAGNOSIS
            notes.append(UNCERTAIN_DIAGNOSIS)
        elif disease_label == "Healthy leaf":
            disease_output = "None"
        else:
            disease_output = disease_label

        gradcam_image = self._generate_heatmap(
            image=image,
            input_tensor=input_tensor,
            target_idx=target_idx,
        )
        confidence_pct = int(round(np.clip(confidence, 0, 1) * 100))

        return {
            "variety": variety,
            "variety_confidence": round(float(np.clip(variety_conf, 0, 1)), 4),
            "health": LEAF_LEVEL_ONLY,
            "health_status": leaf_health_status,
            "leaf_health_status": leaf_health_status,
            "disease": disease_output,
            "disease_confidence": round(float(np.clip(confidence, 0, 1)), 4),
            "severity": leaf_severity,
            "leaf_severity": leaf_severity,
            "health_score": int(np.clip(leaf_health_score, 0, 100)),
            "leaf_health_score": int(np.clip(leaf_health_score, 0, 100)),
            "risk_level": LEAF_LEVEL_ONLY,
            "harvest_window": HARVEST_NOT_AVAILABLE,
            "confidence": f"{confidence_pct}%",
            "infection_percentage": round(infection_percentage, 2),
            "leaf_count": 1,
            "image_quality": "validated",
            "notes": " ".join(notes),
            "gradcam_image": gradcam_image,
            "image_name": image_name,
            "pre_detection_model": self.pre_detector_name,
            "pre_detection_roi_used": bool(roi_meta.get("roi_used", False)),
            "pre_detection_label": roi_meta.get("label"),
            "pre_detection_confidence": round(float(np.clip(float(roi_meta.get("confidence", 0.0)), 0.0, 1.0)), 4),
        }

    def _predict_variety(self, image: Image.Image) -> tuple[str, float]:
        # Leaf-only image is not sufficient for reliable cultivar identification.
        _ = image
        return UNKNOWN_VARIETY, 0.0

    def _predict_disease(
        self,
        image: Image.Image,
        features: dict[str, float],
    ) -> tuple[str, float, bool, torch.Tensor | None, int | None]:
        peacock_signature = features["peacock_signature"] > 0.5

        if self.disease_classifier is not None:
            (
                label,
                model_conf,
                input_tensor,
                target_idx,
                confidence_margin,
                norm_entropy,
            ) = self._predict_with_model(
                image,
                self.disease_classifier,
            )
            mapped_label, healthy_prediction = self._map_model_disease_label(label)
            heuristic_label, heuristic_conf = self._heuristic_disease_from_features(features)
            model_reliable = model_conf >= 0.62 and confidence_margin >= 0.08 and norm_entropy <= 0.90

            # Peacock override should be conservative:
            # only intervene when model evidence is weak/conflicted.
            peacock_override_allowed = (
                peacock_signature
                and mapped_label != "Aculus Olearius (olive mite damage)"
                and (
                    model_conf < 0.58
                    or confidence_margin < 0.08
                    or (
                        healthy_prediction
                        and model_conf < 0.75
                        and features["disease_signal"] >= 0.40
                    )
                )
                and (features["ring_ratio"] >= 0.008 or features["yellow_halo_ratio"] >= 0.03)
            )
            if peacock_override_allowed:
                return (
                    "Olive Peacock Spot (Spilocaea oleaginea)",
                    max(model_conf, features["peacock_confidence"]),
                    False,
                    input_tensor,
                    target_idx,
                )

            # Prefer heuristic over "healthy" only when lesion evidence is clearly strong.
            if (
                healthy_prediction
                and model_conf < 0.75
                and features["disease_signal"] >= 0.45
                and (
                    features["lesion_count"] >= 2
                    or features["ring_ratio"] >= 0.006
                    or features["yellow_halo_ratio"] >= 0.02
                )
            ):
                return heuristic_label, heuristic_conf, False, input_tensor, target_idx

            # Model-first fusion: trust the trained classifier when confidence is stable.
            if model_reliable:
                return mapped_label, model_conf, healthy_prediction, input_tensor, target_idx

            # Fall back to heuristic only when it is substantially stronger than model signal.
            if heuristic_conf >= model_conf + 0.18:
                return heuristic_label, heuristic_conf, heuristic_label == "Healthy leaf", input_tensor, target_idx

            return mapped_label, min(model_conf, 0.60), healthy_prediction, input_tensor, target_idx

        heuristic_label, heuristic_conf = self._heuristic_disease_from_features(features)
        return heuristic_label, heuristic_conf, heuristic_label == "Healthy leaf", None, None

    def _heuristic_disease_from_features(self, features: dict[str, float]) -> tuple[str, float]:
        lesion_area_ratio = features["lesion_area_ratio"]
        lesion_count = int(features["lesion_count"])
        yellow_halo_ratio = features["yellow_halo_ratio"]
        ring_ratio = features["ring_ratio"]
        necrotic_ratio = features["necrotic_ratio"]
        bronzing_ratio = features["bronzing_ratio"]
        rough_texture = features["rough_texture"]
        peacock_signature = features["peacock_signature"] > 0.5
        disease_signal = features["disease_signal"]

        if peacock_signature:
            conf = 0.70 + min(0.22, yellow_halo_ratio * 2.2 + ring_ratio * 5.0)
            return "Olive Peacock Spot (Spilocaea oleaginea)", float(np.clip(conf, 0.70, 0.95))

        # Visible dark lesion(s) with yellow halo should be treated as peacock spot pattern.
        if (
            lesion_count >= 2
            and yellow_halo_ratio > 0.01
            and ring_ratio > 0.0015
            and lesion_area_ratio > 0.004
        ):
            conf = 0.68 + min(0.20, yellow_halo_ratio * 2.2 + lesion_area_ratio * 1.2 + ring_ratio * 2.0)
            return "Olive Peacock Spot (Spilocaea oleaginea)", float(np.clip(conf, 0.68, 0.90))

        if disease_signal < 0.12 and lesion_area_ratio < 0.03 and bronzing_ratio < 0.08 and lesion_count == 0:
            return "Healthy leaf", float(np.clip(0.78 + (0.12 - disease_signal) * 0.7, 0.78, 0.94))

        if necrotic_ratio > 0.10 and lesion_area_ratio >= 0.10:
            conf = 0.68 + min(0.20, necrotic_ratio * 1.1 + lesion_area_ratio * 0.8)
            return "Olive Anthracnose", float(np.clip(conf, 0.68, 0.90))

        if bronzing_ratio > 0.18 and lesion_count <= 4:
            conf = 0.63 + min(0.22, bronzing_ratio * 0.9)
            return "Aculus Olearius (olive mite damage)", float(np.clip(conf, 0.63, 0.85))

        if rough_texture > 0.40 and lesion_count >= 4:
            conf = 0.64 + min(0.20, rough_texture * 0.45 + lesion_area_ratio * 0.4)
            return "Olive Scab / Tuberculosis", float(np.clip(conf, 0.64, 0.86))

        if lesion_area_ratio > 0.10 or lesion_count > 10:
            return "Olive Scab / Tuberculosis", float(np.clip(0.62 + lesion_area_ratio * 0.8, 0.62, 0.86))

        return "Olive Peacock Spot (Spilocaea oleaginea)", float(np.clip(0.55 + disease_signal * 0.35, 0.55, 0.78))

    def _estimate_leaf_severity(
        self,
        disease_label: str,
        lesion_count: int,
        infection_percentage: float,
    ) -> tuple[str, str]:
        if disease_label == "Healthy leaf":
            return "Mild", "Healthy"

        # Severity rules from visible leaf damage only.
        if infection_percentage > 25:
            return "Severe", "Severe"
        if lesion_count >= 4 or infection_percentage >= 10:
            return "Moderate", "Moderate"
        if lesion_count >= 1 or infection_percentage > 0:
            return "Mild", "Mild"
        return "Mild", "Mild"

    def _leaf_health_score(self, infection_percentage: float) -> int:
        score = 100.0 - (float(np.clip(infection_percentage, 0, 100)) * 1.5)
        return int(np.clip(round(score), 0, 100))

    def _extract_leaf_features(self, image: Image.Image) -> dict[str, float]:
        image_np = np.array(image.resize((512, 512)).convert("RGB"))
        hsv = cv2.cvtColor(image_np, cv2.COLOR_RGB2HSV)
        gray = cv2.cvtColor(image_np, cv2.COLOR_RGB2GRAY)

        h = hsv[:, :, 0].astype(np.float32)
        s = hsv[:, :, 1].astype(np.float32)
        v = hsv[:, :, 2].astype(np.float32)
        r = image_np[:, :, 0].astype(np.float32)
        g = image_np[:, :, 1].astype(np.float32)
        b = image_np[:, :, 2].astype(np.float32)

        dark_spot_mask = ((v < 95) & (r < 125) & (g < 125) & (b < 125)).astype(np.uint8) * 255
        yellow_halo_mask = ((h >= 16) & (h <= 45) & (s > 45) & (v > 75)).astype(np.uint8) * 255
        necrotic_mask = ((v < 85) & (s < 95)).astype(np.uint8) * 255
        bronzing_mask = ((r > g) & (g > b) & (r > 95) & (r < 190) & (g > 70) & (g < 165)).astype(np.uint8) * 255

        kernel3 = np.ones((3, 3), np.uint8)
        kernel7 = np.ones((7, 7), np.uint8)
        dark_spot_mask = cv2.morphologyEx(dark_spot_mask, cv2.MORPH_OPEN, kernel3)
        dark_spot_mask = cv2.morphologyEx(dark_spot_mask, cv2.MORPH_CLOSE, kernel3)

        dilated_dark = cv2.dilate(dark_spot_mask, kernel7, iterations=1)
        ring_mask = cv2.bitwise_and(yellow_halo_mask, dilated_dark)
        ring_mask = cv2.bitwise_and(ring_mask, cv2.bitwise_not(dark_spot_mask))

        num_labels, _, stats, _ = cv2.connectedComponentsWithStats(dark_spot_mask, connectivity=8)
        lesion_count = 0
        lesion_pixels = 0
        total_pixels = dark_spot_mask.shape[0] * dark_spot_mask.shape[1]
        for idx in range(1, num_labels):
            area = int(stats[idx, cv2.CC_STAT_AREA])
            if 20 <= area <= 12000:
                lesion_count += 1
                lesion_pixels += area

        lesion_area_ratio = float(lesion_pixels / total_pixels)
        yellow_halo_ratio = float(np.mean(yellow_halo_mask > 0))
        ring_ratio = float(np.mean(ring_mask > 0))
        necrotic_ratio = float(np.mean(necrotic_mask > 0))
        bronzing_ratio = float(np.mean(bronzing_mask > 0))

        laplacian = cv2.Laplacian(gray, cv2.CV_32F)
        rough_texture = float(np.clip(np.std(laplacian) / 40.0, 0, 1))

        peacock_signature_score = (
            1.4 * float(lesion_count >= 1)
            + min(1.4, lesion_count / 4.0)
            + min(2.0, ring_ratio * 90)
            + min(1.6, yellow_halo_ratio * 45)
        )
        peacock_signature = float(
            1.0
            if (
                peacock_signature_score >= 4.2
                and lesion_count >= 2
                and (ring_ratio >= 0.004 or yellow_halo_ratio >= 0.02)
            )
            else 0.0
        )
        peacock_confidence = float(np.clip(0.62 + peacock_signature_score / 12.0, 0.62, 0.95))

        disease_signal = float(
            np.clip(
                lesion_area_ratio * 4.2
                + ring_ratio * 7.5
                + yellow_halo_ratio * 2.4
                + bronzing_ratio * 1.4
                + necrotic_ratio * 1.7,
                0,
                1,
            )
        )

        return {
            "lesion_count": float(lesion_count),
            "lesion_area_ratio": lesion_area_ratio,
            "yellow_halo_ratio": yellow_halo_ratio,
            "ring_ratio": ring_ratio,
            "necrotic_ratio": necrotic_ratio,
            "bronzing_ratio": bronzing_ratio,
            "rough_texture": rough_texture,
            "peacock_signature": peacock_signature,
            "peacock_confidence": peacock_confidence,
            "disease_signal": disease_signal,
        }

    def _predict_with_model(
        self, image: Image.Image, classifier: LoadedClassifier
    ) -> tuple[str, float, torch.Tensor, int, float, float]:
        image_views = [image, ImageOps.mirror(image)]
        input_batches = torch.stack([self.preprocess(view) for view in image_views]).to(self.device)
        with torch.no_grad():
            logits = classifier.model(input_batches)
            probs = torch.softmax(logits, dim=1)
            mean_probs = torch.mean(probs, dim=0)
            idx = int(torch.argmax(mean_probs).item())
            confidence = float(mean_probs[idx].item())

            sorted_probs, _ = torch.sort(mean_probs, descending=True)
            top1 = float(sorted_probs[0].item()) if sorted_probs.numel() > 0 else 0.0
            top2 = float(sorted_probs[1].item()) if sorted_probs.numel() > 1 else 0.0
            margin = float(np.clip(top1 - top2, 0.0, 1.0))

            entropy = float(
                -torch.sum(mean_probs * torch.log(mean_probs + 1e-8)).item()
            )
            max_entropy = float(np.log(max(2, mean_probs.numel())))
            norm_entropy = float(np.clip(entropy / max_entropy, 0.0, 1.0))
        input_tensor = input_batches[:1]
        return classifier.class_names[idx], confidence, input_tensor, idx, margin, norm_entropy

    def _map_model_disease_label(self, label: str) -> tuple[str, bool]:
        label_lower = label.lower().strip()
        if any(token in label_lower for token in ["healthy", "none", "normal"]):
            return "Healthy leaf", True
        if any(token in label_lower for token in ["peacock", "spilocaea"]):
            return "Olive Peacock Spot (Spilocaea oleaginea)", False
        if "anthracnose" in label_lower:
            return "Olive Anthracnose", False
        if "aculus" in label_lower or "olearius" in label_lower or "mite" in label_lower:
            return "Aculus Olearius (olive mite damage)", False
        if any(token in label_lower for token in ["scab", "tuberculosis", "tuberc"]):
            return "Olive Scab / Tuberculosis", False
        return "Olive Scab / Tuberculosis", False

    def _generate_heatmap(
        self,
        image: Image.Image,
        input_tensor: torch.Tensor | None,
        target_idx: int | None,
    ) -> str:
        if self.disease_classifier is not None and input_tensor is not None and target_idx is not None:
            try:
                return generate_gradcam_base64(
                    model=self.disease_classifier.model,
                    model_name=self.disease_classifier.model_name,
                    input_tensor=input_tensor,
                    image=image,
                    class_idx=target_idx,
                )
            except Exception:
                pass
        return generate_heuristic_heatmap_base64(image)
