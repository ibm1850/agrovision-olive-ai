from __future__ import annotations

from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

try:
    from ultralytics import YOLO
    YOLO_IMPORT_ERROR: str | None = None
except Exception as exc:
    YOLO = None
    YOLO_IMPORT_ERROR = str(exc)

from backend.core.config import settings


class OliveDetectionService:
    def __init__(self) -> None:
        self.model_path = Path(settings.olive_detection_model_path)
        self.crop_root = Path(settings.cropped_olives_dir)
        self.model = None
        self.load_error: str | None = None
        self.reload_model()

    def reload_model(self) -> None:
        if YOLO is None:
            self.model = None
            import_error = YOLO_IMPORT_ERROR or "unknown import error"
            self.load_error = f"ultralytics/torch import failed: {import_error}"
            return
        if not self.model_path.exists():
            self.model = None
            self.load_error = f"model file not found: {self.model_path}"
            return
        try:
            self.model = YOLO(str(self.model_path))
            self.load_error = None
        except Exception as exc:
            self.model = None
            self.load_error = f"failed to load model from {self.model_path}: {exc}"

    def detect_from_bytes(
        self,
        image_bytes: bytes,
        conf: float = 0.35,
        iou: float = 0.35,
        imgsz: int = 640,
        min_box_area: float = 150.0,
        max_box_area_ratio: float = 0.35,
        min_aspect_ratio: float = 0.4,
        max_aspect_ratio: float = 2.5,
    ) -> dict:
        if not image_bytes:
            raise ValueError("Uploaded image is empty.")

        if self.model is None:
            self.reload_model()
        if self.model is None:
            reason = self.load_error or "unknown model load error"
            raise RuntimeError(
                "Olive detection model unavailable. "
                f"Reason: {reason}. "
                "Use the project venv to run backend and ensure model exists at "
                f"'{self.model_path}'."
            )

        image_array = np.frombuffer(image_bytes, dtype=np.uint8)
        image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError("Unable to decode uploaded image.")
        image_h, image_w = image.shape[:2]
        image_area = float(max(1, image_h * image_w))
        max_box_area = float(np.clip(max_box_area_ratio, 0.02, 0.95)) * image_area
        min_aspect = float(np.clip(min_aspect_ratio, 0.1, 10.0))
        max_aspect = float(np.clip(max_aspect_ratio, min_aspect + 0.05, 20.0))

        results = self.model.predict(
            source=image,
            conf=float(np.clip(conf, 0.01, 0.99)),
            iou=float(np.clip(iou, 0.01, 0.99)),
            imgsz=int(np.clip(imgsz, 320, 1600)),
            verbose=False,
        )
        if not results or results[0].boxes is None or len(results[0].boxes) == 0:
            return {
                "detected_olives": 0,
                "avg_confidence": 0.0,
                "fruit_density": 0.0,
                "fruit_coverage": 0.0,
                "confidence_scores": [],
                "bounding_boxes": [],
                "cropped_files": [],
                "crop_urls": [],
            }

        boxes = results[0].boxes
        xyxy_np = boxes.xyxy.cpu().numpy()
        confs_np = boxes.conf.cpu().numpy()

        run_dir = self.crop_root / datetime.now().strftime("%Y%m%d_%H%M%S")
        run_dir.mkdir(parents=True, exist_ok=True)

        cropped_files: list[str] = []
        crop_urls: list[str] = []
        kept_boxes: list[list[float]] = []
        kept_confs: list[float] = []

        raw_boxes: list[list[float]] = []
        raw_confs: list[float] = []
        for box, conf_score in zip(xyxy_np, confs_np):
            x1, y1, x2, y2 = [int(max(0, round(v))) for v in box.tolist()]
            width = max(0, x2 - x1)
            height = max(0, y2 - y1)
            area = width * height
            if area < float(min_box_area):
                continue
            if area > max_box_area:
                continue
            if height <= 0:
                continue
            aspect = float(width) / float(height)
            if aspect < min_aspect or aspect > max_aspect:
                continue

            raw_boxes.append([float(x1), float(y1), float(x2), float(y2)])
            raw_confs.append(float(conf_score))

        merged_boxes, merged_confs = self._merge_and_deduplicate(raw_boxes, raw_confs, merge_iou=0.55, duplicate_iou=0.90)

        kept_idx = 0
        for box, conf_score in zip(merged_boxes, merged_confs):
            x1, y1, x2, y2 = [int(max(0, round(v))) for v in box]
            x1 = min(x1, image_w - 1)
            x2 = min(x2, image_w)
            y1 = min(y1, image_h - 1)
            y2 = min(y2, image_h)
            width = max(0, x2 - x1)
            height = max(0, y2 - y1)
            if width == 0 or height == 0:
                continue

            kept_idx += 1
            kept_boxes.append([round(float(x1), 2), round(float(y1), 2), round(float(x2), 2), round(float(y2), 2)])
            kept_confs.append(round(float(conf_score), 4))

            crop = image[y1:y2, x1:x2]
            if crop.size == 0:
                continue
            out_path = run_dir / f"olive_{kept_idx:03d}.jpg"
            cv2.imwrite(str(out_path), crop)
            cropped_files.append(str(out_path))
            rel = out_path.relative_to(self.crop_root).as_posix()
            crop_urls.append(f"/cropped-data/{rel}")

        avg_conf = float(np.mean(kept_confs)) if kept_confs else 0.0
        coverage = 0.0
        if kept_boxes:
            area_sum = 0.0
            for box in kept_boxes:
                area_sum += max(0.0, (box[2] - box[0]) * (box[3] - box[1]))
            coverage = float(np.clip((area_sum / image_area) * 100.0, 0.0, 100.0))
        density = float(len(kept_boxes) / max(1.0, image_area / 10000.0))

        return {
            "detected_olives": len(kept_boxes),
            "avg_confidence": round(avg_conf, 4),
            "fruit_density": round(density, 4),
            "fruit_coverage": round(coverage, 4),
            "confidence_scores": kept_confs,
            "bounding_boxes": kept_boxes,
            "cropped_files": cropped_files,
            "crop_urls": crop_urls,
        }

    def _merge_and_deduplicate(
        self,
        boxes: list[list[float]],
        confs: list[float],
        *,
        merge_iou: float,
        duplicate_iou: float,
    ) -> tuple[list[list[float]], list[float]]:
        if not boxes:
            return [], []

        order = sorted(range(len(boxes)), key=lambda idx: confs[idx], reverse=True)
        used = [False] * len(boxes)
        merged_boxes: list[list[float]] = []
        merged_confs: list[float] = []

        for idx in order:
            if used[idx]:
                continue
            used[idx] = True
            group = [idx]
            for jdx in order:
                if used[jdx]:
                    continue
                iou = self._iou(boxes[idx], boxes[jdx])
                if iou >= duplicate_iou or iou >= merge_iou:
                    used[jdx] = True
                    group.append(jdx)

            weights = np.array([max(1e-6, confs[g]) for g in group], dtype=np.float64)
            coords = np.array([boxes[g] for g in group], dtype=np.float64)
            weighted = (coords * weights[:, None]).sum(axis=0) / weights.sum()
            merged_boxes.append([float(v) for v in weighted.tolist()])
            merged_confs.append(float(np.mean([confs[g] for g in group])))

        return merged_boxes, merged_confs

    def _iou(self, box_a: list[float], box_b: list[float]) -> float:
        ax1, ay1, ax2, ay2 = box_a
        bx1, by1, bx2, by2 = box_b
        inter_x1 = max(ax1, bx1)
        inter_y1 = max(ay1, by1)
        inter_x2 = min(ax2, bx2)
        inter_y2 = min(ay2, by2)
        inter_w = max(0.0, inter_x2 - inter_x1)
        inter_h = max(0.0, inter_y2 - inter_y1)
        inter_area = inter_w * inter_h
        if inter_area <= 0:
            return 0.0
        area_a = max(0.0, (ax2 - ax1) * (ay2 - ay1))
        area_b = max(0.0, (bx2 - bx1) * (by2 - by1))
        denom = area_a + area_b - inter_area
        if denom <= 0:
            return 0.0
        return float(inter_area / denom)
