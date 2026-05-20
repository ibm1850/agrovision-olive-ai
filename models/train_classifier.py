from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import torch
from PIL import Image
from sklearn.metrics import accuracy_score, confusion_matrix, precision_recall_fscore_support
from sklearn.model_selection import train_test_split
from torch import nn
from torch.utils.data import DataLoader, Dataset, WeightedRandomSampler
from torchvision import datasets, models, transforms

try:
    import timm
except Exception:
    timm = None
    extra_paths = [
        Path("C:/Users/Win11/Downloads/pytorch-image-models-main"),
        Path("C:/Users/Win11/Downloads/ConvNeXt-main"),
    ]
    for path in extra_paths:
        if path.exists():
            path_str = str(path.resolve())
            if path_str not in sys.path:
                sys.path.insert(0, path_str)
    try:
        import timm  # type: ignore[no-redef]
    except Exception:
        timm = None


CONVNEXT_TIMM_MODELS = {
    "convnext_tiny": "hf_hub:timm/convnext_tiny.in12k_ft_in1k",
    "convnext_small": "hf_hub:timm/convnext_small.in12k_ft_in1k",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Train an olive classifier with transfer learning "
            "(EfficientNet/MobileNet/ConvNeXt)."
        )
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        action="append",
        required=True,
        help="Path to ImageFolder dataset. Repeat --dataset to merge multiple datasets.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output checkpoint path (e.g. models/disease_model.pt).",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="efficientnet_b0",
        choices=["efficientnet_b0", "mobilenet_v2", "convnext_tiny", "convnext_small"],
    )
    parser.add_argument("--epochs", type=int, default=8)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--val-split", type=float, default=0.2)
    parser.add_argument("--image-size", type=int, default=224)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def set_seed(seed: int) -> None:
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def build_model(model_name: str, num_classes: int) -> nn.Module:
    if model_name in CONVNEXT_TIMM_MODELS:
        if timm is None:
            raise RuntimeError(
                "ConvNeXt requested but timm is not available. "
                "Install timm or provide a local timm source path."
            )
        return timm.create_model(
            CONVNEXT_TIMM_MODELS[model_name],
            pretrained=True,
            num_classes=num_classes,
        )

    if model_name == "mobilenet_v2":
        model = models.mobilenet_v2(weights=models.MobileNet_V2_Weights.DEFAULT)
        in_features = model.classifier[1].in_features
        model.classifier[1] = nn.Linear(in_features, num_classes)
        return model

    model = models.efficientnet_b0(weights=models.EfficientNet_B0_Weights.DEFAULT)
    in_features = model.classifier[1].in_features
    model.classifier[1] = nn.Linear(in_features, num_classes)
    return model


def get_loaders(
    dataset_dirs: list[Path], image_size: int, batch_size: int, val_split: float, seed: int
) -> tuple[DataLoader, DataLoader, list[str]]:
    train_tf = transforms.Compose(
        [
            transforms.Resize((image_size, image_size)),
            transforms.RandomHorizontalFlip(),
            transforms.RandomRotation(8),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
        ]
    )
    val_tf = transforms.Compose(
        [
            transforms.Resize((image_size, image_size)),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
        ]
    )

    samples, targets, class_names = collect_samples_from_datasets(dataset_dirs)
    if len(class_names) < 2:
        raise ValueError("Need at least 2 classes after merging datasets.")

    indices = np.arange(len(samples))
    train_idx, val_idx = train_test_split(
        indices,
        test_size=val_split,
        random_state=seed,
        stratify=np.array(targets),
    )

    train_dataset = PathImageDataset(
        samples=[samples[i] for i in train_idx.tolist()],
        transform=train_tf,
    )
    val_dataset = PathImageDataset(
        samples=[samples[i] for i in val_idx.tolist()],
        transform=val_tf,
    )

    train_targets = [targets[i] for i in train_idx.tolist()]
    class_count = np.bincount(np.array(train_targets, dtype=np.int64), minlength=len(class_names))
    class_count = np.maximum(class_count, 1)
    sample_weights = np.array([1.0 / class_count[label] for label in train_targets], dtype=np.float64)
    train_sampler = WeightedRandomSampler(
        weights=torch.as_tensor(sample_weights, dtype=torch.double),
        num_samples=len(sample_weights),
        replacement=True,
    )
    train_loader = DataLoader(
        train_dataset,
        batch_size=batch_size,
        sampler=train_sampler,
        num_workers=0,
        pin_memory=torch.cuda.is_available(),
    )
    val_loader = DataLoader(
        val_dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=0,
        pin_memory=torch.cuda.is_available(),
    )
    return train_loader, val_loader, class_names


class PathImageDataset(Dataset):
    def __init__(self, samples: list[tuple[Path, int]], transform=None) -> None:
        self.samples = samples
        self.transform = transform

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, index: int):
        image_path, label = self.samples[index]
        image = Image.open(image_path).convert("RGB")
        if self.transform is not None:
            image = self.transform(image)
        return image, label


