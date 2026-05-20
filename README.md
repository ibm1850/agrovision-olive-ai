# AgroVision Olive AI (v2)

AgroVision Olive AI is a FastAPI + React application for olive leaf disease analysis with realistic agronomy constraints.

## Implemented Core Logic

- Multi-leaf image analysis (`1..n` leaf images per request)
- Image quality validation before inference:
  - blur check
  - resolution check
  - leaf detection check
- Leaf crop / background reduction before model heuristics
- Disease classes:
  - Healthy leaf
  - Olive Peacock Spot (Spilocaea oleaginea)
  - Olive Anthracnose
  - Aculus Olearius (olive mite damage)
  - Olive Scab / Tuberculosis
  - Uncertain diagnosis fallback
- Severity by infection area / lesion burden
- Infection percentage calculation
- Health score formula: `100 - (infection_percentage * 1.5)`
- Confidence caps:
  - 1 leaf: max 85%
  - 3+ leaves: max 93%
  - tree image included: max 97%
  - borderline quality: forced below 70%
- Harvest output constraint for leaf-only context:
  - `Cannot be estimated from leaf disease image.`
- Weather risk integration (OpenWeather) for peacock spot conditions
- Orchard history database with `tree_id`

## Project Structure

```text
agrovision-ai/
  backend/
    api/
    core/
    db/
    services/
    main.py
  frontend/
    src/
  data/
  models/
  utils/
  requirements.txt
```

## Backend Setup

```bash
cd agrovision-ai
python -m venv .venv
# PowerShell
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m uvicorn backend.main:app --reload
# If PowerShell policy blocks activation, run directly:
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload
```

Backend: `http://127.0.0.1:8000`

## Frontend Setup

```bash
cd agrovision-ai/frontend
npm install
npm run dev
```

Frontend: `http://127.0.0.1:5173`

## Quality Checks

Backend unit tests:

```bash
cd agrovision-ai
.\.venv\Scripts\python.exe -m unittest discover -s tests -t . -v
```

Frontend production build:

```bash
cd agrovision-ai/frontend
npm.cmd run build
```

## Optional Weather API

Set an OpenWeather key:

```bash
# PowerShell
$env:OPENWEATHER_API_KEY="your_key"
```

## Main API Endpoints

- `POST /predict-tree`
- `POST /predict-harvest`
- `POST /predict-harvest-image`
- `POST /detect-olives`
- `POST /chat`
- `POST /voice`
- `GET /history`
- `GET /orchard/{tree_id}`
- `POST /orchard/feedback`

## Harvest Time Farm Management API

New production-oriented farm management routes:

- `GET /farm/profile`
- `POST /farm/profile`
- `GET /farm/profile/{farm_id}`
- `PUT /farm/profile/{farm_id}`
- `GET /farm/{farm_id}/tree-groups`
- `POST /farm/{farm_id}/tree-groups`
- `PUT /farm/{farm_id}/tree-groups/{group_id}`
- `DELETE /farm/{farm_id}/tree-groups/{group_id}`
- `GET /farm/{farm_id}/scans`
- `POST /farm/{farm_id}/scans`
- `PUT /farm/{farm_id}/scans/{scan_id}/status`
- `GET /farm/{farm_id}/alerts`
- `GET /farm/{farm_id}/notes`
- `POST /farm/{farm_id}/notes`
- `PUT /farm/{farm_id}/notes/{note_id}/status`
- `GET /farm/{farm_id}/dashboard`

## /predict-tree Request (multipart)

Fields:

- `file`: single leaf image (optional if `files` used)
- `files`: multiple leaf images (optional if `file` used)
- `tree_image`: optional tree image
- `tree_id`: optional
- `location`: optional (used for weather risk)
- `season`: optional
- `tree_age`: optional

## /predict-tree Response (key fields)

```json
{
  "variety": "Unknown",
  "disease": "Olive Peacock Spot (Spilocaea oleaginea)",
  "leaf_severity": "Moderate",
  "leaf_health_score": 73,
  "confidence": "85%",
  "notes": "Diagnosis based on leaf-level analysis only.",
  "harvest_window": "Cannot be estimated from leaf disease image.",
  "infection_percentage": 18.0,
  "leaf_count": 1,
  "weather_risk": "high"
}
```

## Using Your Local OpenAI JSONL Dataset

If you want to include:

`C:\Users\Win11\Downloads\Olive disease detection.v3i.openai`

convert it first to ImageFolder (`healthy` / `diseased`):

```bash
cd agrovision-ai
python data/import_openai_jsonl_dataset.py ^
  --source "C:\Users\Win11\Downloads\Olive disease detection.v3i.openai" ^
  --output data/openai_olive_imagefolder
```

You can also include:

`C:\Users\Win11\Downloads\Olive Tree Diseases.v1i.openai`

This one is multi-class (`Anthracnose`, `OlivePeacockSpot`, `Tuberculosis`, etc):

```bash
python data/import_openai_jsonl_dataset.py ^
  --source "C:\Users\Win11\Downloads\Olive Tree Diseases.v1i.openai" ^
  --output data/olive_tree_diseases_v1_imagefolder ^
  --label-mode auto
```

Then you can merge datasets during training by repeating `--dataset`:

```bash
python models/train_classifier.py ^
  --dataset data/primary_imagefolder ^
  --dataset data/openai_olive_imagefolder ^
  --dataset data/olive_tree_diseases_v1_imagefolder ^
  --output models/disease_model.pt ^
  --model efficientnet_b0 ^
  --epochs 10
```

## Harvest Prediction Module (Fruit Measurements)

Dataset used:

