from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
import sys
import zipfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from backend.services.scene_classifier_service import SceneClassifierService
from backend.services.vision_service import VisionService

SUPPORTED_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
ARCHIVE_EXTS = {".zip", ".rar", ".7z"}

LEAF_TARGETS = {"healthy_leaf", "olive_peacock_spot", "aculus_olearius"}
FRUIT_TARGETS = {"healthy_fruit", "olive_anthracnose"}
BRANCH_TARGETS = {"healthy_branch", "olive_scab_tuberculosis"}

TARGET_FOLDERS = [
    "auto_labeled/leaf/healthy_leaf",
    "auto_labeled/leaf/olive_peacock_spot",
    "auto_labeled/leaf/aculus_olearius",
    "auto_labeled/fruit/healthy_fruit",
    "auto_labeled/fruit/olive_anthracnose",
    "auto_labeled/branch/healthy_branch",
    "auto_labeled/branch/olive_scab_tuberculosis",
    "review_needed/low_confidence",
    "review_needed/conflicting_labels",
    "review_needed/blurry",
    "review_needed/unclear",
    "rejected/duplicates",
    "rejected/corrupt",
    "rejected/no_visible_symptom",
    "router_training_data/leaf",
    "router_training_data/fruit",
    "router_training_data/branch_twig",
    "reports",
]

SOURCE_LABEL_KEYWORDS = {
    "olive_peacock_spot": ["peacock", "oeil_de_paon", "spilocaea", "leaf spot", "paon"],
    "olive_anthracnose": ["anthracnose", "momifiee", "mummified", "fruit rot"],
    "aculus_olearius": ["aculus", "olearius", "mite", "psylle", "psyllid"],
    "olive_scab_tuberculosis": ["tubercul", "scab", "knot", "gall", "savastanoi", "rogna"],
    "healthy": ["healthy", "sain", "normal", "no_disease"],
}

PART_HINT_KEYWORDS = {
    "leaf": ["leaf", "feuille", "foli", "peacock", "spilocaea", "aculus"],
    "fruit": ["fruit", "olive", "anthracnose", "momifiee", "mummified"],
    "branch_twig": ["branch", "twig", "knot", "gall", "tubercul", "scab", "savastanoi", "rogna"],
}


@dataclass
class QualityMetrics:
    blur_score: float
    brightness: float
    saturation: float
    texture_std: float
    is_blurry: bool
    too_dark: bool
    too_bright: bool
    too_small: bool
    no_visible_symptom_like: bool


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Semi-automatic olive disease dataset curation pipeline.")
    parser.add_argument("--source", type=Path, action="append", required=True, help="Source dataset root.")
    parser.add_argument("--output-root", type=Path, default=Path("data/disease_training_data"))
    parser.add_argument("--high-confidence", type=float, default=0.82)
    parser.add_argument("--medium-confidence", type=float, default=0.62)
    parser.add_argument("--near-duplicate-distance", type=int, default=5)
    parser.add_argument("--copy-mode", choices=["copy", "hardlink"], default="copy")
    parser.add_argument("--limit", type=int, default=0, help="Optional cap for faster dry runs.")
    return parser.parse_args()


def ensure_structure(output_root: Path) -> None:
    for rel in TARGET_FOLDERS:
        (output_root / rel).mkdir(parents=True, exist_ok=True)


def sanitize_name(text: str, max_len: int = 64) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "_", text).strip("._-")
    if not cleaned:
        cleaned = "image"
    return cleaned[:max_len]


def read_image(path: Path) -> np.ndarray:
    with Image.open(path) as img:
        return np.array(img.convert("RGB"))


def dhash64(image_rgb: np.ndarray) -> int:
    gray = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2GRAY)
    small = cv2.resize(gray, (9, 8), interpolation=cv2.INTER_AREA)
    diff = small[:, 1:] > small[:, :-1]
    value = 0
    for bit in diff.flatten():
        value = (value << 1) | int(bit)
    return int(value)


def hamming(a: int, b: int) -> int:
    return (a ^ b).bit_count()


