from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np
from PIL import Image

from backend.services.image_io import decode_image_rgb
from backend.services.scene_classifier_service import SceneClassifierService
from backend.services.quality_service import ImageQualityService
from backend.services.vision_service import UNCERTAIN_DIAGNOSIS, VisionService


@dataclass(frozen=True)
class DiseaseExpertThresholds:
    # Keep hard-stop threshold practical for mobile uploads.
    min_resolution: int = 170
    blur_threshold: float = 70.0
    min_brightness: float = 45.0
    min_leaf_coverage: float = 0.045
    min_part_coverage: float = 0.035
    max_border_touch_ratio: float = 0.35
    min_symptom_signal: float = 0.16
    conflict_symptom_signal: float = 0.32
    min_diagnosis_confidence: float = 0.72
    uncertain_confidence_cap: float = 0.65
    leaf_override_min_coverage: float = 0.06
    leaf_override_center_coverage: float = 0.08
    leaf_override_min_symptom: float = 0.18
    leaf_override_leaf_vs_branch_ratio: float = 1.2
    likely_leaf_confidence_floor: float = 0.62
    no_symptom_signal_threshold: float = 0.09
    weak_symptom_signal_threshold: float = 0.16
    peacock_min_ring_ratio: float = 0.0028
    peacock_min_yellow_halo_ratio: float = 0.014
    peacock_min_lesion_area_ratio: float = 0.007
    peacock_min_lesion_count: int = 2
    max_shadow_for_peacock_without_halo: float = 0.27
    aculus_min_bronzing_ratio: float = 0.10


