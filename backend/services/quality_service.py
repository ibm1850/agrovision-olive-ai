from __future__ import annotations

import io
from dataclasses import dataclass

import cv2
import numpy as np
from PIL import Image

from backend.services.image_io import decode_image_rgb


@dataclass
class QualityResult:
    valid: bool
    message: str
    blur_score: float
    width: int
    height: int
    leaf_detected: bool
    cropped_image_bytes: bytes | None = None


class ImageQualityService:
    def __init__(self, min_resolution: int = 224, blur_threshold: float = 75.0) -> None:
        self.min_resolution = min_resolution
        self.blur_threshold = blur_threshold

    def validate_and_crop(self, image_bytes: bytes) -> QualityResult:
        image_np = decode_image_rgb(image_bytes)
        height, width = image_np.shape[:2]

        if min(width, height) < self.min_resolution:
            return QualityResult(
                valid=False,
                message="Image resolution too low. Upload a higher-resolution leaf photo.",
                blur_score=0.0,
                width=width,
                height=height,
                leaf_detected=False,
            )

        gray = cv2.cvtColor(image_np, cv2.COLOR_RGB2GRAY)
        blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        if blur_score < self.blur_threshold:
            return QualityResult(
                valid=False,
                message="Image too blurry. Upload a clearer leaf photo.",
                blur_score=blur_score,
                width=width,
                height=height,
                leaf_detected=False,
            )

        leaf_mask = self._leaf_mask(image_np)
        contours, _ = cv2.findContours(leaf_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return QualityResult(
                valid=False,
                message="Leaf not detected. Upload an image where the leaf is clearly visible.",
                blur_score=blur_score,
                width=width,
                height=height,
                leaf_detected=False,
            )

        largest = max(contours, key=cv2.contourArea)
        area_ratio = cv2.contourArea(largest) / float(width * height)
        if area_ratio < 0.05:
            return QualityResult(
                valid=False,
                message="Leaf region too small. Move closer and capture the leaf clearly.",
                blur_score=blur_score,
                width=width,
                height=height,
                leaf_detected=False,
            )

        x, y, w, h = cv2.boundingRect(largest)
        margin = int(max(w, h) * 0.08)
        x1 = max(0, x - margin)
        y1 = max(0, y - margin)
        x2 = min(width, x + w + margin)
        y2 = min(height, y + h + margin)
        crop = image_np[y1:y2, x1:x2]

        buffer = io.BytesIO()
        Image.fromarray(crop).save(buffer, format="PNG")
        return QualityResult(
            valid=True,
            message="ok",
            blur_score=blur_score,
            width=width,
            height=height,
            leaf_detected=True,
            cropped_image_bytes=buffer.getvalue(),
        )

    def _leaf_mask(self, image_np: np.ndarray) -> np.ndarray:
        hsv = cv2.cvtColor(image_np, cv2.COLOR_RGB2HSV)
        # Green/yellow/brown ranges seen in healthy + diseased olive leaves.
        green_mask = cv2.inRange(hsv, (20, 25, 25), (95, 255, 255))
        yellow_mask = cv2.inRange(hsv, (10, 20, 20), (35, 255, 255))
        brown_mask = cv2.inRange(hsv, (5, 15, 10), (25, 255, 180))

        merged = cv2.bitwise_or(green_mask, yellow_mask)
        merged = cv2.bitwise_or(merged, brown_mask)
        kernel = np.ones((5, 5), np.uint8)
        merged = cv2.morphologyEx(merged, cv2.MORPH_CLOSE, kernel)
        merged = cv2.morphologyEx(merged, cv2.MORPH_OPEN, kernel)
        return merged
