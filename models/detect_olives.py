from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO

DEFAULT_MODEL = Path(__file__).resolve().parent / "olive_detector_best.pt"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run olive detection + crop detected olives.")
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL, help="Path to trained detector model")
    parser.add_argument("--image", type=Path, required=True, help="Input image path")
    parser.add_argument("--crop-dir", type=Path, default=Path("cropped_olives"), help="Output crop folder")
    parser.add_argument("--conf", type=float, default=0.65, help="Confidence threshold")
    parser.add_argument("--iou", type=float, default=0.35, help="NMS IoU threshold")
    parser.add_argument("--imgsz", type=int, default=640, help="Inference image size")
    parser.add_argument("--min-box-area", type=float, default=2500.0, help="Discard boxes smaller than this area")
    parser.add_argument(
        "--max-box-area-ratio",
        type=float,
        default=0.35,
        help="Discard boxes larger than this image-area ratio",
    )
    parser.add_argument(
        "--min-aspect-ratio",
        type=float,
        default=0.4,
        help="Discard boxes with width/height below this ratio",
    )
    parser.add_argument(
        "--max-aspect-ratio",
        type=float,
        default=2.5,
        help="Discard boxes with width/height above this ratio",
    )
    parser.add_argument(
        "--viz-out",
        type=Path,
        default=Path("olive_detection_visualized.jpg"),
        help="Output visualization path",
    )
    return parser.parse_args()


def detect_olives(
    model_path: Path,
    image_path: Path,
    crop_dir: Path,
    conf_threshold: float = 0.65,
    iou_threshold: float = 0.35,
    imgsz: int = 640,
    min_box_area: float = 2500.0,
    max_box_area_ratio: float = 0.35,
    min_aspect_ratio: float = 0.4,
    max_aspect_ratio: float = 2.5,
    viz_out: Path | None = None,
) -> dict:
    if not model_path.exists():
        raise FileNotFoundError(f"Model not found: {model_path}")
    if not image_path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")

    model = YOLO(str(model_path))
    image = cv2.imread(str(image_path))
    if image is None:
        raise ValueError(f"Unable to read image: {image_path}")
    image_h, image_w = image.shape[:2]
    image_area = float(max(1, image_h * image_w))
    max_box_area = float(np.clip(max_box_area_ratio, 0.02, 0.95)) * image_area
    min_aspect = float(np.clip(min_aspect_ratio, 0.1, 10.0))
    max_aspect = float(np.clip(max_aspect_ratio, min_aspect + 0.05, 20.0))

    results = model.predict(
        source=image,
        conf=conf_threshold,
        iou=iou_threshold,
        imgsz=imgsz,
        verbose=False,
    )
    if not results:
        return {
            "detected_olives": 0,
            "avg_confidence": 0.0,
            "confidence_scores": [],
            "bounding_boxes": [],
            "cropped_files": [],
            "visualized_image": "",
        }

    boxes = results[0].boxes
    if boxes is None or len(boxes) == 0:
        return {
            "detected_olives": 0,
            "avg_confidence": 0.0,
            "confidence_scores": [],
            "bounding_boxes": [],
            "cropped_files": [],
            "visualized_image": "",
        }

    xyxy_np = boxes.xyxy.cpu().numpy()
    confs_np = boxes.conf.cpu().numpy()

    crop_dir.mkdir(parents=True, exist_ok=True)
    cropped_files: list[str] = []
    kept_boxes: list[list[float]] = []
    kept_confs: list[float] = []
    visual = image.copy()

    kept_idx = 0
    for box, conf in zip(xyxy_np, confs_np):
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

        kept_idx += 1
        kept_boxes.append([round(float(v), 2) for v in box.tolist()])
        kept_confs.append(round(float(conf), 4))

        cv2.rectangle(visual, (x1, y1), (x2, y2), (74, 196, 79), 2)
        label = f"olive {float(conf):.2f}"
        cv2.putText(
            visual,
            label,
            (x1, max(15, y1 - 6)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (36, 88, 32),
            2,
            cv2.LINE_AA,
        )

        x1, y1, x2, y2 = [int(max(0, round(v))) for v in box]
        crop = image[y1:y2, x1:x2]
        if crop.size == 0:
            continue

        output_path = crop_dir / f"olive_{kept_idx:03d}.jpg"
        cv2.imwrite(str(output_path), crop)
        cropped_files.append(str(output_path))

    total = len(kept_boxes)
    avg_conf = float(np.mean(kept_confs)) if kept_confs else 0.0
    cv2.putText(
        visual,
        f"Detected olives: {total}",
        (12, 28),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (24, 72, 24),
        2,
        cv2.LINE_AA,
    )
    vis_path = ""
    if viz_out is not None:
        viz_out.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(viz_out), visual)
        vis_path = str(viz_out)

    return {
        "detected_olives": total,
        "avg_confidence": round(avg_conf, 4),
        "confidence_scores": kept_confs,
        "bounding_boxes": kept_boxes,
        "cropped_files": cropped_files,
        "visualized_image": vis_path,
    }


def main() -> None:
    args = parse_args()
    result = detect_olives(
        model_path=args.model,
        image_path=args.image,
        crop_dir=args.crop_dir,
        conf_threshold=args.conf,
        iou_threshold=args.iou,
        imgsz=args.imgsz,
        min_box_area=args.min_box_area,
        max_box_area_ratio=args.max_box_area_ratio,
        min_aspect_ratio=args.min_aspect_ratio,
        max_aspect_ratio=args.max_aspect_ratio,
        viz_out=args.viz_out,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
