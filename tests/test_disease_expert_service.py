from __future__ import annotations

import io
import unittest
from types import SimpleNamespace

import cv2
import numpy as np
from PIL import Image

from backend.services.disease_expert_service import DiseaseExpertService, DiseaseExpertThresholds


class _FakeSceneClassifier:
    def __init__(self, scene_type: str, confidence: float = 0.9) -> None:
        self.scene_type = scene_type
        self.confidence = confidence

    def classify(self, image_bytes: bytes):  # noqa: ANN001
        return {"scene_type": self.scene_type, "confidence": self.confidence}


class _FakeQualityService:
    def validate_and_crop(self, image_bytes: bytes):  # noqa: ANN001
        return SimpleNamespace(
            valid=True,
            message="ok",
            blur_score=120.0,
            width=512,
            height=512,
            leaf_detected=True,
            cropped_image_bytes=image_bytes,
        )

    def _leaf_mask(self, image_np: np.ndarray) -> np.ndarray:
        hsv = cv2.cvtColor(image_np, cv2.COLOR_RGB2HSV)
        return cv2.inRange(hsv, (20, 25, 25), (95, 255, 255))


class _FakeQualityServiceSoftCropFail(_FakeQualityService):
    def validate_and_crop(self, image_bytes: bytes):  # noqa: ANN001
        return SimpleNamespace(
            valid=False,
            message="Image resolution too low. Upload a higher-resolution leaf photo.",
            blur_score=120.0,
            width=250,
            height=180,
            leaf_detected=True,
            cropped_image_bytes=None,
        )


class _FakeQualityServiceNoLeaf(_FakeQualityService):
    def _leaf_mask(self, image_np: np.ndarray) -> np.ndarray:  # noqa: ARG002
        return np.zeros(image_np.shape[:2], dtype=np.uint8)


class _FakeVisionService:
    def __init__(
        self,
        *,
        disease: str,
        confidence: float,
        severity: str,
        symptom_signal: float,
        feature_overrides: dict[str, float] | None = None,
    ) -> None:
        self.disease = disease
        self.confidence = confidence
        self.severity = severity
        self.symptom_signal = symptom_signal
        self.feature_overrides = feature_overrides or {}

    def analyze_image(self, image_bytes: bytes, image_name: str = "upload.jpg"):  # noqa: ARG002
        return {
            "disease": self.disease,
            "disease_confidence": self.confidence,
            "severity": self.severity,
        }

    def _extract_leaf_features(self, image: Image.Image):  # noqa: ARG002
        disease_lower = self.disease.lower()
        features = {
            "disease_signal": self.symptom_signal,
            "lesion_count": 0.0,
            "lesion_area_ratio": 0.0,
            "yellow_halo_ratio": 0.0,
            "ring_ratio": 0.0,
            "necrotic_ratio": 0.0,
            "bronzing_ratio": 0.0,
            "peacock_signature": 0.0,
        }
        if "peacock" in disease_lower or "spilocaea" in disease_lower:
            features.update(
                {
                    "lesion_count": 4.0,
                    "lesion_area_ratio": 0.018,
                    "yellow_halo_ratio": 0.03,
                    "ring_ratio": 0.006,
                    "peacock_signature": 1.0,
                }
            )
        elif "aculus" in disease_lower or "olearius" in disease_lower:
            features.update(
                {
                    "lesion_count": 1.0,
                    "lesion_area_ratio": 0.008,
                    "bronzing_ratio": 0.17,
                    "peacock_signature": 0.0,
                }
            )
        features.update(self.feature_overrides)
        return features


