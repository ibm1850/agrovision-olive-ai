from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import yaml
from ultralytics import YOLO

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}
DEFAULT_DATA_YAML = Path(r"C:\Users\Win11\Downloads\olive-fruit-detection.v1i.yolov8\data.yaml")
DEFAULT_MODEL = Path(__file__).resolve().parent / "olive_detector_best.pt"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Add new images to YOLO dataset with pseudo-labels and per-image olive counts.",
    )
    parser.add_argument("--input-dir", type=Path, required=True, help="Folder containing new orchard images")
    parser.add_argument("--data-yaml", type=Path, default=DEFAULT_DATA_YAML, help="YOLO data.yaml path")
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL, help="Trained olive detector model")
    parser.add_argument(
        "--target-split",
        type=str,
        default="train",
        choices=["train", "val", "test"],
        help="Dataset split where images/labels are added",
    )
    parser.add_argument("--conf", type=float, default=0.65)
    parser.add_argument("--iou", type=float, default=0.35)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--min-box-area", type=float, default=2500.0)
    parser.add_argument("--max-box-area-ratio", type=float, default=0.35)
    parser.add_argument("--min-aspect-ratio", type=float, default=0.4)
    parser.add_argument("--max-aspect-ratio", type=float, default=2.5)
    parser.add_argument("--class-id", type=int, default=0, help="YOLO class index for olive")
    parser.add_argument("--prefix", type=str, default="useradd")
    parser.add_argument("--summary-json", type=Path, default=Path("data") / "olive_additions_summary.json")
    parser.add_argument("--dry-run", action="store_true", help="Only report counts, do not write files")
    return parser.parse_args()


def _resolve_path(value: str | list[str] | None, data_dir: Path) -> Path:
    if value is None:
        raise ValueError("Split path missing in data.yaml")

    if isinstance(value, list):
        if not value:
            raise ValueError("Split path list is empty in data.yaml")
        value = value[0]

    raw = str(value).replace("\\", "/")
    p = Path(value)
    if p.is_absolute():
        return p

    candidates = [data_dir / p]
    if raw.startswith("../"):
        candidates.append(data_dir / raw[3:])
    if raw.startswith("./"):
        candidates.append(data_dir / raw[2:])

    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    return candidates[0].resolve()


def _load_split_dirs(data_yaml: Path, split: str) -> tuple[Path, Path]:
    if not data_yaml.exists():
        raise FileNotFoundError(f"data.yaml not found: {data_yaml}")

    with data_yaml.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    if not isinstance(cfg, dict):
        raise ValueError("Invalid data.yaml format")

    data_dir = data_yaml.parent
    split_key = "val" if split == "val" else split
    if split == "val" and "val" not in cfg and "valid" in cfg:
        split_key = "valid"

    images_dir = _resolve_path(cfg.get(split_key), data_dir)
    if images_dir.name.lower() != "images":
        raise ValueError(f"Expected split path to end with 'images', got: {images_dir}")

    labels_dir = images_dir.parent / "labels"
    labels_dir.mkdir(parents=True, exist_ok=True)
    images_dir.mkdir(parents=True, exist_ok=True)
    return images_dir, labels_dir


def _iter_images(folder: Path) -> list[Path]:
    if not folder.exists():
        raise FileNotFoundError(f"Input folder not found: {folder}")
    paths = [p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTS]
    if not paths:
        raise ValueError(f"No images found in: {folder}")
    return sorted(paths)


def _filter_boxes(
    boxes_xyxy: np.ndarray,
    confs: np.ndarray,
    image_w: int,
    image_h: int,
    min_box_area: float,
    max_box_area_ratio: float,
    min_aspect_ratio: float,
    max_aspect_ratio: float,
) -> list[list[float]]:
    image_area = float(max(1, image_w * image_h))
    max_box_area = float(np.clip(max_box_area_ratio, 0.02, 0.95)) * image_area
    min_aspect = float(np.clip(min_aspect_ratio, 0.1, 10.0))
    max_aspect = float(np.clip(max_aspect_ratio, min_aspect + 0.05, 20.0))

    kept: list[list[float]] = []
    for box, _conf in zip(boxes_xyxy, confs):
        x1, y1, x2, y2 = [float(v) for v in box.tolist()]
        width = max(0.0, x2 - x1)
        height = max(0.0, y2 - y1)
        area = width * height
        if area < float(min_box_area):
            continue
        if area > max_box_area:
            continue
        if height <= 0.0:
            continue
        aspect = width / height
        if aspect < min_aspect or aspect > max_aspect:
            continue
        kept.append([x1, y1, x2, y2])
    return kept


