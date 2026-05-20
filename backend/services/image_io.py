from __future__ import annotations

import io

import cv2
import numpy as np
from PIL import Image


def decode_image_rgb(image_bytes: bytes) -> np.ndarray:
    if not image_bytes:
        raise ValueError("Uploaded image is empty.")

    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if bgr is not None:
        return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)

    try:
        return np.array(Image.open(io.BytesIO(image_bytes)).convert("RGB"))
    except ModuleNotFoundError as exc:
        if "pi_heif" in str(exc):
            raise ValueError(
                "This image codec is not available on the server (pi_heif missing). "
                "Please upload JPG/PNG/WEBP, or install dependency: pip install pi-heif"
            ) from exc
        raise ValueError(f"Unsupported image format: {exc}") from exc
    except Exception as exc:
        raise ValueError(f"Unable to decode uploaded image: {exc}") from exc
