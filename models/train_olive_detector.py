from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import yaml
from ultralytics import YOLO

DEFAULT_DATA_YAML = Path(r"C:\Users\Win11\Downloads\olive-fruit-detection.v1i.yolov8\data.yaml")
DEFAULT_OUTPUT = Path(__file__).resolve().parent / "olive_detector_best.pt"


IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train YOLOv8 olive fruit detector.")
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA_YAML, help="Path to YOLO data.yaml")
    parser.add_argument("--epochs", type=int, default=120)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=4)
    parser.add_argument("--weights", type=str, default="yolov8s.pt")
    parser.add_argument("--device", type=str, default="0", help="Training device, e.g. 0 or cpu")
    parser.add_argument("--workers", type=int, default=2, help="Dataloader worker processes")
    parser.add_argument("--patience", type=int, default=20)
    parser.add_argument("--hsv-h", type=float, default=0.015)
    parser.add_argument("--hsv-s", type=float, default=0.7)
    parser.add_argument("--hsv-v", type=float, default=0.4)
    parser.add_argument("--degrees", type=float, default=10.0)
    parser.add_argument("--translate", type=float, default=0.1)
    parser.add_argument("--scale", type=float, default=0.5)
    parser.add_argument("--flipud", type=float, default=0.0)
    parser.add_argument("--fliplr", type=float, default=0.5)
    parser.add_argument("--mosaic", type=float, default=1.0)
    parser.add_argument("--mixup", type=float, default=0.1)
    parser.add_argument("--project", type=Path, default=Path("runs") / "olive_detection")
    parser.add_argument("--name", type=str, default="yolov8s_olive")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def _resolve_split_path(raw: str | list[str] | None, data_dir: Path) -> list[Path]:
    if raw is None:
        return []
    values = raw if isinstance(raw, list) else [raw]

    resolved: list[Path] = []
    for value in values:
        split_path = Path(value)
        if split_path.is_absolute():
            resolved.append(split_path)
            continue

        raw_value = str(value).replace("\\", "/")
        candidates = [data_dir / split_path]

        if raw_value.startswith("../"):
            candidates.append(data_dir / raw_value[3:])
        if raw_value.startswith("./"):
            candidates.append(data_dir / raw_value[2:])

        existing = next((candidate for candidate in candidates if candidate.exists()), None)
        resolved.append(existing if existing is not None else candidates[0])
    return resolved


def _count_images(folder: Path) -> int:
    if not folder.exists():
        return 0
    return sum(1 for path in folder.rglob("*") if path.suffix.lower() in IMAGE_EXTS)


def verify_dataset(data_yaml: Path) -> tuple[dict, dict[str, list[Path]]]:
    if not data_yaml.exists():
        raise SystemExit(f"Dataset yaml not found: {data_yaml}")

    with data_yaml.open("r", encoding="utf-8") as file:
        config = yaml.safe_load(file)

    if not isinstance(config, dict):
        raise SystemExit("Invalid data.yaml format.")

    data_dir = data_yaml.parent

    train_paths = _resolve_split_path(config.get("train"), data_dir)
    valid_paths = _resolve_split_path(config.get("val") or config.get("valid"), data_dir)
    test_paths = _resolve_split_path(config.get("test"), data_dir)

    if not train_paths:
        raise SystemExit("train split not found in data.yaml")
    if not valid_paths:
        raise SystemExit("validation split not found in data.yaml (val/valid)")
    if not test_paths:
        raise SystemExit("test split not found in data.yaml")

    for split_name, paths in (
        ("train", train_paths),
        ("valid", valid_paths),
        ("test", test_paths),
    ):
        missing = [str(path) for path in paths if not path.exists()]
        if missing:
            raise SystemExit(f"Missing {split_name} paths: {missing}")

    train_count = sum(_count_images(path) for path in train_paths)
    valid_count = sum(_count_images(path) for path in valid_paths)
    test_count = sum(_count_images(path) for path in test_paths)

    print("Dataset verification complete")
    print(f"train images: {train_count}")
    print(f"valid images: {valid_count}")
    print(f"test images:  {test_count}")

    resolved = {
        "train": train_paths,
        "val": valid_paths,
        "test": test_paths,
    }
    return config, resolved


def build_resolved_yaml(
    src_yaml: Path,
    config: dict,
    resolved_paths: dict[str, list[Path]],
) -> Path:
    export_config = dict(config)
    for split in ("train", "val", "test"):
        paths = resolved_paths[split]
        if len(paths) == 1:
            export_config[split] = str(paths[0].resolve())
        else:
            export_config[split] = [str(path.resolve()) for path in paths]

    resolved_yaml = src_yaml.with_name("data.resolved.yaml")
    with resolved_yaml.open("w", encoding="utf-8") as file:
        yaml.safe_dump(export_config, file, sort_keys=False)
    return resolved_yaml


def main() -> None:
    args = parse_args()

    print("STEP 1 - Dependencies expected: ultralytics, opencv-python, numpy, pandas")
    print(f"Using dataset yaml: {args.data}")

    config, resolved_paths = verify_dataset(args.data)
    resolved_yaml = build_resolved_yaml(args.data, config, resolved_paths)
    print(f"Using resolved yaml: {resolved_yaml}")

    print("STEP 3 - Training YOLO model")
    model = YOLO(args.weights)
    results = model.train(
        data=str(resolved_yaml),
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        device=args.device,
        workers=args.workers,
        patience=args.patience,
        hsv_h=args.hsv_h,
        hsv_s=args.hsv_s,
        hsv_v=args.hsv_v,
        degrees=args.degrees,
        translate=args.translate,
        scale=args.scale,
        flipud=args.flipud,
        fliplr=args.fliplr,
        mosaic=args.mosaic,
        mixup=args.mixup,
        project=str(args.project),
        name=args.name,
    )

    best_path = Path(results.save_dir) / "weights" / "best.pt"
    if not best_path.exists():
        raise SystemExit(f"Training completed but best.pt not found in {best_path.parent}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(best_path, args.output)

    print("STEP 6 - Saved trained model")
    print(f"olive_detector_best.pt saved to: {args.output}")


if __name__ == "__main__":
    main()