def _to_yolo_line(class_id: int, box: list[float], image_w: int, image_h: int) -> str:
    x1, y1, x2, y2 = box
    cx = ((x1 + x2) / 2.0) / image_w
    cy = ((y1 + y2) / 2.0) / image_h
    w = (x2 - x1) / image_w
    h = (y2 - y1) / image_h
    cx = float(np.clip(cx, 0.0, 1.0))
    cy = float(np.clip(cy, 0.0, 1.0))
    w = float(np.clip(w, 0.0, 1.0))
    h = float(np.clip(h, 0.0, 1.0))
    return f"{class_id} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}"


def main() -> None:
    args = parse_args()

    if not args.model.exists():
        raise FileNotFoundError(f"Model not found: {args.model}")

    images_dir, labels_dir = _load_split_dirs(args.data_yaml, args.target_split)
    source_images = _iter_images(args.input_dir)
    model = YOLO(str(args.model))

    run_stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    records: list[dict] = []

    print(f"Input images: {len(source_images)}")
    print(f"Target images dir: {images_dir}")
    print(f"Target labels dir: {labels_dir}")
    print(f"Dry run: {args.dry_run}")

    for idx, source_path in enumerate(source_images, start=1):
        image = cv2.imread(str(source_path))
        if image is None:
            print(f"SKIP (unreadable): {source_path}")
            continue
        h, w = image.shape[:2]

        results = model.predict(
            source=image,
            conf=float(np.clip(args.conf, 0.01, 0.99)),
            iou=float(np.clip(args.iou, 0.01, 0.99)),
            imgsz=int(np.clip(args.imgsz, 320, 1600)),
            verbose=False,
        )

        boxes = results[0].boxes if results else None
        if boxes is None or len(boxes) == 0:
            kept_boxes: list[list[float]] = []
        else:
            kept_boxes = _filter_boxes(
                boxes_xyxy=boxes.xyxy.cpu().numpy(),
                confs=boxes.conf.cpu().numpy(),
                image_w=w,
                image_h=h,
                min_box_area=args.min_box_area,
                max_box_area_ratio=args.max_box_area_ratio,
                min_aspect_ratio=args.min_aspect_ratio,
                max_aspect_ratio=args.max_aspect_ratio,
            )

        olive_count = len(kept_boxes)
        out_stem = f"{args.prefix}_{run_stamp}_{idx:03d}"
        out_image = images_dir / f"{out_stem}.jpg"
        out_label = labels_dir / f"{out_stem}.txt"

        if not args.dry_run:
            cv2.imwrite(str(out_image), image)
            yolo_lines = [_to_yolo_line(args.class_id, box, w, h) for box in kept_boxes]
            out_label.write_text("\n".join(yolo_lines), encoding="utf-8")

        record = {
            "source_image": str(source_path),
            "saved_image": str(out_image),
            "saved_label": str(out_label),
            "detected_olives": olive_count,
        }
        records.append(record)
        print(f"[{idx}/{len(source_images)}] {source_path.name}: {olive_count} olives")

    if not args.dry_run:
        args.summary_json.parent.mkdir(parents=True, exist_ok=True)
        args.summary_json.write_text(
            json.dumps(
                {
                    "timestamp": run_stamp,
                    "input_dir": str(args.input_dir),
                    "target_split": args.target_split,
                    "total_images": len(records),
                    "records": records,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        cache_file = images_dir.parent / "labels.cache"
        if cache_file.exists():
            cache_file.unlink()
        print(f"\nSummary saved: {args.summary_json}")
        print(f"Removed cache: {cache_file}")


if __name__ == "__main__":
    main()