- `C:\Users\Win11\Downloads\14754498\olive-ripening-dataset.csv`

Train the harvest model:

```bash
cd agrovision-ai
python models/train_harvest_model.py ^
  --dataset "C:\Users\Win11\Downloads\14754498\olive-ripening-dataset.csv" ^
  --output models/olive_harvest_model.pkl
```

This training script performs:

- dataset inspection (shape, columns, summary, missing values)
- preprocessing + feature normalization
- model training/evaluation:
  - `RandomForestRegressor`
  - `GradientBoostingRegressor`
  - `LinearRegression`
- best-model selection by metrics (`R2`, `MAE`, `MSE`)
- maturity stage mapping and harvest recommendation logic
- model save (`olive_harvest_model.pkl`)
- optional plots in `models/harvest_plots/`

API request example:

`POST /predict-harvest`

```json
{
  "measurements": {
    "Week No.": 4,
    "Set number": 77,
    "Measurement 1": 61.2,
    "Measurement 2": 74.5,
    "Measurement 3": 72.1,
    "Measurement 4": 75.8,
    "Measurement 5": 82.4,
    "Measurement 6": 81.7,
    "Measurement 7": 84.9,
    "Measurement 8": 92.3,
    "Measurement 9": 83.8,
    "Measurement 10": 80.1,
    "Measurement 11": 85.6,
    "Measurement 12": 87.4,
    "Measurement 13": 90.1,
    "Measurement 14": 88.7,
    "Measurement 15": 89.2,
    "Average capacitance (nF)": 82.6
  }
}
```

API response example:

```json
{
  "estimated_oil_content": 18.4,
  "estimated_fcdm": 42.3,
  "estimated_fcfw": 18.4,
  "maturity_stage": "Optimal Harvest Stage",
  "harvest_recommendation": "Recommended harvest window",
  "model_name": "RandomForestRegressor"
}
```

## YOLOv8 Olive Fruit Detection Module

Local dataset path:

- `C:\Users\Win11\Downloads\olive-fruit-detection.v1i.yolov8`
- `data.yaml`: `C:\Users\Win11\Downloads\olive-fruit-detection.v1i.yolov8\data.yaml`

### 1) Install dependencies

```bash
pip install ultralytics opencv-python numpy pandas
```

### 2) Train detector

```bash
cd agrovision-ai
python models/train_olive_detector.py ^
  --data "C:\Users\Win11\Downloads\olive-fruit-detection.v1i.yolov8\data.yaml" ^
  --epochs 120 ^
  --imgsz 640 ^
  --batch 4 ^
  --workers 2 ^
  --patience 20 ^
  --weights yolov8s.pt ^
  --output models/olive_detector_best.pt
```

Training uses:

- `YOLO(\"yolov8s.pt\")`
- verifies train/valid/test splits from `data.yaml`
- applies augmentation (`hsv/degrees/translate/scale/mosaic/mixup`)
- copies best weights to `models/olive_detector_best.pt`

### 3) Test detection + crop olives

```bash
python models/detect_olives.py ^
  --model models/olive_detector_best.pt ^
  --image olive_test.jpg ^
  --crop-dir cropped_olives ^
  --conf 0.65 ^
  --iou 0.35 ^
  --imgsz 640 ^
  --min-box-area 2500 ^
  --max-box-area-ratio 0.35 ^
  --min-aspect-ratio 0.4 ^
  --max-aspect-ratio 2.5 ^
  --viz-out olive_detection_visualized.jpg
```

Output JSON shape:

```json
{
  "detected_olives": 5,
  "avg_confidence": 0.81,
  "confidence_scores": [0.93, 0.88, 0.82],
  "bounding_boxes": [[x1, y1, x2, y2]],
  "cropped_files": ["cropped_olives/olive_001.jpg"],
  "visualized_image": "olive_detection_visualized.jpg"
}
```

### 4) API endpoint for uploaded images

`POST /detect-olives` (multipart form-data)

Fields:

- `file`: image file
- `conf`: optional confidence threshold (default `0.65`)
- `iou`: optional NMS IoU threshold (default `0.35`)
- `imgsz`: optional inference size (default `640`)
- `min_box_area`: optional minimum area filter (default `2500`)
- `max_box_area_ratio`: optional max box area / image area ratio (default `0.35`)
- `min_aspect_ratio`: optional minimum width/height box ratio (default `0.4`)
- `max_aspect_ratio`: optional maximum width/height box ratio (default `2.5`)

### 5) Add new orchard photos to YOLO dataset (auto count + pseudo labels)

1. Put new images in a folder, for example:
   - `C:\Users\Win11\Downloads\olive_new_photos`
2. Run:

```bash
python models/add_olive_images_to_dataset.py ^
  --input-dir "C:\Users\Win11\Downloads\olive_new_photos" ^
  --data-yaml "C:\Users\Win11\Downloads\olive-fruit-detection.v1i.yolov8\data.yaml" ^
  --model models/olive_detector_best.pt ^
  --target-split train
```

This command will:
- print olive count for each photo
- save images into `train/images`
- save YOLO labels into `train/labels`
- write a summary json in `data/olive_additions_summary.json`

Image-scan harvest endpoint:

`POST /predict-harvest-image` (multipart form-data)

Fields:

- `file` (required image)
- `sample_date` (optional, `YYYY-MM-DD`)
- `week_no` (optional, `1..52`)

## Notes

- If confidence drops below 70%, the disease field is set to:
  - `Diagnosis uncertain - upload clearer leaf image`
- The current implementation is optimized for realistic constraints and mobile-ready backend behavior.
- YOLOv8/U-Net training pipelines are represented by the modular service structure and can be plugged in with trained weights.
