from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Iterator

import requests


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Convert OpenAI/Roboflow JSONL export into ImageFolder-style dataset. "
            "Supports binary (Buena/Mala) and multi-class labels."
        )
    )
    parser.add_argument(
        "--source",
        type=Path,
        required=True,
        help="Path to folder containing _annotations.train/valid/test.jsonl files.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output ImageFolder root.",
    )
    parser.add_argument(
        "--label-mode",
        type=str,
        choices=["auto", "binary", "multiclass"],
        default="auto",
        help=(
            "auto: detect format from labels; "
            "binary: map Buena/Mala to healthy/diseased; "
            "multiclass: keep class names from assistant labels."
        ),
    )
    parser.add_argument(
        "--max-images",
        type=int,
        default=0,
        help="Optional limit for quick tests. 0 means no limit.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=20,
        help="HTTP timeout for image downloads.",
    )
    return parser.parse_args()


def jsonl_files(source: Path) -> list[Path]:
    files = sorted(source.glob("_annotations.*.jsonl"))
    if not files:
        raise SystemExit(f"No _annotations.*.jsonl files found in: {source}")
    return files


def iter_records(file_path: Path) -> Iterator[dict]:
    with file_path.open("r", encoding="utf-8") as fp:
        for line in fp:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def slugify_label(label: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", label.strip()).strip("_").lower()
    return cleaned or "unknown"


def extract_labels_from_assistant(assistant_text: str) -> list[str]:
    # Example chunk: "<loc..><loc..><loc..><loc..> BlackScale"
    labels: list[str] = []
    for part in assistant_text.split(";"):
        piece = part.strip()
        if not piece:
            continue
        # Remove all <loc....> tokens and keep trailing class text.
        piece = re.sub(r"<loc\d{4}>", " ", piece).strip()
        if not piece:
            continue
        labels.append(piece)
    return labels


def choose_label(raw_labels: list[str], mode: str) -> str | None:
    if not raw_labels:
        return None
    counts = Counter(raw_labels)
    dominant = counts.most_common(1)[0][0]

    dominant_lower = dominant.lower()
    if mode == "binary":
        return "diseased" if "mala" in dominant_lower else "healthy"

    if mode == "auto":
        unique_lower = {lbl.lower() for lbl in raw_labels}
        if unique_lower.issubset({"buena", "mala"}) or "buena" in unique_lower or "mala" in unique_lower:
            return "diseased" if "mala" in unique_lower else "healthy"
        mode = "multiclass"

    if mode == "multiclass":
        normalized = dominant.replace("OlivePeacockSpot", "Olive Peacock Spot")
        normalized = normalized.replace("BlackScale", "Black Scale")
        return slugify_label(normalized)

    return None


def extract_url_and_label(record: dict, mode: str) -> tuple[str | None, str | None]:
    messages = record.get("messages", [])
    image_url = None
    assistant_text = ""

    for msg in messages:
        role = msg.get("role")
        content = msg.get("content")
        if role == "assistant" and isinstance(content, str):
            assistant_text = content
        if role == "user" and isinstance(content, list):
            for item in content:
                if item.get("type") == "image_url":
                    image_url = item.get("image_url", {}).get("url")

    if not image_url:
        return None, None

    labels = extract_labels_from_assistant(assistant_text)
    final_label = choose_label(labels, mode=mode)
    return image_url, final_label


def download_image(url: str, timeout: int) -> bytes | None:
    try:
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
        return resp.content
    except Exception:
        return None


def main() -> None:
    args = parse_args()
    source = args.source
    output = args.output
    output.mkdir(parents=True, exist_ok=True)

    total_saved = 0
    total_seen = 0
    class_counter: Counter[str] = Counter()

    for jsonl in jsonl_files(source):
        print(f"Reading {jsonl.name}")
        for rec in iter_records(jsonl):
            total_seen += 1
            url, label = extract_url_and_label(rec, mode=args.label_mode)
            if not url or not label:
                continue

            data = download_image(url, timeout=args.timeout)
            if data is None:
                continue

            class_dir = output / label
            class_dir.mkdir(parents=True, exist_ok=True)
            digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]
            target = class_dir / f"{digest}.jpg"
            if not target.exists():
                target.write_bytes(data)
                total_saved += 1
                class_counter[label] += 1

            if args.max_images > 0 and total_saved >= args.max_images:
                print(f"Reached max-images={args.max_images}")
                print(f"Saved: {total_saved} images from {total_seen} records")
                print(f"Class distribution: {dict(class_counter)}")
                return

    print(f"Completed. Saved: {total_saved} images from {total_seen} records.")
    print(f"ImageFolder output: {output}")
    print(f"Class distribution: {dict(class_counter)}")


if __name__ == "__main__":
    main()