def _image_bytes(*, rgb: tuple[int, int, int], size: int = 512, noise: bool = False) -> bytes:
    arr = np.zeros((size, size, 3), dtype=np.uint8)
    arr[:, :, 0] = rgb[0]
    arr[:, :, 1] = rgb[1]
    arr[:, :, 2] = rgb[2]
    if noise:
        jitter = np.random.default_rng(42).integers(-30, 30, size=arr.shape, dtype=np.int16)
        arr = np.clip(arr.astype(np.int16) + jitter, 0, 255).astype(np.uint8)
    image = Image.fromarray(arr, mode="RGB")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _orchard_leaf_scene_bytes(*, lesion_style: str = "peacock", size: int = 640, off_center: bool = False) -> bytes:
    arr = np.full((size, size, 3), fill_value=[160, 190, 170], dtype=np.uint8)
    # Subtle texture for non-zero blur variance.
    noise = np.random.default_rng(7).integers(-20, 20, size=arr.shape, dtype=np.int16)
    arr = np.clip(arr.astype(np.int16) + noise, 0, 255).astype(np.uint8)

    # Background branch network.
    branch_color = (120, 88, 58)  # RGB
    cv2.line(arr, (40, 480), (600, 130), branch_color, 12, lineType=cv2.LINE_AA)
    cv2.line(arr, (120, 560), (520, 230), branch_color, 8, lineType=cv2.LINE_AA)

    # Foreground leaf area (dominant subject).
    center = (430, 300) if off_center else (330, 320)
    axes = (220, 110)
    leaf_color = (74, 148, 70)  # RGB
    cv2.ellipse(arr, center, axes, -18, 0, 360, leaf_color, -1, lineType=cv2.LINE_AA)
    cv2.ellipse(arr, center, axes, -18, 0, 360, (92, 166, 86), 3, lineType=cv2.LINE_AA)

    if lesion_style == "peacock":
        # Dark circular lesions with yellow-ish halos.
        for x, y, r in [(280, 310, 15), (350, 290, 13), (390, 345, 12), (455, 305, 11)]:
            cv2.circle(arr, (x, y), r + 3, (165, 175, 90), -1, lineType=cv2.LINE_AA)
            cv2.circle(arr, (x, y), r, (60, 50, 35), -1, lineType=cv2.LINE_AA)
    elif lesion_style == "aculus":
        # Bronzing/stipple pattern.
        for x in range(220, 500, 16):
            for y in range(250, 390, 14):
                cv2.circle(arr, (x, y), 2, (138, 118, 70), -1, lineType=cv2.LINE_AA)
    elif lesion_style == "healthy":
        # Keep mostly clean.
        pass

    image = Image.fromarray(arr, mode="RGB")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


