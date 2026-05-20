from __future__ import annotations

import os
from pathlib import Path


class Settings:
    def __init__(self) -> None:
        self.base_dir = Path(__file__).resolve().parents[2]
        self.models_dir = self.base_dir / "models"
        self.data_dir = self.base_dir / "data"

        self.variety_model_path = Path(
            os.getenv("VARIETY_MODEL_PATH", str(self.models_dir / "variety_model.pt"))
        )
        curated_leaf_model = self.models_dir / "curated" / "leaf_disease_model.pt"
        default_disease_model = self.models_dir / "disease_model.pt"
        self.disease_model_path = Path(
            os.getenv(
                "DISEASE_MODEL_PATH",
                str(curated_leaf_model if curated_leaf_model.exists() else default_disease_model),
            )
        )
        self.harvest_model_path = Path(
            os.getenv("HARVEST_MODEL_PATH", str(self.models_dir / "harvest_rf.joblib"))
        )
        self.harvest_oil_model_path = Path(
            os.getenv("HARVEST_OIL_MODEL_PATH", str(self.models_dir / "olive_harvest_model.pkl"))
        )
        curated_scene_model = self.models_dir / "curated" / "plant_part_router.pt"
        default_scene_model = self.models_dir / "scene_classifier_model.pt"
        self.scene_classifier_model_path = Path(
            os.getenv(
                "SCENE_CLASSIFIER_MODEL_PATH",
                str(curated_scene_model if curated_scene_model.exists() else default_scene_model),
            )
        )
        self.olive_detection_model_path = Path(
            os.getenv("OLIVE_DETECTION_MODEL_PATH", str(self.models_dir / "olive_detector_best.pt"))
        )
        self.pre_detection_model_path = Path(
            os.getenv(
                "PRE_DETECTION_MODEL_PATH",
                str(self.models_dir / "leaf_roi_detector.pt"),
            )
        )
        self.pre_detection_conf = float(os.getenv("PRE_DETECTION_CONF", "0.25"))
        self.pre_detection_iou = float(os.getenv("PRE_DETECTION_IOU", "0.45"))
        self.cropped_olives_dir = Path(
            os.getenv("CROPPED_OLIVES_DIR", str(self.base_dir / "data" / "cropped_olives"))
        )
        self.observations_dir = Path(
            os.getenv("OBSERVATIONS_DIR", str(self.base_dir / "data" / "observations"))
        )
        self.history_db_path = Path(
            os.getenv("HISTORY_DB_PATH", str(self.base_dir / "data" / "analysis_history.db"))
        )

        self.ollama_url = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434/api/generate")
        self.ollama_model = os.getenv("OLLAMA_MODEL", "mistral")
        self.whisper_model = os.getenv("WHISPER_MODEL", "tiny")
        self.openweather_api_key = os.getenv("OPENWEATHER_API_KEY", "")
        self.openweather_url = os.getenv(
            "OPENWEATHER_URL", "https://api.openweathermap.org/data/2.5/weather"
        )
        self.default_weather_units = os.getenv("OPENWEATHER_UNITS", "metric")
        self.allowed_origins = os.getenv(
            "ALLOWED_ORIGINS", "http://127.0.0.1:5173,http://localhost:5173"
        ).split(",")


settings = Settings()
