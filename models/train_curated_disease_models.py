from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

SUPPORTED_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train curated plant-part and disease models.")
    parser.add_argument("--curated-root", type=Path, default=Path("data/disease_training_data"))
    parser.add_argument(
        "--extra-curated-root",
        type=Path,
        action="append",
        default=[],
        help="Additional curated roots to merge (repeatable).",
    )
    parser.add_argument("--output-dir", type=Path, default=Path("models/curated"))
    parser.add_argument("--execute", action="store_true", help="Run training commands; otherwise print only.")
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--router-epochs", type=int, default=8)
    parser.add_argument("--python-exe", type=Path, default=Path(sys.executable))
    parser.add_argument("--router-model", type=str, default="efficientnet_b0")
    parser.add_argument("--disease-model", type=str, default="efficientnet_b0")
    parser.add_argument("--router-lr", type=float, default=1e-3)
    parser.add_argument("--disease-lr", type=float, default=3e-4)
    parser.add_argument("--batch-size", type=int, default=16)
    return parser.parse_args()


def _iter_images(folder: Path):
    if not folder.exists():
        return
    for p in folder.rglob("*"):
        if p.is_file() and p.suffix.lower() in SUPPORTED_IMAGE_EXTS:
            yield p


def _safe_link_or_copy(source: Path, target: Path) -> None:
    if target.exists():
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        target.hardlink_to(source)
    except Exception:
        shutil.copy2(source, target)


def _short_name(prefix: str, source: Path) -> str:
    stem = source.stem[:24]
    suffix = source.suffix.lower()
    digest = f"{abs(hash(str(source.resolve()))) % 10**12:012d}"
    return f"{prefix}_{stem}_{digest}{suffix}"