def compute_quality(image_rgb: np.ndarray) -> QualityMetrics:
    h, w = image_rgb.shape[:2]
    hsv = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2HSV)
    gray = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2GRAY)
    blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    brightness = float(np.mean(hsv[:, :, 2]))
    saturation = float(np.mean(hsv[:, :, 1]))
    texture_std = float(np.std(gray))
    return QualityMetrics(
        blur_score=round(blur_score, 3),
        brightness=round(brightness, 3),
        saturation=round(saturation, 3),
        texture_std=round(texture_std, 3),
        is_blurry=blur_score < 38.0,
        too_dark=brightness < 40.0,
        too_bright=brightness > 235.0,
        too_small=min(h, w) < 160,
        no_visible_symptom_like=(texture_std < 16.0 and saturation < 40.0 and brightness > 70.0),
    )


def detect_source_label(path_text: str) -> tuple[str | None, float]:
    text = path_text.lower()
    best_label = None
    best_score = 0.0
    for label, keywords in SOURCE_LABEL_KEYWORDS.items():
        score = sum(1.0 for kw in keywords if kw in text)
        if score > best_score:
            best_label = label
            best_score = score
    if best_label is None:
        return None, 0.0
    return best_label, round(min(0.96, 0.58 + best_score * 0.12), 3)


def detect_source_part_hint(path_text: str) -> tuple[str | None, float]:
    text = path_text.lower()
    scores = {part: sum(1.0 for kw in keys if kw in text) for part, keys in PART_HINT_KEYWORDS.items()}
    part = max(scores, key=scores.get)
    score = scores[part]
    if score <= 0:
        return None, 0.0
    return part, round(min(0.92, 0.5 + score * 0.1), 3)


def map_scene_to_part(scene: dict[str, Any]) -> tuple[str, float, str]:
    raw = str(scene.get("scene_type", "unknown")).lower().strip()
    conf = float(scene.get("confidence", 0.0) or 0.0)
    if raw == "leaf":
        return "leaf", conf, raw
    if raw == "fruit_closeup":
        return "fruit", conf, raw
    if raw == "orchard_branch":
        return "branch_twig", conf, raw
    if raw == "harvest_pile":
        return "fruit", max(0.0, conf - 0.18), "harvest_pile_to_fruit"
    return "unclear", conf, raw


def map_leaf_disease(disease_text: str) -> str | None:
    t = disease_text.lower().strip()
    if "uncertain" in t:
        return None
    if t == "none" or "healthy" in t:
        return "healthy_leaf"
    if "peacock" in t or "spilocaea" in t:
        return "olive_peacock_spot"
    if "aculus" in t or "olearius" in t or "mite" in t:
        return "aculus_olearius"
    return None


def detect_archive_contents(path: Path) -> dict[str, Any]:
    suffix = path.suffix.lower()
    if suffix != ".zip":
        return {"path": str(path), "archive_type": suffix, "entries": 0, "image_entries": 0, "supported": False}
    try:
        with zipfile.ZipFile(path) as zf:
            names = zf.namelist()
            img_count = sum(1 for n in names if Path(n).suffix.lower() in SUPPORTED_IMAGE_EXTS)
            return {"path": str(path), "archive_type": suffix, "entries": len(names), "image_entries": img_count, "supported": True}
    except Exception:
        return {"path": str(path), "archive_type": suffix, "entries": 0, "image_entries": 0, "supported": False}


def place_file(source: Path, destination_dir: Path, short_hash: str, mode: str) -> Path:
    destination_dir.mkdir(parents=True, exist_ok=True)
    out_name = f"{sanitize_name(source.stem)}__{short_hash}{source.suffix.lower()}"
    out_path = destination_dir / out_name
    if out_path.exists():
        return out_path
    if mode == "hardlink":
        try:
            out_path.hardlink_to(source)
            return out_path
        except Exception:
            pass
    shutil.copy2(source, out_path)
    return out_path


