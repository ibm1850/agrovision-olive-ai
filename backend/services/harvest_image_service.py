from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import cv2
import numpy as np

from backend.core.config import settings
from backend.services.harvest_oil_service import HarvestOilService
from backend.services.image_io import decode_image_rgb
from backend.services.tunisian_harvest_logic import estimate_maturity_index, harvest_decision

try:
    from ultralytics import YOLO
except Exception:
    YOLO = None


@dataclass
class OliveFocusStats:
    detected_olives: int = 0
    avg_confidence: float = 0.0
    fruit_area_ratio: float = 0.0
    detector_ready: bool = False
    full_image_fallback: bool = True


class HarvestImageService:
    """Image-first harvest predictor.

    The current harvest model was trained on measurement/lab data, not raw images.
    This service extracts surrogate measurements from the uploaded olive image and
    feeds them to the trained model for an image-scan UX.
    """

    def __init__(self, harvest_oil_service: HarvestOilService) -> None:
        self.harvest_oil_service = harvest_oil_service
        self.detector = None
        model_path = settings.olive_detection_model_path
        if YOLO is not None and model_path.exists():
            try:
                self.detector = YOLO(str(model_path))
                try:
                    # Deterministic inference mode for stable predictions.
                    self.detector.model.eval()
                except Exception:
                    pass
            except Exception:
                self.detector = None

    def predict_from_image(
        self,
        image_bytes: bytes,
        image_name: str = "harvest_upload.jpg",
        sample_date: str | None = None,
        week_no: int | None = None,
        cultivar: str | None = "Chemlali",
        target_style: str | None = "premium_oil",
        disease: str | None = None,
        health_score: int | None = None,
        scene_type: str | None = None,
    ) -> dict[str, Any]:
        if not image_bytes:
            raise ValueError("Uploaded image is empty.")

        image_np = self._decode_image_rgb(image_bytes)
        scene_key = str(scene_type or "").strip().lower()
        disable_counting = scene_key == "harvest_pile"
        measurements, ripeness_index, mi_skin_estimate, mi_uncertain, focus_stats, _olive_focus = self._extract_surrogate_measurements(
            image_np=image_np,
            sample_date=sample_date,
            week_no=week_no,
            use_detector=not disable_counting,
        )
        if not disable_counting and focus_stats.detected_olives <= 0:
            raise ValueError(
                "No olives detected in the uploaded image. "
                "Upload a clear fruit image with visible olives for harvest prediction."
            )
        if disable_counting:
            focus_stats.detected_olives = 0
            focus_stats.avg_confidence = 0.0
            focus_stats.fruit_area_ratio = 0.0
            focus_stats.full_image_fallback = True
        measurements["cultivar"] = str(cultivar or "Chemlali")
        measurements["target_style"] = str(target_style or "premium_oil")

        prediction = self.harvest_oil_service.predict(measurements)
        mi_from_ripeness = float(estimate_maturity_index(ripeness_index))
        color_weight = 0.7 if focus_stats.avg_confidence >= 0.65 else 0.55
        mi_estimate = round(float(np.clip((color_weight * mi_skin_estimate) + ((1.0 - color_weight) * mi_from_ripeness), 0.0, 7.0)), 2)
        decision = harvest_decision(
            cultivar=cultivar,
            target_style=target_style,
            maturity_index=mi_estimate,
            estimated_oil_content=float(prediction.get("estimated_oil_content", 0.0)),
            disease=disease,
            health_score=health_score,
        )

        prediction["maturity_stage"] = str(decision["maturity_stage"])
        prediction["harvest_recommendation"] = str(decision["harvest_recommendation"])
        prediction["maturity_index_estimate"] = float(decision["maturity_index_estimate"])
        prediction["ioc_maturity_class"] = str(decision["ioc_maturity_class"])
        prediction["tunisian_window"] = str(decision["tunisian_window"])
        image_reliability = self._image_reliability(focus_stats=focus_stats, mi_uncertain=mi_uncertain)
        prediction["reliability"] = self._merge_reliability(str(decision["reliability"]), image_reliability)
        prediction["ripeness_index"] = round(float(ripeness_index), 3)
        prediction["image_maturity_index"] = round(float(mi_estimate), 3)
        prediction["average_capacitance"] = round(
            float(measurements.get("Average capacitance (nF)", 0.0)), 3
        )
        prediction["detected_olives"] = int(focus_stats.detected_olives)
        prediction["olive_detection_confidence"] = round(float(focus_stats.avg_confidence), 3)
        prediction["fruit_coverage_percent"] = round(float(focus_stats.fruit_area_ratio * 100.0), 2)
        prediction["image_name"] = image_name
        prediction["notes"] = (
            "Image-based harvest estimate generated from detected olive-fruit regions. "
            "For maximum accuracy, combine with lab measurements. "
            f"{decision['notes']} "
            + (
                "MI 4-7 distinction is uncertain from skin-only images without cut-flesh observation."
                if mi_uncertain
                else "Skin-stage estimation confidence is acceptable for this image."
            )
        )
        if disable_counting:
            prediction["notes"] = (
                "Scene correction applied: harvest_pile detected. Fruit counting is disabled, "
                "maturity estimation uses full image only. "
                + prediction["notes"]
            )
        return prediction

    def estimate_visual_maturity(
        self,
        *,
        image_bytes: bytes,
        scene_type: str | None = None,
        sample_date: str | None = None,
        week_no: int | None = None,
    ) -> dict[str, Any]:
        image_np = self._decode_image_rgb(image_bytes)
        height, width = image_np.shape[:2]
        scene_key = str(scene_type or "").strip().lower()
        disable_counting = scene_key == "harvest_pile"

        _, ripeness_index, mi_skin_estimate, mi_uncertain, focus_stats, olive_focus = self._extract_surrogate_measurements(
            image_np=image_np,
            sample_date=sample_date,
            week_no=week_no,
            use_detector=not disable_counting,
        )
        if disable_counting:
            focus_stats.detected_olives = 0
            focus_stats.avg_confidence = 0.0
            focus_stats.fruit_area_ratio = 0.0
            focus_stats.full_image_fallback = True
        preprocessing = {
            "scene_type": scene_key or "unknown",
            "detector_available": bool(self.detector is not None),
            "detector_enabled": bool(not disable_counting),
            "detector_used": bool((not disable_counting) and (self.detector is not None)),
            "full_image_fallback": bool(focus_stats.full_image_fallback),
            "inference_augment": False,
            "inference_randomized": False,
        }

        hsv_full = cv2.cvtColor(image_np, cv2.COLOR_RGB2HSV)
        hsv_focus = cv2.cvtColor(olive_focus, cv2.COLOR_RGB2HSV)
        gray = cv2.cvtColor(image_np, cv2.COLOR_RGB2GRAY)
        brightness = float(np.mean(hsv_full[:, :, 2]))
        focus_brightness = float(np.mean(hsv_focus[:, :, 2]))
        blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        exposure_high_ratio = float(np.mean(hsv_full[:, :, 2] >= 245))
        exposure_low_ratio = float(np.mean(hsv_full[:, :, 2] <= 20))
        shadow_ratio = float(np.mean(hsv_full[:, :, 2] <= 40))
        focus_pixels = int(np.prod(olive_focus.shape[:2])) if olive_focus.ndim >= 2 else int(len(olive_focus))

        color_ratios = self._color_ratios(
            h=hsv_focus[:, :, 0].astype(np.float32),
            s=hsv_focus[:, :, 1].astype(np.float32),
            v=hsv_focus[:, :, 2].astype(np.float32),
        )
        color_ratios_full = self._color_ratios(
            h=hsv_full[:, :, 0].astype(np.float32),
            s=hsv_full[:, :, 1].astype(np.float32),
            v=hsv_full[:, :, 2].astype(np.float32),
        )
        visual_stage = self._visual_stage_from_mi(mi_skin_estimate, color_ratios)
        sample_uniformity = self._uniformity_from_ratios(color_ratios)
        stage_ambiguous = bool(mi_uncertain or sample_uniformity == "mixed")

        warnings: list[str] = []
        blocking: list[str] = []
        if min(width, height) < 720:
            warnings.append("Resolution is low; capture a closer and sharper olive photo.")
        if blur_score < 40:
            warnings.append("Image appears blurry.")
        if brightness < 60:
            warnings.append("Image appears too dark.")
        if exposure_high_ratio > 0.15:
            warnings.append("Image has bright overexposed areas that may reduce maturity accuracy.")
        if shadow_ratio > 0.35:
            warnings.append("Image has strong shadows; maturity can be underestimated.")
        if not disable_counting and focus_stats.fruit_area_ratio < 0.003:
            warnings.append("Too much background compared to visible fruit.")
        if brightness < 35:
            blocking.append("Image is too dark for reliable maturity estimation.")
        if blur_score < 25:
            blocking.append("Image is too blurry for reliable maturity estimation.")
        if exposure_high_ratio > 0.32:
            blocking.append("Image is too overexposed for reliable maturity estimation.")
        if exposure_low_ratio > 0.30:
            blocking.append("Image is too underexposed for reliable maturity estimation.")
        if not disable_counting and focus_stats.detected_olives <= 0:
            blocking.append("No olive detected in the image.")
        if not disable_counting and focus_stats.detected_olives > 0 and focus_stats.fruit_area_ratio < 0.004:
            warnings.append("Olive appears too small in frame; move closer.")
        if not disable_counting and focus_stats.detected_olives > 0 and focus_stats.fruit_area_ratio < 0.0018:
            blocking.append("Olive is too far/small in the frame for reliable maturity estimation.")
        if mi_uncertain:
            warnings.append("Late-stage class is uncertain from skin-only image.")
        if len(warnings) >= 4 and not blocking:
            blocking.append("Image quality is too poor for reliable maturity estimation.")

        quality_score = 100.0
        quality_score -= min(25.0, max(0.0, 55.0 - blur_score) * 0.4)
        quality_score -= min(20.0, max(0.0, 65.0 - brightness) * 0.22)
        quality_score -= min(18.0, exposure_high_ratio * 55.0)
        quality_score -= min(14.0, exposure_low_ratio * 50.0)
        quality_score -= min(10.0, shadow_ratio * 25.0)
        if not disable_counting:
            quality_score -= min(16.0, max(0.0, 0.009 - focus_stats.fruit_area_ratio) * 900.0)
        quality_score = float(np.clip(quality_score, 0.0, 100.0))

        return {
            "scene_type": scene_key or "unknown",
            "image_width": int(width),
            "image_height": int(height),
            "brightness": round(brightness, 2),
            "focus_brightness": round(focus_brightness, 2),
            "blur_score": round(blur_score, 2),
            "overexposure_ratio": round(exposure_high_ratio, 3),
            "underexposure_ratio": round(exposure_low_ratio, 3),
            "shadow_ratio": round(shadow_ratio, 3),
            "quality_score": round(quality_score, 2),
            "quality_warnings": warnings,
            "blocking_issues": blocking,
            "quality_passed": len(blocking) == 0,
            "detected_olives": int(focus_stats.detected_olives),
            "olive_detection_confidence": round(float(focus_stats.avg_confidence), 3),
            "fruit_coverage_percent": round(float(focus_stats.fruit_area_ratio * 100.0), 2),
            "ripeness_index": round(float(ripeness_index), 3),
            "image_maturity_index": round(float(np.clip(mi_skin_estimate, 0.0, 7.0)), 3),
            "visual_stage": visual_stage,
            "sample_uniformity": sample_uniformity,
            "stage_ambiguous": stage_ambiguous,
            "mi_uncertain": bool(mi_uncertain),
            "color_ratios": color_ratios,
            "color_ratios_full": color_ratios_full,
            "preprocessing": preprocessing,
            "focus_pixels": focus_pixels,
        }

    def _decode_image_rgb(self, image_bytes: bytes) -> np.ndarray:
        return decode_image_rgb(image_bytes)

    def _merge_reliability(self, decision_reliability: str, image_reliability: str) -> str:
        order = {"low": 0, "medium": 1, "high": 2}
        dec = (decision_reliability or "medium").strip().lower()
        img = (image_reliability or "medium").strip().lower()
        dec_rank = order.get(dec, 1)
        img_rank = order.get(img, 1)
        return dec if dec_rank <= img_rank else img

    def _image_reliability(self, focus_stats: OliveFocusStats, mi_uncertain: bool) -> str:
        score = 0
        if focus_stats.detected_olives >= 3:
            score += 1
        if focus_stats.avg_confidence >= 0.7:
            score += 1
        elif focus_stats.avg_confidence < 0.5:
            score -= 1
        if focus_stats.fruit_area_ratio >= 0.02:
            score += 1
        elif focus_stats.fruit_area_ratio < 0.005:
            score -= 1
        if mi_uncertain:
            score -= 1

        if score >= 2:
            return "high"
        if score >= 0:
            return "medium"
        return "low"

    def _color_ratios(self, h: np.ndarray, s: np.ndarray, v: np.ndarray) -> dict[str, float]:
        green = float(np.mean((h >= 30) & (h <= 95) & (s > 25) & (v > 35)))
        yellow = float(np.mean((h >= 15) & (h <= 40) & (s > 40) & (v > 55)))
        # Purple/violet can appear near hue wrap (0-12) or in high-hue magenta bands.
        purple_core = (h >= 110) & (h <= 179) & (s > 18) & (v > 18)
        purple_wrap = (h <= 12) & (s > 45) & (v > 22)
        purple = float(np.mean(purple_core | purple_wrap))
        green_zone = (h >= 25) & (h <= 95) & (s > 25)
        yellow_zone = (h >= 10) & (h <= 45) & (s > 30)
        dark_low = v < 70
        dark_low_sat = dark_low & (s < 60)
        # Capture dark purple/black-ripe olives that can keep medium/high saturation.
        dark_ripe_hue = ((h >= 90) & (h <= 179)) | (h <= 12)
        dark_purple = (v < 95) & (s > 35) & dark_ripe_hue
        dark_true = (dark_low_sat | dark_purple) & (~green_zone) & (~yellow_zone)
        blackish = float(np.mean(dark_true))
        dark_ratio = float(np.mean(dark_low))
        dark_low_sat_ratio = float(np.mean(dark_low_sat))
        turning = float(np.clip((yellow + (0.7 * purple)) * (1.0 - min(blackish, 0.75)), 0.0, 1.0))
        return {
            "green": round(float(np.clip(green, 0.0, 1.0)), 3),
            "yellow": round(float(np.clip(yellow, 0.0, 1.0)), 3),
            "turning": round(float(np.clip(turning, 0.0, 1.0)), 3),
            "purple": round(float(np.clip(purple, 0.0, 1.0)), 3),
            "black": round(float(np.clip(blackish, 0.0, 1.0)), 3),
            "dark": round(float(np.clip(dark_ratio, 0.0, 1.0)), 3),
            "dark_low_sat": round(float(np.clip(dark_low_sat_ratio, 0.0, 1.0)), 3),
            "dark_purple": round(float(np.clip(float(np.mean(dark_purple)), 0.0, 1.0)), 3),
        }

    def _visual_stage_from_mi(self, mi: float, color_ratios: dict[str, float]) -> str:
        black = float(color_ratios.get("black", 0.0))
        purple = float(color_ratios.get("purple", 0.0))
        green = float(color_ratios.get("green", 0.0))
        yellow = float(color_ratios.get("yellow", 0.0))
        turning = float(color_ratios.get("turning", 0.0))
        dark = float(color_ratios.get("dark", 0.0))
        dark_low_sat = float(color_ratios.get("dark_low_sat", 0.0))
        dark_purple = float(color_ratios.get("dark_purple", 0.0))
        early_total = green + yellow
        early_dominance = early_total >= 0.5
        dark_dominant = black >= max(0.50, early_total + 0.08)

        # Mature only when dark-ripe evidence is dominant, not just shadows/lighting.
        if (
            (not early_dominance or dark_dominant)
            and black >= 0.58
            and dark >= 0.60
            and (dark_low_sat >= 0.30 or dark_purple >= 0.22 or purple >= 0.10)
        ) or (
            (not early_dominance or dark_dominant)
            and black >= 0.42
            and purple >= 0.20
            and dark >= 0.55
            and mi >= 3.8
        ) or (
            (not early_dominance or dark_dominant)
            and black >= 0.50
            and dark >= 0.65
            and dark_purple >= 0.25
        ):
            return "black / very mature"
        if purple >= 0.22 or (mi >= 3.2 and not early_dominance):
            return "mostly purple"
        if (purple >= 0.06 or turning >= 0.16 or (green >= 0.35 and purple >= 0.05)) and black < 0.32:
            return "start of color change"
        if green >= 0.7 and purple < 0.1 and black < 0.15:
            return "deep green"
        if green >= 0.45:
            return "yellow-green"
        return "ambiguous"

    def _uniformity_from_ratios(self, color_ratios: dict[str, float]) -> str:
        values = sorted(
            [
                float(color_ratios.get("green", 0.0)),
                float(color_ratios.get("turning", 0.0)),
                float(color_ratios.get("purple", 0.0)),
                float(color_ratios.get("black", 0.0)),
            ],
            reverse=True,
        )
        top = values[0] if values else 0.0
        second = values[1] if len(values) > 1 else 0.0
        if top >= 0.55 and (top - second) >= 0.2:
            return "uniform"
        if top >= 0.4:
            return "moderately_uniform"
        return "mixed"

    def _olive_color_mask(self, patch_rgb: np.ndarray) -> np.ndarray:
        hsv = cv2.cvtColor(patch_rgb, cv2.COLOR_RGB2HSV)
        h = hsv[:, :, 0]
        s = hsv[:, :, 1]
        v = hsv[:, :, 2]

        green = (h >= 25) & (h <= 95) & (s > 35) & (v > 30)
        yellow = (h >= 10) & (h <= 40) & (s > 45) & (v > 55)
        purple = (((h >= 120) & (h <= 179)) | (h <= 12)) & (s > 25) & (v > 20)
        dark_ripe = (v < 65) & (s < 150)
        return (green | yellow | purple | dark_ripe)

    def _extract_olive_focus_pixels(self, image_np: np.ndarray) -> tuple[np.ndarray, OliveFocusStats]:
        stats = OliveFocusStats(detector_ready=self.detector is not None)
        if self.detector is None:
            return image_np, stats

        try:
            results = self.detector.predict(
                source=image_np,
                conf=0.30,
                iou=0.45,
                imgsz=960,
                augment=False,
                verbose=False,
            )
        except Exception:
            return image_np, stats

        if not results or results[0].boxes is None or len(results[0].boxes) == 0:
            return image_np, stats

        confs = results[0].boxes.conf.cpu().numpy()
        boxes = results[0].boxes.xyxy.cpu().numpy()
        patches: list[np.ndarray] = []
        patch_confs: list[float] = []
        h, w = image_np.shape[:2]
        image_area = float(max(1, h * w))
        min_area = max(80.0, image_area * 0.00015)
        max_area = image_area * 0.45
        total_box_area = 0.0

        for box, conf in zip(boxes, confs):
            x1, y1, x2, y2 = [int(max(0, round(v))) for v in box.tolist()]
            x1 = min(x1, w - 1)
            x2 = min(x2, w)
            y1 = min(y1, h - 1)
            y2 = min(y2, h)
            if x2 <= x1 or y2 <= y1:
                continue
            width = x2 - x1
            height = y2 - y1
            if height <= 0:
                continue
            area = float(width * height)
            if area < min_area or area > max_area:
                continue
            aspect = float(width) / float(height)
            if aspect < 0.2 or aspect > 4.0:
                continue
            patch = image_np[y1:y2, x1:x2]
            if patch.size == 0:
                continue

            color_mask = self._olive_color_mask(patch)
            mask_ratio = float(np.mean(color_mask))
            if mask_ratio > 0.03:
                masked = patch[color_mask]
                if masked.size > 0:
                    patches.append(masked.reshape(-1, 3))
                else:
                    patches.append(patch.reshape(-1, 3))
            else:
                patches.append(patch.reshape(-1, 3))
            patch_confs.append(float(conf))
            total_box_area += area

        if not patches:
            return image_np, stats

        stacked = np.concatenate(patches, axis=0)
        stats.detected_olives = len(patches)
        stats.avg_confidence = float(np.mean(patch_confs)) if patch_confs else 0.0
        stats.fruit_area_ratio = float(np.clip(total_box_area / image_area, 0.0, 1.0))
        stats.full_image_fallback = False
        return stacked.reshape(-1, 1, 3), stats

    def _skin_mi_from_color(self, h: np.ndarray, s: np.ndarray, v: np.ndarray) -> tuple[float, bool]:
        green = float(np.mean((h >= 30) & (h <= 95) & (s > 25) & (v > 35)))
        yellow = float(np.mean((h >= 15) & (h <= 40) & (s > 40) & (v > 55)))
        purple_core = (h >= 110) & (h <= 179) & (s > 20) & (v > 20)
        purple_wrap = (h <= 12) & (s > 45) & (v > 20)
        purple = float(np.mean(purple_core | purple_wrap))
        green_zone = (h >= 25) & (h <= 95) & (s > 25)
        yellow_zone = (h >= 10) & (h <= 45) & (s > 30)
        dark_low = v < 70
        dark_low_sat = dark_low & (s < 60)
        dark_ripe_hue = ((h >= 90) & (h <= 179)) | (h <= 12)
        dark_purple = (v < 95) & (s > 35) & dark_ripe_hue
        blackish = float(np.mean((dark_low_sat | dark_purple) & (~green_zone) & (~yellow_zone)))
        early_dominance = (green + yellow) >= 0.55 and blackish < 0.42

        if not early_dominance and blackish > 0.60:
            return 5.3, True
        if not early_dominance and blackish > 0.48:
            return 4.8, True
        if purple > 0.45:
            return 3.4, False
        if purple > 0.20:
            return 2.6, False
        if purple > 0.10:
            return 2.3, False
        if yellow > 0.20 and green > 0.35:
            return 1.4, False
        if green > 0.55:
            return 0.7, False
        return 2.1, False

    def _extract_surrogate_measurements(
        self,
        image_np: np.ndarray,
        sample_date: str | None,
        week_no: int | None,
        use_detector: bool = True,
    ) -> tuple[dict[str, Any], float, float, bool, OliveFocusStats, np.ndarray]:
        if use_detector:
            olive_focus, focus_stats = self._extract_olive_focus_pixels(image_np)
        else:
            olive_focus, focus_stats = image_np, OliveFocusStats(detector_ready=self.detector is not None)
        hsv = cv2.cvtColor(olive_focus, cv2.COLOR_RGB2HSV)
        gray_focus = cv2.cvtColor(olive_focus, cv2.COLOR_RGB2GRAY)

        h = hsv[:, :, 0].astype(np.float32)
        s = hsv[:, :, 1].astype(np.float32)
        v = hsv[:, :, 2].astype(np.float32)
        mi_skin_estimate, mi_uncertain = self._skin_mi_from_color(h, s, v)

        green_mask = ((h >= 30) & (h <= 95) & (s > 25) & (v > 35)).astype(np.uint8)
        yellow_mask = ((h >= 15) & (h <= 40) & (s > 40) & (v > 55)).astype(np.uint8)
        purple_core = ((h >= 110) & (h <= 179) & (s > 18) & (v > 18))
        purple_wrap = ((h <= 12) & (s > 45) & (v > 18))
        purple_mask = (purple_core | purple_wrap).astype(np.uint8)
        green_zone = ((h >= 25) & (h <= 95) & (s > 25))
        yellow_zone = ((h >= 10) & (h <= 45) & (s > 30))
        dark_low_sat = ((v < 70) & (s < 60))
        dark_ripe_hue = (((h >= 90) & (h <= 179)) | (h <= 12))
        dark_purple = ((v < 95) & (s > 35) & dark_ripe_hue)
        dark_mask = ((dark_low_sat | dark_purple) & (~green_zone) & (~yellow_zone)).astype(np.uint8)

        green_ratio = float(np.mean(green_mask))
        yellow_ratio = float(np.mean(yellow_mask))
        purple_ratio = float(np.mean(purple_mask))
        dark_ratio = float(np.mean(dark_mask))
        texture = float(np.std(cv2.Laplacian(gray_focus, cv2.CV_32F)) / 42.0)
        texture = float(np.clip(texture, 0, 1))

        # Higher means riper-looking fruit according to skin color transition.
        ripeness_index = float(
            np.clip(
                0.08 * yellow_ratio + 0.45 * purple_ratio + 0.62 * dark_ratio + 0.22 * (1 - green_ratio) + 0.08 * texture,
                0,
                1,
            )
        )

        base_capacitance = float(
            np.clip(
                52 + 52 * ripeness_index + 13 * (1 - green_ratio) + 8 * texture,
                35,
                140,
            )
        )

        rgb_means = olive_focus.reshape(-1, 3).mean(axis=0)
        r_mean, g_mean, b_mean = [float(x) for x in rgb_means]
        color_bias = float(np.clip((r_mean - g_mean) / 255.0, -0.25, 0.25))

        measurements: dict[str, Any] = {}
        for i in range(1, 16):
            wave = np.sin(i * 0.63) * 2.8 + np.cos(i * 0.21) * 1.9
            drift = (i - 8) * 0.18 * color_bias * 10
            val = base_capacitance + wave + drift
            measurements[f"Measurement {i}"] = round(float(np.clip(val, 30, 200)), 2)

        measurements["Average capacitance (nF)"] = round(
            float(np.mean([measurements[f"Measurement {i}"] for i in range(1, 16)])),
            2,
        )
        measurements["Set number"] = 1

        if week_no is not None:
            measurements["Week No."] = int(np.clip(week_no, 1, 52))
        else:
            measurements["Week No."] = int(np.clip(round(1 + ripeness_index * 5), 1, 52))

        parsed_date = None
        if sample_date:
            try:
                parsed_date = datetime.fromisoformat(sample_date)
            except ValueError:
                parsed_date = None
        if parsed_date is not None:
            measurements["Date"] = parsed_date.strftime("%Y-%m-%d")

        return measurements, ripeness_index, mi_skin_estimate, mi_uncertain, focus_stats, olive_focus