class DiseaseExpertService:
    def __init__(
        self,
        *,
        scene_classifier: SceneClassifierService,
        quality_service: ImageQualityService,
        vision_service: VisionService,
        thresholds: DiseaseExpertThresholds | None = None,
    ) -> None:
        self.scene_classifier = scene_classifier
        self.quality_service = quality_service
        self.vision_service = vision_service
        self.thresholds = thresholds or DiseaseExpertThresholds()

    def predict(self, *, image_bytes: bytes, image_name: str = "upload.jpg") -> dict[str, Any]:
        scene = self.scene_classifier.classify(image_bytes)
        scene_type = str(scene.get("scene_type", "unknown"))
        route_conf = float(np.clip(float(scene.get("confidence", 0.0) or 0.0), 0.0, 1.0))
        image_np = decode_image_rgb(image_bytes)
        part = self._map_scene_to_part(scene_type)
        part, route_override = self._prefer_leaf_foreground(
            image=image_np,
            part=part,
            scene_type=scene_type,
        )

        quality = self._run_quality_gate(image=image_np, part=part)
        if not quality["passed"]:
            return self._response(
                likely_disease="Uncertain",
                affected_part=part,
                confidence=min(route_conf, 0.45),
                status="needs_better_image",
                short_reason=quality["short_reason"],
                next_action="Upload a clearer close-up image with proper lighting and visible symptom area.",
                plant_part_route=part,
                route_confidence=route_conf,
                quality_gate=quality,
                severity="Unknown",
                warnings=(quality["failed_checks"] + ([route_override] if route_override else [])),
            )

        if part == "unclear":
            return self._response(
                likely_disease="Uncertain",
                affected_part=part,
                confidence=min(route_conf, 0.5),
                status="uncertain",
                short_reason="Plant part is unclear. The image cannot be routed reliably to a disease model.",
                next_action="Re-take one clear close-up of a leaf, fruit, or branch.",
                plant_part_route=part,
                route_confidence=route_conf,
                quality_gate=quality,
                severity="Unknown",
            )

        if part in {"fruit", "branch"}:
            return self._response(
                likely_disease="Uncertain",
                affected_part=part,
                confidence=min(route_conf, 0.55),
                status="unsupported_part",
                short_reason=f"{part.capitalize()} disease prediction is conservative until this part-specific dataset is stronger.",
                next_action="Upload a leaf close-up for reliable disease diagnosis, or proceed with agronomist review.",
                plant_part_route=part,
                route_confidence=route_conf,
                quality_gate=quality,
                severity="Unknown",
                warnings=[route_override] if route_override else None,
            )

        if route_override and scene_type != "leaf" and route_conf >= 0.80:
            return self._response(
                likely_disease="Uncertain",
                affected_part="leaf",
                confidence=min(route_conf, self.thresholds.uncertain_confidence_cap),
                status="uncertain",
                short_reason="Plant part routing is conflicting; supported leaf diagnosis is not reliable from this image.",
                next_action="Upload a clear close-up of one olive leaf. If the symptom is an insect or another plant part, use agronomist review.",
                plant_part_route="leaf",
                route_confidence=route_conf,
                quality_gate=quality,
                severity="Unknown",
                warnings=[route_override],
            )

        leaf_quality = self.quality_service.validate_and_crop(image_bytes)
        leaf_quality_warnings: list[str] = []
        if not leaf_quality.valid:
            # Secondary crop gate should not hard-stop valid field photos.
            # Continue with full image and reduce confidence later.
            leaf_quality_warnings.append(leaf_quality.message)
        # Keep inference on the full validated photo. Earlier leaf-mask crops could
        # isolate only bright lesion/edge regions and create false disease outputs.
        model_result = self.vision_service.analyze_image(image_bytes, image_name=image_name)
        model_conf = float(np.clip(float(model_result.get("disease_confidence", 0.0) or 0.0), 0.0, 1.0))
        predicted = str(model_result.get("disease", "Unknown"))
        severity = str(model_result.get("severity", "Unknown"))
        evidence = self._evaluate_symptom_evidence(
            predicted=predicted,
            model_conf=model_conf,
            quality=quality,
        )
        predicted = str(evidence["predicted"])
        model_conf = float(np.clip(float(evidence["confidence"]), 0.0, 1.0))
        if bool(evidence.get("force_mild_severity", False)) and severity.lower() in {"moderate", "severe", "high"}:
            severity = "Mild"

        symptom_signal = float(quality.get("symptom_signal", 0.0) or 0.0)
        conflict = self._is_conflict(predicted=predicted, symptom_signal=symptom_signal)
        final_conf = model_conf
        warnings: list[str] = list(evidence.get("warnings", []))
        if conflict:
            final_conf = min(final_conf, self.thresholds.uncertain_confidence_cap)
            warnings.append("Prediction conflicts with visible symptom evidence; confidence reduced.")
        if leaf_quality_warnings:
            final_conf = min(final_conf, 0.68)
            warnings.extend(leaf_quality_warnings)
        if route_override:
            warnings.append(route_override)

        no_disease_label = predicted in {"None", "No visible symptom"}
        uncertain_label = predicted == UNCERTAIN_DIAGNOSIS
        low_conf = final_conf < self.thresholds.min_diagnosis_confidence
        leaf_evidence_strong = (
            float(quality.get("symptom_signal", 0.0) or 0.0) >= self.thresholds.leaf_override_min_symptom
            and float(quality.get("metrics", {}).get("part_coverage", 0.0) or 0.0)
            >= (self.thresholds.min_leaf_coverage * 0.85)
        )
        allow_likely_leaf = (
            low_conf
            and (not uncertain_label)
            and predicted not in {"None", "Unknown"}
            and leaf_evidence_strong
            and final_conf >= self.thresholds.likely_leaf_confidence_floor
        )
        if allow_likely_leaf:
            final_conf = max(final_conf, self.thresholds.likely_leaf_confidence_floor)
            warnings.append("Strong visible leaf symptoms; returning likely diagnosis with conservative confidence.")
            low_conf = False

        if no_disease_label and conflict:
            return self._response(
                likely_disease="Uncertain",
                affected_part="leaf",
                confidence=min(final_conf, self.thresholds.uncertain_confidence_cap),
                status="uncertain",
                short_reason="Visible symptom evidence conflicts with a healthy/no-symptom output.",
                next_action="Upload another close-up from the affected area and a second angle.",
                plant_part_route="leaf",
                route_confidence=route_conf,
                quality_gate=quality,
                severity="Unknown",
                warnings=warnings,
            )

        if no_disease_label:
            likely_disease = "No clear disease detected" if predicted == "None" else "No visible symptom"
            short_reason = (
                "No strong disease pattern is visible in this leaf image."
                if predicted == "None"
                else "Leaf is visible but clear lesion evidence is weak."
            )
            next_action = (
                "Continue monitoring and rescan in 7 days or when symptoms appear."
                if predicted == "None"
                else "Capture another close-up if new spots appear; otherwise continue routine monitoring."
            )
            return self._response(
                likely_disease=likely_disease,
                affected_part="leaf",
                confidence=max(final_conf, 0.62),
                status="ok",
                short_reason=short_reason,
                next_action=next_action,
                plant_part_route="leaf",
                route_confidence=route_conf,
                quality_gate=quality,
                severity="Mild",
                warnings=warnings,
            )

        if uncertain_label or low_conf:
            return self._response(
                likely_disease="Uncertain",
                affected_part="leaf",
                confidence=min(final_conf, self.thresholds.uncertain_confidence_cap),
                status="uncertain",
                short_reason="Leaf evidence is not strong enough for a reliable diagnosis from this image.",
                next_action="Upload another clear close-up from an affected area and a second angle.",
                plant_part_route="leaf",
                route_confidence=route_conf,
                quality_gate=quality,
                severity="Unknown",
                warnings=warnings,
            )

        return self._response(
            likely_disease=predicted,
            affected_part="leaf",
            confidence=final_conf,
            status="ok",
            short_reason="Leaf symptoms and model evidence are consistent for this diagnosis.",
            next_action="Apply recommended management and rescan in 5-7 days.",
            plant_part_route="leaf",
            route_confidence=route_conf,
            quality_gate=quality,
            severity=severity,
            warnings=warnings,
        )

    def _run_quality_gate(self, *, image: np.ndarray, part: str) -> dict[str, Any]:
        height, width = image.shape[:2]
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        hsv = cv2.cvtColor(image, cv2.COLOR_RGB2HSV)

        blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        brightness = float(np.mean(hsv[:, :, 2]))

        part_mask = self._part_mask(image=image, part=part)
        coverage = float(np.mean(part_mask > 0))
        border_touch_ratio = self._border_touch_ratio(mask=part_mask)

        symptom_signal = 0.0
        no_visible_symptom = False
        if part == "leaf":
            feats = self.vision_service._extract_leaf_features(Image.fromarray(image).convert("RGB"))
            symptom_signal = float(feats.get("disease_signal", 0.0) or 0.0)
            no_visible_symptom = symptom_signal < self.thresholds.min_symptom_signal
        else:
            feats = {}

        checks = {
            "blur": blur_score >= self.thresholds.blur_threshold,
            "too_dark": brightness >= self.thresholds.min_brightness,
            "too_far": coverage >= (self.thresholds.min_leaf_coverage if part == "leaf" else self.thresholds.min_part_coverage),
            "bad_framing": border_touch_ratio <= self.thresholds.max_border_touch_ratio,
            "no_visible_symptom": (not no_visible_symptom) if part == "leaf" else True,
            "resolution": min(width, height) >= self.thresholds.min_resolution,
        }

        # Hard-stop only for truly unusable images. Keep other checks as strong warnings.
        hard_failed_checks: list[str] = []
        soft_failed_checks: list[str] = []

        if not checks["blur"]:
            hard_failed_checks.append("blur")
        if not checks["too_dark"]:
            hard_failed_checks.append("too_dark")
        if not checks["too_far"]:
            if part == "leaf" and symptom_signal >= self.thresholds.leaf_override_min_symptom:
                soft_failed_checks.append("too_far")
            else:
                hard_failed_checks.append("too_far")
        if not checks["resolution"]:
            hard_failed_checks.append("resolution")

        # Border touching can be normal for close-up disease photos.
        # Treat it as hard fail only when the subject is both clipped and not well represented.
        if not checks["bad_framing"]:
            # Leaf close-ups frequently touch frame borders in real field captures.
            # Keep this as warning for leaf routing, and stricter for other parts.
            if part == "leaf":
                soft_failed_checks.append("bad_framing")
            elif 0.06 <= coverage <= 0.85:
                hard_failed_checks.append("bad_framing")
            else:
                soft_failed_checks.append("bad_framing")

        # No-visible-symptom should not block scans; it should lower confidence and request another image.
        if not checks["no_visible_symptom"]:
            soft_failed_checks.append("no_visible_symptom")

        passed = len(hard_failed_checks) == 0
        failed_checks = hard_failed_checks + soft_failed_checks

        short_reason_map = {
            "blur": "Image is blurry.",
            "too_dark": "Image is too dark.",
            "too_far": "Plant part is too small in frame.",
            "bad_framing": "Framing is poor; subject is clipped or off-center.",
            "no_visible_symptom": "No visible symptom is clear in this image.",
            "resolution": "Image resolution is too low.",
        }
        short_reason = "Quality gate passed."
        if hard_failed_checks:
            short_reason = " ".join(short_reason_map.get(k, "Image quality issue detected.") for k in hard_failed_checks[:2])
        elif soft_failed_checks:
            short_reason = "Image is usable, but quality warnings may reduce diagnostic confidence."

        return {
            "passed": passed,
            "failed_checks": failed_checks,
            "hard_failed_checks": hard_failed_checks,
            "soft_failed_checks": soft_failed_checks,
            "short_reason": short_reason,
            "metrics": {
                "width": int(width),
                "height": int(height),
                "blur_score": round(blur_score, 3),
                "brightness": round(brightness, 3),
                "part_coverage": round(coverage, 4),
                "border_touch_ratio": round(border_touch_ratio, 4),
                "symptom_signal": round(symptom_signal, 4),
            },
            "leaf_features": {
                "lesion_count": float(feats.get("lesion_count", 0.0) or 0.0),
                "lesion_area_ratio": float(feats.get("lesion_area_ratio", 0.0) or 0.0),
                "yellow_halo_ratio": float(feats.get("yellow_halo_ratio", 0.0) or 0.0),
                "ring_ratio": float(feats.get("ring_ratio", 0.0) or 0.0),
                "necrotic_ratio": float(feats.get("necrotic_ratio", 0.0) or 0.0),
                "bronzing_ratio": float(feats.get("bronzing_ratio", 0.0) or 0.0),
                "peacock_signature": float(feats.get("peacock_signature", 0.0) or 0.0),
            },
            "thresholds": {
                "min_resolution": self.thresholds.min_resolution,
                "blur_threshold": self.thresholds.blur_threshold,
                "min_brightness": self.thresholds.min_brightness,
                "min_leaf_coverage": self.thresholds.min_leaf_coverage,
                "min_part_coverage": self.thresholds.min_part_coverage,
                "max_border_touch_ratio": self.thresholds.max_border_touch_ratio,
                "min_symptom_signal": self.thresholds.min_symptom_signal,
                "leaf_override_min_coverage": self.thresholds.leaf_override_min_coverage,
                "leaf_override_center_coverage": self.thresholds.leaf_override_center_coverage,
                "leaf_override_min_symptom": self.thresholds.leaf_override_min_symptom,
                "leaf_override_leaf_vs_branch_ratio": self.thresholds.leaf_override_leaf_vs_branch_ratio,
                "no_symptom_signal_threshold": self.thresholds.no_symptom_signal_threshold,
                "weak_symptom_signal_threshold": self.thresholds.weak_symptom_signal_threshold,
                "peacock_min_ring_ratio": self.thresholds.peacock_min_ring_ratio,
                "peacock_min_yellow_halo_ratio": self.thresholds.peacock_min_yellow_halo_ratio,
                "peacock_min_lesion_area_ratio": self.thresholds.peacock_min_lesion_area_ratio,
                "peacock_min_lesion_count": self.thresholds.peacock_min_lesion_count,
            },
            "symptom_signal": symptom_signal,
        }

    def _prefer_leaf_foreground(self, *, image: np.ndarray, part: str, scene_type: str) -> tuple[str, str | None]:
        if part == "leaf":
            return part, None

        leaf_mask = self.quality_service._leaf_mask(image)
        branch_mask = self._part_mask(image=image, part="branch")
        leaf_coverage = float(np.mean(leaf_mask > 0))
        branch_coverage = float(np.mean(branch_mask > 0))

        h, w = image.shape[:2]
        y1, y2 = int(h * 0.2), int(h * 0.8)
        x1, x2 = int(w * 0.2), int(w * 0.8)
        center_leaf = leaf_mask[y1:y2, x1:x2]
        center_branch = branch_mask[y1:y2, x1:x2]
        center_leaf_cov = float(np.mean(center_leaf > 0)) if center_leaf.size else 0.0
        center_branch_cov = float(np.mean(center_branch > 0)) if center_branch.size else 0.0

        feats = self.vision_service._extract_leaf_features(Image.fromarray(image).convert("RGB"))
        symptom_signal = float(feats.get("disease_signal", 0.0) or 0.0)

        dominant_center_leaf = (
            center_leaf_cov >= self.thresholds.leaf_override_center_coverage
            and center_leaf_cov >= (center_branch_cov * self.thresholds.leaf_override_leaf_vs_branch_ratio)
        )
        clear_leaf_symptom = (
            leaf_coverage >= self.thresholds.leaf_override_min_coverage
            and symptom_signal >= self.thresholds.leaf_override_min_symptom
        )

        if dominant_center_leaf or clear_leaf_symptom:
            reason = (
                f"Foreground symptomatic leaf override applied (scene={scene_type}, "
                f"leaf_cov={leaf_coverage:.3f}, center_leaf={center_leaf_cov:.3f})."
            )
            return "leaf", reason
        return part, None

    @staticmethod
    def _map_scene_to_part(scene_type: str) -> str:
        mapping = {
            "leaf": "leaf",
            "fruit_closeup": "fruit",
            "orchard_branch": "branch",
            "harvest_pile": "unclear",
            "unknown": "unclear",
        }
        return mapping.get(scene_type, "unclear")

    def _part_mask(self, *, image: np.ndarray, part: str) -> np.ndarray:
        hsv = cv2.cvtColor(image, cv2.COLOR_RGB2HSV)
        if part == "leaf":
            return self.quality_service._leaf_mask(image)
        if part == "fruit":
            green = cv2.inRange(hsv, (25, 30, 25), (95, 255, 255))
            yellow = cv2.inRange(hsv, (10, 30, 35), (38, 255, 255))
            dark = cv2.inRange(hsv, (0, 0, 0), (180, 120, 80))
            return cv2.bitwise_or(cv2.bitwise_or(green, yellow), dark)
        if part == "branch":
            brown1 = cv2.inRange(hsv, (5, 25, 20), (28, 255, 180))
            brown2 = cv2.inRange(hsv, (0, 10, 10), (15, 255, 150))
            return cv2.bitwise_or(brown1, brown2)
        # fallback foreground-ish mask
        sat = cv2.inRange(hsv, (0, 25, 15), (180, 255, 255))
        return sat

    @staticmethod
    def _border_touch_ratio(*, mask: np.ndarray) -> float:
        if mask.size == 0:
            return 1.0
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return 1.0
        largest = max(contours, key=cv2.contourArea)
        x, y, w, h = cv2.boundingRect(largest)
        h_img, w_img = mask.shape[:2]
        margin_x = int(w_img * 0.04)
        margin_y = int(h_img * 0.04)
        touch_count = 0
        if x <= margin_x:
            touch_count += 1
        if y <= margin_y:
            touch_count += 1
        if (x + w) >= (w_img - margin_x):
            touch_count += 1
        if (y + h) >= (h_img - margin_y):
            touch_count += 1
        return float(touch_count / 4.0)

    def _is_conflict(self, *, predicted: str, symptom_signal: float) -> bool:
        predicted_lower = predicted.lower().strip()
        if predicted_lower in {"none", "no visible symptom", "no clear disease detected", "healthy leaf"}:
            return symptom_signal >= self.thresholds.conflict_symptom_signal
        if predicted == UNCERTAIN_DIAGNOSIS:
            return False
        return symptom_signal < (self.thresholds.min_symptom_signal * 0.7)

    def _evaluate_symptom_evidence(
        self,
        *,
        predicted: str,
        model_conf: float,
        quality: dict[str, Any],
    ) -> dict[str, Any]:
        predicted_text = str(predicted or "Unknown")
        predicted_lower = predicted_text.lower().strip()
        symptom_signal = float(quality.get("symptom_signal", 0.0) or 0.0)
        leaf_features = quality.get("leaf_features", {}) or {}
        metrics = quality.get("metrics", {}) or {}

        lesion_count = float(leaf_features.get("lesion_count", 0.0) or 0.0)
        lesion_area_ratio = float(leaf_features.get("lesion_area_ratio", 0.0) or 0.0)
        yellow_halo_ratio = float(leaf_features.get("yellow_halo_ratio", 0.0) or 0.0)
        ring_ratio = float(leaf_features.get("ring_ratio", 0.0) or 0.0)
        bronzing_ratio = float(leaf_features.get("bronzing_ratio", 0.0) or 0.0)
        peacock_signature = float(leaf_features.get("peacock_signature", 0.0) or 0.0)
        brightness = float(metrics.get("brightness", 0.0) or 0.0)

        quality_soft_fail = set(quality.get("soft_failed_checks", []) or [])
        no_symptom = (
            symptom_signal < self.thresholds.no_symptom_signal_threshold
            and lesion_count < 2
            and ring_ratio < self.thresholds.peacock_min_ring_ratio
            and yellow_halo_ratio < self.thresholds.peacock_min_yellow_halo_ratio
        )
        weak_evidence = (
            symptom_signal < self.thresholds.weak_symptom_signal_threshold
            and ring_ratio < self.thresholds.peacock_min_ring_ratio
            and yellow_halo_ratio < self.thresholds.peacock_min_yellow_halo_ratio
            and lesion_area_ratio < self.thresholds.peacock_min_lesion_area_ratio
        )
        strong_peacock_shape = (
            peacock_signature >= 0.5
            or (
                lesion_count >= self.thresholds.peacock_min_lesion_count
                and lesion_area_ratio >= self.thresholds.peacock_min_lesion_area_ratio
                and (
                    ring_ratio >= self.thresholds.peacock_min_ring_ratio
                    or yellow_halo_ratio >= self.thresholds.peacock_min_yellow_halo_ratio
                )
            )
        )
        shadow_like_darkness = (
            brightness < 85.0
            and ring_ratio < self.thresholds.peacock_min_ring_ratio
            and yellow_halo_ratio < self.thresholds.peacock_min_yellow_halo_ratio
        )
        peacock_supported = strong_peacock_shape and (not shadow_like_darkness or symptom_signal >= 0.20)
        aculus_supported = (
            bronzing_ratio >= self.thresholds.aculus_min_bronzing_ratio
            or symptom_signal >= self.thresholds.weak_symptom_signal_threshold
        )

        warnings: list[str] = []
        out_label = predicted_text
        out_conf = float(model_conf)
        force_mild_severity = False

        if "peacock" in predicted_lower or "spilocaea" in predicted_lower:
            if not peacock_supported:
                if no_symptom or "no_visible_symptom" in quality_soft_fail:
                    out_label = "No visible symptom"
                    out_conf = min(out_conf, 0.62)
                    warnings.append("Peacock spot suppressed: visible lesion evidence is weak.")
                    force_mild_severity = True
                elif weak_evidence:
                    out_label = UNCERTAIN_DIAGNOSIS
                    out_conf = min(out_conf, self.thresholds.uncertain_confidence_cap)
                    warnings.append("Peacock spot confidence reduced: lesion pattern is not clearly supported.")
                    force_mild_severity = True

        if "aculus" in predicted_lower or "olearius" in predicted_lower:
            if not aculus_supported:
                if no_symptom:
                    out_label = "No visible symptom"
                    out_conf = min(out_conf, 0.62)
                    warnings.append("Aculus diagnosis suppressed: bronzing/symptom evidence is weak.")
                    force_mild_severity = True
                elif weak_evidence:
                    out_label = UNCERTAIN_DIAGNOSIS
                    out_conf = min(out_conf, self.thresholds.uncertain_confidence_cap)
                    warnings.append("Aculus confidence reduced: visible symptom evidence is limited.")
                    force_mild_severity = True

        if (
            out_label not in {UNCERTAIN_DIAGNOSIS, "None", "No visible symptom"}
            and ("healthy" not in out_label.lower())
            and weak_evidence
        ):
            out_label = UNCERTAIN_DIAGNOSIS
            out_conf = min(out_conf, self.thresholds.uncertain_confidence_cap)
            warnings.append("Diagnosis downgraded: symptom evidence is weak for a reliable disease label.")
            force_mild_severity = True

        return {
            "predicted": out_label,
            "confidence": out_conf,
            "warnings": warnings,
            "force_mild_severity": force_mild_severity,
        }

    @staticmethod
    def _confidence_label(confidence: float) -> str:
        if confidence >= 0.85:
            return "High"
        if confidence >= 0.70:
            return "Medium"
        return "Low"

    @staticmethod
    def _normalize_disease_key(label: str) -> str:
        text = str(label or "").strip().lower()
        if text in {"healthy leaf", "healthy_leaf"}:
            return "healthy_leaf"
        if "peacock" in text or "spilocaea" in text:
            return "olive_peacock_spot"
        if "aculus" in text or "olearius" in text:
            return "aculus_olearius"
        if "no visible symptom" in text:
            return "no_visible_symptom"
        if text in {"none", "no clear disease detected"}:
            return "healthy_leaf"
        return "uncertain_leaf"

    @staticmethod
    def _normalize_part_key(part: str) -> str:
        text = str(part or "").strip().lower().replace(" ", "_")
        if text in {"leaf", "fruit", "branch", "branch_twig", "unclear"}:
            return text
        return "unknown"

    @staticmethod
    def _reason_key(reason: str, *, part_key: str) -> str:
        text = str(reason or "").strip().lower()
        if "proper lighting" in text or "visible symptom area" in text:
            return "quality_image_closer"
        if "cannot be routed reliably" in text or "part is unclear" in text:
            return "part_unclear"
        if "routing is conflicting" in text:
            return "routing_conflict"
        if "dataset is stronger" in text and part_key == "fruit":
            return "fruit_conservative"
        if "dataset is stronger" in text and part_key == "branch":
            return "branch_conservative"
        if "conflicts with a healthy" in text:
            return "conflict_visible_evidence"
        if "no strong disease pattern" in text:
            return "no_strong_pattern"
        if "lesion evidence is weak" in text:
            return "weak_lesion_evidence"
        if "not strong enough" in text:
            return "not_enough_leaf_evidence"
        if "model evidence are consistent" in text:
            return "consistent_leaf_model"
        return ""

    @staticmethod
    def _action_key(action: str) -> str:
        text = str(action or "").strip().lower()
        if "re-take one clear close-up" in text:
            return "retake_closeup"
        if "upload a leaf close-up" in text:
            return "upload_leaf_closeup"
        if "second angle" in text and "another close-up from the affected area" in text:
            return "upload_second_angle"
        if "continue monitoring and rescan" in text:
            return "monitor_rescan"
        if "new spots appear" in text:
            return "capture_if_new_spots"
        if "another clear close-up" in text:
            return "upload_clear_closeup"
        if "apply recommended management" in text:
            return "apply_management"
        if "insect or another plant part" in text:
            return "upload_leaf_or_review"
        return ""

    def _response(
        self,
        *,
        likely_disease: str,
        affected_part: str,
        confidence: float,
        status: str,
        short_reason: str,
        next_action: str,
        plant_part_route: str,
        route_confidence: float,
        quality_gate: dict[str, Any],
        severity: str,
        warnings: list[str] | None = None,
    ) -> dict[str, Any]:
        conf = float(np.clip(confidence, 0.0, 1.0))
        confidence_label = self._confidence_label(conf)
        disease_key = self._normalize_disease_key(likely_disease)
        part_key = self._normalize_part_key(affected_part)
        severity_key = str(severity or "unknown").strip().lower().replace(" ", "_")
        reason_key = self._reason_key(short_reason, part_key=part_key)
        action_key = self._action_key(next_action)
        return {
            "likely_disease": likely_disease,
            "likely_disease_key": disease_key,
            "affected_part": affected_part,
            "affected_part_key": part_key,
            "confidence": round(conf, 4),
            "confidence_label": confidence_label,
            "confidence_label_key": confidence_label.lower(),
            "short_reason": short_reason,
            "short_reason_key": reason_key or None,
            "next_action": next_action,
            "next_action_key": action_key or None,
            "status": status,
            "status_key": str(status or "").strip().lower(),
            "plant_part_route": plant_part_route,
            "route_confidence": round(float(np.clip(route_confidence, 0.0, 1.0)), 4),
            "severity": severity,
            "severity_key": severity_key,
            "quality_gate": quality_gate,
            "warnings": warnings or [],
            "model_used": "DiseaseExpertService-v1",
        }