def decide_destination(
    *,
    output_root: Path,
    part: str,
    predicted_label: str | None,
    conf: float,
    quality: QualityMetrics,
    conflicting: bool,
    high_conf: float,
    medium_conf: float,
) -> tuple[str, str, Path]:
    if quality.no_visible_symptom_like and part == "unclear" and predicted_label is None:
        return "rejected", "no_visible_symptom", output_root / "rejected" / "no_visible_symptom"
    if conflicting:
        return "review_needed", "conflicting_labels", output_root / "review_needed" / "conflicting_labels"
    if quality.is_blurry:
        return "review_needed", "blurry", output_root / "review_needed" / "blurry"
    if part == "unclear" or predicted_label is None:
        return "review_needed", "unclear", output_root / "review_needed" / "unclear"
    if conf < medium_conf:
        return "review_needed", "low_confidence", output_root / "review_needed" / "low_confidence"
    if conf < high_conf:
        return "review_needed", "low_confidence", output_root / "review_needed" / "low_confidence"
    if part == "leaf" and predicted_label in LEAF_TARGETS:
        return "auto_labeled", "high_confidence", output_root / "auto_labeled" / "leaf" / predicted_label
    if part == "fruit" and predicted_label in FRUIT_TARGETS:
        return "auto_labeled", "high_confidence", output_root / "auto_labeled" / "fruit" / predicted_label
    if part == "branch_twig" and predicted_label in BRANCH_TARGETS:
        return "auto_labeled", "high_confidence", output_root / "auto_labeled" / "branch" / predicted_label
    return "review_needed", "unclear", output_root / "review_needed" / "unclear"