class DiseaseExpertServiceTests(unittest.TestCase):
    def test_quality_gate_stops_blurry_image(self) -> None:
        service = DiseaseExpertService(
            scene_classifier=_FakeSceneClassifier("leaf", 0.92),
            quality_service=_FakeQualityService(),
            vision_service=_FakeVisionService(
                disease="Olive Peacock Spot (Spilocaea oleaginea)",
                confidence=0.95,
                severity="Moderate",
                symptom_signal=0.45,
            ),
            thresholds=DiseaseExpertThresholds(min_symptom_signal=0.01),
        )
        # Flat image => very low Laplacian variance => blur fail.
        payload = service.predict(image_bytes=_image_bytes(rgb=(40, 130, 40), noise=False))
        self.assertEqual(payload["status"], "needs_better_image")
        self.assertIn("blur", payload["quality_gate"]["failed_checks"])

    def test_routes_branch_to_conservative_fallback(self) -> None:
        service = DiseaseExpertService(
            scene_classifier=_FakeSceneClassifier("orchard_branch", 0.88),
            quality_service=_FakeQualityServiceNoLeaf(),
            vision_service=_FakeVisionService(
                disease="Olive Peacock Spot (Spilocaea oleaginea)",
                confidence=0.92,
                severity="Moderate",
                symptom_signal=0.05,
            ),
            thresholds=DiseaseExpertThresholds(
                blur_threshold=0.0,
                min_brightness=0.0,
                min_part_coverage=0.0,
                max_border_touch_ratio=1.0,
                min_symptom_signal=0.0,
            ),
        )
        payload = service.predict(image_bytes=_image_bytes(rgb=(120, 80, 50), noise=True))
        self.assertEqual(payload["status"], "unsupported_part")
        self.assertEqual(payload["affected_part"], "branch")
        self.assertEqual(payload["likely_disease"], "Uncertain")

    def test_obvious_peacock_leaf_in_orchard_background_routes_to_leaf(self) -> None:
        service = DiseaseExpertService(
            scene_classifier=_FakeSceneClassifier("orchard_branch", 0.91),
            quality_service=_FakeQualityService(),
            vision_service=_FakeVisionService(
                disease="Olive Peacock Spot (Spilocaea oleaginea)",
                confidence=0.86,
                severity="Moderate",
                symptom_signal=0.58,
            ),
            thresholds=DiseaseExpertThresholds(),
        )
        payload = service.predict(image_bytes=_orchard_leaf_scene_bytes(lesion_style="peacock"))
        self.assertEqual(payload["plant_part_route"], "leaf")
        self.assertEqual(payload["affected_part"], "leaf")
        self.assertEqual(payload["status"], "ok")
        self.assertIn("Peacock Spot", payload["likely_disease"])

    def test_obvious_healthy_leaf_in_orchard_background_routes_to_leaf(self) -> None:
        service = DiseaseExpertService(
            scene_classifier=_FakeSceneClassifier("orchard_branch", 0.87),
            quality_service=_FakeQualityService(),
            vision_service=_FakeVisionService(
                disease="None",
                confidence=0.88,
                severity="Mild",
                symptom_signal=0.08,
            ),
            thresholds=DiseaseExpertThresholds(),
        )
        payload = service.predict(image_bytes=_orchard_leaf_scene_bytes(lesion_style="healthy"))
        self.assertEqual(payload["plant_part_route"], "leaf")
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["likely_disease"], "No clear disease detected")

    def test_obvious_aculus_leaf_in_orchard_background_routes_to_leaf(self) -> None:
        service = DiseaseExpertService(
            scene_classifier=_FakeSceneClassifier("orchard_branch", 0.89),
            quality_service=_FakeQualityService(),
            vision_service=_FakeVisionService(
                disease="Aculus Olearius (olive mite damage)",
                confidence=0.84,
                severity="Moderate",
                symptom_signal=0.42,
            ),
            thresholds=DiseaseExpertThresholds(),
        )
        payload = service.predict(image_bytes=_orchard_leaf_scene_bytes(lesion_style="aculus"))
        self.assertEqual(payload["plant_part_route"], "leaf")
        self.assertEqual(payload["status"], "ok")
        self.assertIn("Aculus", payload["likely_disease"])

    def test_leaf_foreground_dominant_with_branch_background_is_not_forced_to_branch(self) -> None:
        service = DiseaseExpertService(
            scene_classifier=_FakeSceneClassifier("orchard_branch", 0.9),
            quality_service=_FakeQualityService(),
            vision_service=_FakeVisionService(
                disease="Olive Peacock Spot (Spilocaea oleaginea)",
                confidence=0.82,
                severity="Moderate",
                symptom_signal=0.48,
            ),
            thresholds=DiseaseExpertThresholds(),
        )
        payload = service.predict(image_bytes=_orchard_leaf_scene_bytes(lesion_style="peacock", off_center=True))
        self.assertEqual(payload["plant_part_route"], "leaf")
        self.assertNotEqual(payload["status"], "unsupported_part")
        self.assertNotEqual(payload["status"], "needs_better_image")

    def test_low_confidence_leaf_returns_uncertain(self) -> None:
        service = DiseaseExpertService(
            scene_classifier=_FakeSceneClassifier("leaf", 0.93),
            quality_service=_FakeQualityService(),
            vision_service=_FakeVisionService(
                disease="Olive Peacock Spot (Spilocaea oleaginea)",
                confidence=0.58,
                severity="Moderate",
                symptom_signal=0.50,
            ),
            thresholds=DiseaseExpertThresholds(
                blur_threshold=0.0,
                min_brightness=0.0,
                min_leaf_coverage=0.0,
                max_border_touch_ratio=1.0,
                min_symptom_signal=0.01,
                min_diagnosis_confidence=0.72,
            ),
        )
        payload = service.predict(image_bytes=_image_bytes(rgb=(50, 150, 50), noise=True))
        self.assertEqual(payload["status"], "uncertain")
        self.assertEqual(payload["likely_disease"], "Uncertain")

    def test_unclear_scene_returns_uncertain(self) -> None:
        service = DiseaseExpertService(
            scene_classifier=_FakeSceneClassifier("unknown", 0.44),
            quality_service=_FakeQualityServiceNoLeaf(),
            vision_service=_FakeVisionService(
                disease="Olive Peacock Spot (Spilocaea oleaginea)",
                confidence=0.95,
                severity="Moderate",
                symptom_signal=0.05,
            ),
            thresholds=DiseaseExpertThresholds(
                blur_threshold=0.0,
                min_brightness=0.0,
                min_part_coverage=0.0,
                max_border_touch_ratio=1.0,
                min_symptom_signal=0.0,
            ),
        )
        payload = service.predict(image_bytes=_image_bytes(rgb=(90, 90, 90), noise=True))
        self.assertEqual(payload["status"], "uncertain")
        self.assertEqual(payload["affected_part"], "unclear")

    def test_conflict_between_model_and_visible_evidence_reduces_confidence(self) -> None:
        service = DiseaseExpertService(
            scene_classifier=_FakeSceneClassifier("leaf", 0.90),
            quality_service=_FakeQualityService(),
            vision_service=_FakeVisionService(
                disease="None",
                confidence=0.93,
                severity="Mild",
                symptom_signal=0.55,
            ),
            thresholds=DiseaseExpertThresholds(
                blur_threshold=0.0,
                min_brightness=0.0,
                min_leaf_coverage=0.0,
                max_border_touch_ratio=1.0,
                min_symptom_signal=0.01,
                min_diagnosis_confidence=0.72,
                uncertain_confidence_cap=0.65,
            ),
        )
        payload = service.predict(image_bytes=_image_bytes(rgb=(50, 140, 50), noise=True))
        self.assertEqual(payload["status"], "uncertain")
        self.assertLessEqual(payload["confidence"], 0.65)
        self.assertTrue(any("confidence reduced" in warning.lower() for warning in payload["warnings"]))

    def test_soft_crop_quality_failure_does_not_hard_stop_scan(self) -> None:
        service = DiseaseExpertService(
            scene_classifier=_FakeSceneClassifier("leaf", 0.90),
            quality_service=_FakeQualityServiceSoftCropFail(),
            vision_service=_FakeVisionService(
                disease="Olive Peacock Spot (Spilocaea oleaginea)",
                confidence=0.91,
                severity="Moderate",
                symptom_signal=0.5,
            ),
            thresholds=DiseaseExpertThresholds(
                blur_threshold=0.0,
                min_brightness=0.0,
                min_leaf_coverage=0.0,
                max_border_touch_ratio=1.0,
                min_symptom_signal=0.01,
                min_diagnosis_confidence=0.72,
            ),
        )
        payload = service.predict(image_bytes=_image_bytes(rgb=(45, 145, 45), noise=True))
        self.assertNotEqual(payload["status"], "needs_better_image")
        self.assertTrue(any("resolution too low" in warning.lower() for warning in payload["warnings"]))

    def test_off_center_leaf_with_clear_symptoms_is_not_rejected_for_framing(self) -> None:
        service = DiseaseExpertService(
            scene_classifier=_FakeSceneClassifier("leaf", 0.9),
            quality_service=_FakeQualityService(),
            vision_service=_FakeVisionService(
                disease="Olive Peacock Spot (Spilocaea oleaginea)",
                confidence=0.76,
                severity="Moderate",
                symptom_signal=0.44,
            ),
            thresholds=DiseaseExpertThresholds(),
        )
        payload = service.predict(image_bytes=_orchard_leaf_scene_bytes(lesion_style="peacock", off_center=True))
        self.assertNotEqual(payload["status"], "needs_better_image")

    def test_peacock_false_positive_is_blocked_when_lesion_evidence_is_weak(self) -> None:
        service = DiseaseExpertService(
            scene_classifier=_FakeSceneClassifier("leaf", 0.93),
            quality_service=_FakeQualityService(),
            vision_service=_FakeVisionService(
                disease="Olive Peacock Spot (Spilocaea oleaginea)",
                confidence=0.93,
                severity="Moderate",
                symptom_signal=0.05,
                feature_overrides={
                    "lesion_count": 0.0,
                    "lesion_area_ratio": 0.001,
                    "yellow_halo_ratio": 0.001,
                    "ring_ratio": 0.0004,
                    "peacock_signature": 0.0,
                    "bronzing_ratio": 0.01,
                },
            ),
            thresholds=DiseaseExpertThresholds(
                blur_threshold=0.0,
                min_brightness=0.0,
                min_leaf_coverage=0.0,
                max_border_touch_ratio=1.0,
                min_symptom_signal=0.01,
            ),
        )
        payload = service.predict(image_bytes=_image_bytes(rgb=(70, 150, 70), noise=True))
        self.assertEqual(payload["status"], "ok")
        self.assertIn(payload["likely_disease"], {"No visible symptom", "No clear disease detected"})
        self.assertEqual(payload["severity"], "Mild")

    def test_weak_symptom_image_returns_uncertain_leaf(self) -> None:
        service = DiseaseExpertService(
            scene_classifier=_FakeSceneClassifier("leaf", 0.92),
            quality_service=_FakeQualityService(),
            vision_service=_FakeVisionService(
                disease="Olive Peacock Spot (Spilocaea oleaginea)",
                confidence=0.79,
                severity="Moderate",
                symptom_signal=0.12,
                feature_overrides={
                    "lesion_count": 1.0,
                    "lesion_area_ratio": 0.004,
                    "yellow_halo_ratio": 0.006,
                    "ring_ratio": 0.0012,
                    "peacock_signature": 0.0,
                },
            ),
            thresholds=DiseaseExpertThresholds(
                blur_threshold=0.0,
                min_brightness=0.0,
                min_leaf_coverage=0.0,
                max_border_touch_ratio=1.0,
                min_symptom_signal=0.01,
            ),
        )
        payload = service.predict(image_bytes=_image_bytes(rgb=(75, 145, 75), noise=True))
        self.assertEqual(payload["status"], "uncertain")
        self.assertEqual(payload["likely_disease"], "Uncertain")
        self.assertEqual(payload["severity"], "Unknown")


if __name__ == "__main__":
    unittest.main()
