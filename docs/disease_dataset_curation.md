# Disease Dataset Curation Pipeline

This project includes a semi-automatic curation workflow for Disease Scan datasets:

- Audit source datasets (counts, corrupt files, duplicates, unsupported types, archive contents).
- Auto-route by plant part (`leaf`, `fruit`, `branch_twig`, `unclear`).
- Auto-label only high-confidence obvious samples.
- Send uncertain/conflicting samples to review queues.
- Produce reports and training-ready folder structure.

## 1) Run curation

```powershell
cd C:\Users\Win11\Downloads\pfe\agrovision-ai
.\.venv\Scripts\python.exe models\curate_disease_dataset.py `
  --source "C:\Users\Win11\Downloads\datasets\Olive Tree Diseases - Combined Data.v1i.yolov8" `
  --source "C:\Users\Win11\Downloads\datasets\CNN_olive_dataset-master (1)" `
  --source "C:\Users\Win11\Downloads\datasets" `
  --output-root data\disease_training_data
```

## 2) Review uncertain items

Open:

- `data/disease_training_data/reports/review_queue.csv`

Filter by:

- `route_reason` (`blurry`, `conflicting_labels`, `low_confidence`, `unclear`)
- `predicted_part`
- `predicted_label`

### Optional tiny local web review page

```powershell
cd C:\Users\Win11\Downloads\pfe\agrovision-ai
.\.venv\Scripts\python.exe tools\review_queue_app.py
```

Then open:

- `http://127.0.0.1:8765`

Features:

- one image at a time
- metadata panel (path, dataset, predicted route/label, confidence, reason)
- one-click final labels + keyboard shortcuts
- saves decisions to:
  - `data/disease_training_data/reports/review_decisions.csv`
  - `data/disease_training_data/reports/review_decisions.json`
- **Apply Moves** button moves labeled files to:
  - `data/disease_training_data/final_curated/...`

## 3) Train models only after cleanup

Print training commands:

```powershell
.\.venv\Scripts\python.exe models\train_curated_disease_models.py `
  --curated-root data\disease_training_data `
  --output-dir models\curated
```

Execute training:

```powershell
.\.venv\Scripts\python.exe models\train_curated_disease_models.py `
  --curated-root data\disease_training_data `
  --output-dir models\curated `
  --execute
```

This trains:

- `models/curated/plant_part_router.pt`
- `models/curated/leaf_disease_model.pt`
- `models/curated/fruit_disease_model.pt`
- `models/curated/branch_disease_model.pt`