def _copy_class_dirs(class_sources: list[Path], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    seen: set[str] = set()
    for src in class_sources:
        for image in _iter_images(src):
            key = str(image.resolve()).lower()
            if key in seen:
                continue
            seen.add(key)
            target = out_dir / _short_name("img", image)
            _safe_link_or_copy(image, target)


def build_merged_training_roots(curated_roots: list[Path], output_dir: Path) -> tuple[Path, Path, Path]:
    prepared_root = output_dir / "_prepared_datasets"
    if prepared_root.exists():
        shutil.rmtree(prepared_root)
    leaf_root = prepared_root / "leaf"
    fruit_root = prepared_root / "fruit"
    branch_root = prepared_root / "branch"

    leaf_classes = ["healthy_leaf", "olive_peacock_spot", "aculus_olearius"]
    fruit_classes = ["healthy_fruit", "olive_anthracnose"]
    branch_classes = ["healthy_branch", "olive_scab_tuberculosis"]

    for cls in leaf_classes:
        class_sources: list[Path] = []
        for root in curated_roots:
            class_sources.append(root / "auto_labeled" / "leaf" / cls)
            class_sources.append(root / "final_curated" / "leaf" / cls)
        _copy_class_dirs(class_sources, leaf_root / cls)

    for cls in fruit_classes:
        class_sources = []
        for root in curated_roots:
            class_sources.append(root / "auto_labeled" / "fruit" / cls)
            class_sources.append(root / "final_curated" / "fruit" / cls)
        _copy_class_dirs(class_sources, fruit_root / cls)

    for cls in branch_classes:
        class_sources = []
        for root in curated_roots:
            class_sources.append(root / "auto_labeled" / "branch" / cls)
            class_sources.append(root / "final_curated" / "branch" / cls)
        _copy_class_dirs(class_sources, branch_root / cls)

    return leaf_root, fruit_root, branch_root


def has_min_classes(dataset_dir: Path, min_classes: int = 2) -> bool:
    if not dataset_dir.exists():
        return False
    class_dirs = [p for p in dataset_dir.iterdir() if p.is_dir()]
    valid = 0
    for class_dir in class_dirs:
        if any(p.suffix.lower() in SUPPORTED_IMAGE_EXTS for p in class_dir.rglob("*") if p.is_file()):
            valid += 1
    return valid >= min_classes


def build_router_dataset(curated_root: Path) -> Path:
    router_root = curated_root / "router_training_data"
    if router_root.exists():
        return router_root
    router_root.mkdir(parents=True, exist_ok=True)
    mapping = {
        "leaf": curated_root / "auto_labeled" / "leaf",
        "fruit": curated_root / "auto_labeled" / "fruit",
        "branch_twig": curated_root / "auto_labeled" / "branch",
    }
    for part, src_root in mapping.items():
        dst = router_root / part
        dst.mkdir(parents=True, exist_ok=True)
        if not src_root.exists():
            continue
        for p in src_root.rglob("*"):
            if not p.is_file() or p.suffix.lower() not in SUPPORTED_IMAGE_EXTS:
                continue
            target = dst / p.name
            if target.exists():
                continue
            shutil.copy2(p, target)
    return router_root


def build_router_dataset_from_parts(
    *,
    leaf_dataset: Path,
    fruit_dataset: Path,
    branch_dataset: Path,
    output_dir: Path,
) -> Path:
    router_root = output_dir / "_prepared_datasets" / "router_training_data"
    if router_root.exists():
        shutil.rmtree(router_root)
    mapping = {
        "leaf": leaf_dataset,
        "fruit": fruit_dataset,
        "branch_twig": branch_dataset,
    }
    for part, src_root in mapping.items():
        dst = router_root / part
        dst.mkdir(parents=True, exist_ok=True)
        for class_dir in src_root.iterdir():
            if not class_dir.is_dir():
                continue
            for p in _iter_images(class_dir):
                target = dst / _short_name(class_dir.name[:10], p)
                _safe_link_or_copy(p, target)
    return router_root


def build_command(
    *,
    python_exe: Path,
    dataset: Path,
    output: Path,
    model: str,
    epochs: int,
    lr: float,
    batch_size: int,
) -> list[str]:
    return [
        str(python_exe),
        "models/train_classifier.py",
        "--dataset",
        str(dataset),
        "--output",
        str(output),
        "--model",
        model,
        "--epochs",
        str(epochs),
        "--lr",
        str(lr),
        "--batch-size",
        str(batch_size),
    ]


def run_or_print(commands: list[list[str]], execute: bool) -> None:
    for cmd in commands:
        printable = " ".join(cmd)
        print(printable)
        if execute:
            subprocess.run(cmd, check=True)


def main() -> None:
    args = parse_args()
    curated_roots = [args.curated_root.resolve(), *[p.resolve() for p in args.extra_curated_root]]
    curated_roots = [p for p in curated_roots if p.exists()]
    if not curated_roots:
        print("No valid curated roots found.")
        return
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    leaf_dataset, fruit_dataset, branch_dataset = build_merged_training_roots(curated_roots, output_dir)
    router_dataset = build_router_dataset_from_parts(
        leaf_dataset=leaf_dataset,
        fruit_dataset=fruit_dataset,
        branch_dataset=branch_dataset,
        output_dir=output_dir,
    )

    commands: list[list[str]] = []

    if has_min_classes(router_dataset):
        commands.append(
            build_command(
                python_exe=args.python_exe,
                dataset=router_dataset,
                output=output_dir / "plant_part_router.pt",
                model=args.router_model,
                epochs=args.router_epochs,
                lr=args.router_lr,
                batch_size=args.batch_size,
            )
        )
    else:
        print(f"Skipping router model (not enough classes): {router_dataset}")

    if has_min_classes(leaf_dataset):
        commands.append(
            build_command(
                python_exe=args.python_exe,
                dataset=leaf_dataset,
                output=output_dir / "leaf_disease_model.pt",
                model=args.disease_model,
                epochs=args.epochs,
                lr=args.disease_lr,
                batch_size=args.batch_size,
            )
        )
    else:
        print(f"Skipping leaf model (not enough classes): {leaf_dataset}")

    if has_min_classes(fruit_dataset):
        commands.append(
            build_command(
                python_exe=args.python_exe,
                dataset=fruit_dataset,
                output=output_dir / "fruit_disease_model.pt",
                model="efficientnet_b0",
                epochs=args.epochs,
                lr=args.disease_lr,
                batch_size=args.batch_size,
            )
        )
    else:
        print(f"Skipping fruit model (not enough classes): {fruit_dataset}")

    if has_min_classes(branch_dataset):
        commands.append(
            build_command(
                python_exe=args.python_exe,
                dataset=branch_dataset,
                output=output_dir / "branch_disease_model.pt",
                model="efficientnet_b0",
                epochs=args.epochs,
                lr=args.disease_lr,
                batch_size=args.batch_size,
            )
        )
    else:
        print(f"Skipping branch model (not enough classes): {branch_dataset}")

    if not commands:
        print("No trainable datasets found after cleanup.")
        return

    run_or_print(commands, args.execute)


if __name__ == "__main__":
    main()