def collect_samples_from_datasets(
    dataset_dirs: list[Path],
) -> tuple[list[tuple[Path, int]], list[int], list[str]]:
    if not dataset_dirs:
        raise ValueError("No datasets provided.")

    all_classes: set[str] = set()
    loaded_datasets: list[tuple[Path, datasets.ImageFolder]] = []

    for dataset_dir in dataset_dirs:
        if not dataset_dir.exists():
            raise ValueError(f"Dataset path does not exist: {dataset_dir}")
        ds = datasets.ImageFolder(dataset_dir)
        if len(ds.classes) < 1:
            raise ValueError(f"Dataset has no classes: {dataset_dir}")
        loaded_datasets.append((dataset_dir, ds))
        all_classes.update(ds.classes)

    class_names = sorted(all_classes)
    class_to_idx: dict[str, int] = {name: idx for idx, name in enumerate(class_names)}

    samples: list[tuple[Path, int]] = []
    targets: list[int] = []
    for _dataset_dir, ds in loaded_datasets:
        for file_path, old_idx in ds.samples:
            class_name = ds.classes[old_idx]
            mapped_idx = class_to_idx[class_name]
            path_obj = Path(file_path)
            samples.append((path_obj, mapped_idx))
            targets.append(mapped_idx)

    return samples, targets, class_names


def train_one_epoch(
    model: nn.Module,
    loader: DataLoader,
    optimizer: torch.optim.Optimizer,
    criterion: nn.Module,
    device: torch.device,
) -> float:
    model.train()
    running_loss = 0.0
    for images, labels in loader:
        images = images.to(device)
        labels = labels.to(device)

        optimizer.zero_grad(set_to_none=True)
        logits = model(images)
        loss = criterion(logits, labels)
        loss.backward()
        optimizer.step()
        running_loss += loss.item() * images.size(0)

    return running_loss / len(loader.dataset)


def evaluate(
    model: nn.Module,
    loader: DataLoader,
    criterion: nn.Module,
    device: torch.device,
) -> tuple[float, list[int], list[int]]:
    model.eval()
    running_loss = 0.0
    y_true: list[int] = []
    y_pred: list[int] = []

    with torch.no_grad():
        for images, labels in loader:
            images = images.to(device)
            labels = labels.to(device)
            logits = model(images)
            loss = criterion(logits, labels)
            running_loss += loss.item() * images.size(0)

            predictions = torch.argmax(logits, dim=1)
            y_true.extend(labels.cpu().tolist())
            y_pred.extend(predictions.cpu().tolist())

    val_loss = running_loss / len(loader.dataset)
    return val_loss, y_true, y_pred


def save_confusion_matrix(cm: np.ndarray, class_names: list[str], output_path: Path) -> None:
    plt.figure(figsize=(8, 6))
    plt.imshow(cm, interpolation="nearest", cmap=plt.cm.Blues)
    plt.title("Confusion Matrix")
    plt.colorbar()
    ticks = np.arange(len(class_names))
    plt.xticks(ticks, class_names, rotation=45, ha="right")
    plt.yticks(ticks, class_names)
    plt.ylabel("True label")
    plt.xlabel("Predicted label")
    plt.tight_layout()
    plt.savefig(output_path, dpi=180)
    plt.close()


def main() -> None:
    args = parse_args()
    set_seed(args.seed)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    train_loader, val_loader, class_names = get_loaders(
        dataset_dirs=args.dataset,
        image_size=args.image_size,
        batch_size=args.batch_size,
        val_split=args.val_split,
        seed=args.seed,
    )

    model = build_model(args.model, num_classes=len(class_names)).to(device)
    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr)

    best_state = None
    best_f1 = -1.0

    print(f"Training {args.model} on {len(class_names)} classes, device={device}")
    for epoch in range(1, args.epochs + 1):
        train_loss = train_one_epoch(model, train_loader, optimizer, criterion, device)
        val_loss, y_true, y_pred = evaluate(model, val_loader, criterion, device)
        acc = accuracy_score(y_true, y_pred)
        precision, recall, f1, _ = precision_recall_fscore_support(
            y_true, y_pred, average="weighted", zero_division=0
        )
        print(
            f"Epoch {epoch:02d}/{args.epochs} | "
            f"train_loss={train_loss:.4f} val_loss={val_loss:.4f} "
            f"acc={acc:.4f} precision={precision:.4f} recall={recall:.4f} f1={f1:.4f}"
        )

        if f1 > best_f1:
            best_f1 = f1
            best_state = {k: v.cpu() for k, v in model.state_dict().items()}

    if best_state is None:
        raise SystemExit("Training did not produce a valid model state.")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    checkpoint = {
        "model_name": args.model,
        "class_names": class_names,
        "state_dict": best_state,
        "image_size": args.image_size,
    }
    torch.save(checkpoint, args.output)

    # Final validation metrics with the best saved state.
    model.load_state_dict(best_state)
    _, y_true, y_pred = evaluate(model, val_loader, criterion, device)
    accuracy = accuracy_score(y_true, y_pred)
    precision, recall, f1, _ = precision_recall_fscore_support(
        y_true, y_pred, average="weighted", zero_division=0
    )
    cm = confusion_matrix(y_true, y_pred)

    metrics = {
        "accuracy": round(float(accuracy), 6),
        "precision": round(float(precision), 6),
        "recall": round(float(recall), 6),
        "f1_score": round(float(f1), 6),
        "classes": class_names,
    }

    metrics_path = args.output.with_suffix(".metrics.json")
    cm_image_path = args.output.with_suffix(".confusion_matrix.png")
    cm_csv_path = args.output.with_suffix(".confusion_matrix.csv")

    with metrics_path.open("w", encoding="utf-8") as fp:
        json.dump(metrics, fp, indent=2)
    np.savetxt(cm_csv_path, cm, delimiter=",", fmt="%d")
    save_confusion_matrix(cm, class_names, cm_image_path)

    print(f"Checkpoint saved to {args.output}")
    print(f"Metrics saved to {metrics_path}")
    print(f"Confusion matrix saved to {cm_image_path}")


if __name__ == "__main__":
    main()