def main() -> None:
    args = parse_args()
    sources = [p.resolve() for p in args.source]
    output_root = args.output_root.resolve()
    ensure_structure(output_root)
    reports_dir = output_root / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    files = []
    for root in sources:
        if root.exists():
            files.extend([p for p in root.rglob("*") if p.is_file()])

    unsupported = Counter()
    archive_audit = []
    for p in files:
        suffix = p.suffix.lower()
        if suffix in ARCHIVE_EXTS:
            archive_audit.append(detect_archive_contents(p))
        if suffix and suffix not in SUPPORTED_IMAGE_EXTS:
            unsupported[suffix] += 1

    image_files = [p for p in files if p.suffix.lower() in SUPPORTED_IMAGE_EXTS]
    if args.limit > 0:
        image_files = image_files[: args.limit]

    scene_router = SceneClassifierService()
    vision = VisionService()

    seen_exact: dict[str, Path] = {}
    seen_hashes: list[tuple[int, Path]] = []
    class_before = Counter()
    class_after = Counter()
    split_counts = Counter()
    review_counts = Counter()
    rejected_counts = Counter()
    source_counts = Counter()

    rows: list[dict[str, Any]] = []

    for i, path in enumerate(image_files, start=1):
        source_dataset = "unknown"
        for root in sources:
            try:
                path.relative_to(root)
                source_dataset = root.name
                break
            except ValueError:
                continue
        source_counts[source_dataset] += 1

        source_label, source_label_conf = detect_source_label(str(path).lower())
        source_part_hint, source_part_hint_conf = detect_source_part_hint(str(path).lower())
        class_before[source_label or "unknown"] += 1
        expected_part_from_label = {
            "olive_peacock_spot": "leaf",
            "aculus_olearius": "leaf",
            "olive_anthracnose": "fruit",
            "olive_scab_tuberculosis": "branch_twig",
            "healthy": None,
        }.get(source_label)

        try:
            image_bytes = path.read_bytes()
            image = read_image(path)
        except Exception as exc:
            dst = place_file(path, output_root / "rejected" / "corrupt", "corrupt", args.copy_mode)
            split_counts["rejected/corrupt"] += 1
            rejected_counts["corrupt"] += 1
            rows.append({"source_path": str(path), "route_split": "rejected", "route_reason": "corrupt", "error": str(exc), "destination_path": str(dst)})
            continue

        sha = hashlib.sha256(image_bytes).hexdigest()
        short_sha = sha[:12]
        if sha in seen_exact:
            dst = place_file(path, output_root / "rejected" / "duplicates", short_sha, args.copy_mode)
            split_counts["rejected/duplicates"] += 1
            rejected_counts["duplicates"] += 1
            rows.append({"source_path": str(path), "route_split": "rejected", "route_reason": "duplicate_exact", "duplicate_of": str(seen_exact[sha]), "destination_path": str(dst)})
            continue

        d_hash = dhash64(image)
        near = None
        for prev_hash, prev_path in seen_hashes:
            if hamming(d_hash, prev_hash) <= args.near_duplicate_distance:
                near = prev_path
                break
        if near is not None:
            dst = place_file(path, output_root / "rejected" / "duplicates", short_sha, args.copy_mode)
            split_counts["rejected/duplicates"] += 1
            rejected_counts["duplicates"] += 1
            rows.append({"source_path": str(path), "route_split": "rejected", "route_reason": "duplicate_near", "duplicate_of": str(near), "destination_path": str(dst)})
            continue

        seen_exact[sha] = path
        seen_hashes.append((d_hash, path))

        quality = compute_quality(image)
        scene = scene_router.classify(image_bytes)
        part, part_conf, scene_note = map_scene_to_part(scene)
        if source_part_hint and source_part_hint_conf >= 0.75 and part_conf < 0.60:
            part = source_part_hint
            part_conf = max(part_conf, source_part_hint_conf - 0.08)
            scene_note = f"hint_override:{part}"
        elif part == "unclear" and expected_part_from_label is not None:
            part = expected_part_from_label
            part_conf = max(part_conf, min(0.82, source_label_conf + 0.12))
            scene_note = f"label_part_fallback:{part}"

        pred_label = None
        pred_conf = 0.0
        if part == "leaf":
            try:
                result = vision.analyze_image(image_bytes=image_bytes, image_name=path.name)
                pred_label = map_leaf_disease(str(result.get("disease", "")))
                pred_conf = float(result.get("disease_confidence", 0.0) or 0.0)
            except Exception:
                pred_label, pred_conf = None, 0.0

        if pred_label is None:
            if part == "fruit":
                if source_label == "olive_anthracnose":
                    pred_label, pred_conf = "olive_anthracnose", max(0.85, source_label_conf)
                elif source_label == "healthy":
                    pred_label, pred_conf = "healthy_fruit", max(0.80, source_label_conf)
            elif part == "branch_twig":
                if source_label == "olive_scab_tuberculosis":
                    pred_label, pred_conf = "olive_scab_tuberculosis", max(0.86, source_label_conf)
                elif source_label == "healthy":
                    pred_label, pred_conf = "healthy_branch", max(0.80, source_label_conf)
            elif part == "leaf":
                if source_label == "olive_peacock_spot":
                    pred_label, pred_conf = "olive_peacock_spot", max(0.76, source_label_conf)
                elif source_label == "aculus_olearius":
                    pred_label, pred_conf = "aculus_olearius", max(0.76, source_label_conf)
                elif source_label == "healthy":
                    pred_label, pred_conf = "healthy_leaf", max(0.74, source_label_conf)
        if pred_label is None and source_label == "healthy" and part in {"leaf", "fruit", "branch_twig"}:
            healthy_map = {"leaf": "healthy_leaf", "fruit": "healthy_fruit", "branch_twig": "healthy_branch"}
            pred_label = healthy_map[part]
            pred_conf = max(pred_conf, min(0.78, source_label_conf + 0.06))

        pred_conf = float(np.clip(pred_conf, 0.0, 1.0))
        combined_conf = float(np.clip((pred_conf * 0.7) + (part_conf * 0.3), 0.0, 1.0))

        conflicting = False
        if source_label in {"olive_anthracnose", "olive_scab_tuberculosis"} and part == "leaf":
            conflicting = True
        if source_label in {"olive_peacock_spot", "aculus_olearius"} and part in {"fruit", "branch_twig"}:
            conflicting = True

        split, reason, dst_dir = decide_destination(
            output_root=output_root,
            part=part,
            predicted_label=pred_label,
            conf=combined_conf,
            quality=quality,
            conflicting=conflicting,
            high_conf=args.high_confidence,
            medium_conf=args.medium_confidence,
        )
        dst = place_file(path, dst_dir, short_sha, args.copy_mode)
        split_counts[f"{split}/{reason}"] += 1
        if split == "auto_labeled" and pred_label is not None:
            class_after[pred_label] += 1
            place_file(path, output_root / "router_training_data" / part, short_sha, args.copy_mode)
        elif split == "review_needed":
            review_counts[reason] += 1
        else:
            rejected_counts[reason] += 1

        rows.append(
            {
                "source_path": str(path),
                "source_dataset": source_dataset,
                "source_label": source_label or "unknown",
                "source_part_hint": source_part_hint or "unknown",
                "predicted_part": part,
                "scene_note": scene_note,
                "part_confidence": round(part_conf, 4),
                "predicted_label": pred_label or "unknown",
                "predicted_confidence": round(pred_conf, 4),
                "combined_confidence": round(combined_conf, 4),
                "blur_score": quality.blur_score,
                "brightness": quality.brightness,
                "saturation": quality.saturation,
                "route_split": split,
                "route_reason": reason,
                "destination_path": str(dst),
            }
        )
        if i % 250 == 0:
            print(f"Processed {i}/{len(image_files)} images...")

    summary = {
        "sources": [str(p) for p in sources],
        "output_root": str(output_root),
        "total_files_scanned": len(files),
        "supported_images_found": len(image_files),
        "unsupported_file_types": dict(sorted(unsupported.items())),
        "archive_audit": archive_audit,
        "before_cleanup_class_counts": dict(class_before),
        "after_cleanup_class_counts": dict(class_after),
        "split_counts": dict(split_counts),
        "review_queue_counts": dict(review_counts),
        "rejected_counts": dict(rejected_counts),
        "duplicate_count": int(rejected_counts.get("duplicates", 0)),
        "corrupt_count": int(rejected_counts.get("corrupt", 0)),
        "review_queue_count": int(sum(review_counts.values())),
        "source_dataset_counts": dict(source_counts),
        "recommended_training_commands": [
            r".\.venv\Scripts\python.exe models\train_curated_disease_models.py --curated-root data\disease_training_data --output-dir models\curated --execute",
            r".\.venv\Scripts\python.exe models\train_classifier.py --dataset data\disease_training_data\router_training_data --output models\curated\plant_part_router.pt --model efficientnet_b0 --epochs 8",
            r".\.venv\Scripts\python.exe models\train_classifier.py --dataset data\disease_training_data\auto_labeled\leaf --output models\curated\leaf_disease_model.pt --model convnext_tiny --epochs 10",
            r".\.venv\Scripts\python.exe models\train_classifier.py --dataset data\disease_training_data\auto_labeled\fruit --output models\curated\fruit_disease_model.pt --model efficientnet_b0 --epochs 10",
            r".\.venv\Scripts\python.exe models\train_classifier.py --dataset data\disease_training_data\auto_labeled\branch --output models\curated\branch_disease_model.pt --model efficientnet_b0 --epochs 10",
        ],
    }

    summary_json = reports_dir / "dataset_summary.json"
    summary_md = reports_dir / "dataset_summary.md"
    all_csv = reports_dir / "all_processed_records.csv"
    review_csv = reports_dir / "review_queue.csv"
    archive_csv = reports_dir / "archive_audit.csv"

    summary_json.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    with all_csv.open("w", newline="", encoding="utf-8") as f:
        if rows:
            keys = sorted({k for row in rows for k in row.keys()})
            writer = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
    review_rows = [r for r in rows if r.get("route_split") == "review_needed"]
    with review_csv.open("w", newline="", encoding="utf-8") as f:
        if review_rows:
            keys = sorted({k for row in review_rows for k in row.keys()})
            writer = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(review_rows)
    with archive_csv.open("w", newline="", encoding="utf-8") as f:
        if archive_audit:
            writer = csv.DictWriter(f, fieldnames=list(archive_audit[0].keys()))
            writer.writeheader()
            writer.writerows(archive_audit)

    lines = [
        "# Disease Dataset Curation Summary",
        "",
        f"- Sources scanned: {len(sources)}",
        f"- Total files scanned: {summary['total_files_scanned']}",
        f"- Supported images processed: {summary['supported_images_found']}",
        f"- Duplicate count: {summary['duplicate_count']}",
        f"- Corrupt count: {summary['corrupt_count']}",
        f"- Review queue count: {summary['review_queue_count']}",
        "",
        "## Before Cleanup (source label hints)",
    ]
    for k, v in sorted(class_before.items()):
        lines.append(f"- {k}: {v}")
    lines.append("")
    lines.append("## After Cleanup (auto-labeled)")
    for k, v in sorted(class_after.items()):
        lines.append(f"- {k}: {v}")
    lines.append("")
    lines.append("## Split Counts")
    for k, v in sorted(split_counts.items()):
        lines.append(f"- {k}: {v}")
    lines.append("")
    lines.append("## Review Workflow")
    lines.append(f"- Review CSV: `{review_csv}`")
    lines.append("- Open in Excel/Sheets and filter by `route_reason`.")
    lines.append("")
    lines.append("## Final Training Commands")
    for cmd in summary["recommended_training_commands"]:
        lines.append(f"- `{cmd}`")
    summary_md.write_text("\n".join(lines), encoding="utf-8")

    print(f"Curation complete. Summary: {summary_json}")
    print(f"Review queue CSV: {review_csv}")


if __name__ == "__main__":
    main()
