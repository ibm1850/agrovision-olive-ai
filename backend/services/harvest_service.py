from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from backend.core.config import settings

OLIVE_VARIETIES = ["Chemlali", "Chetoui", "Arbequina", "Picholine", "Koroneiki"]
TARGET_HARVEST_MONTH = {
    "Chemlali": 11,
    "Chetoui": 10,
    "Arbequina": 9,
    "Picholine": 11,
    "Koroneiki": 10,
}


class HarvestService:
    def __init__(self) -> None:
        self.model_path = Path(settings.harvest_model_path)
        self.model = self._load_or_create_model()

    def _load_or_create_model(self) -> Pipeline:
        if self.model_path.exists():
            return joblib.load(self.model_path)

        self.model_path.parent.mkdir(parents=True, exist_ok=True)
        model = self._train_synthetic_model()
        joblib.dump(model, self.model_path)
        return model

    def _train_synthetic_model(self) -> Pipeline:
        rng = np.random.default_rng(42)
        rows: list[dict[str, Any]] = []
        for variety in OLIVE_VARIETIES:
            target_month = TARGET_HARVEST_MONTH[variety]
            for current_month in range(1, 13):
                for health_score in range(35, 101, 5):
                    month_diff = (target_month - current_month) % 12
                    base_days = 20 + month_diff * 30
                    # Better health generally means a slightly tighter and earlier window.
                    health_effect = (75 - health_score) * 0.9
                    noise = rng.normal(0, 7)
                    days_to_harvest = max(10, base_days + health_effect + noise)
                    rows.append(
                        {
                            "variety": variety,
                            "current_month": current_month,
                            "health_score": health_score,
                            "days_to_harvest": days_to_harvest,
                        }
                    )

        df = pd.DataFrame(rows)
        preprocessor = ColumnTransformer(
            transformers=[
                ("variety", OneHotEncoder(handle_unknown="ignore"), ["variety"]),
                ("num", "passthrough", ["current_month", "health_score"]),
            ]
        )

        model = Pipeline(
            steps=[
                ("preprocessor", preprocessor),
                ("regressor", RandomForestRegressor(n_estimators=220, random_state=42)),
            ]
        )
        model.fit(
            df[["variety", "current_month", "health_score"]],
            df["days_to_harvest"],
        )
        return model

    def predict_window(
        self,
        variety: str,
        current_month: int,
        health_score: int,
        disease: str | None = None,
        severity: str | None = None,
    ) -> str:
        feature_df = pd.DataFrame(
            [
                {
                    "variety": variety if variety in OLIVE_VARIETIES else "Chemlali",
                    "current_month": int(np.clip(current_month, 1, 12)),
                    "health_score": int(np.clip(health_score, 0, 100)),
                }
            ]
        )
        days_to_harvest = float(self.model.predict(feature_df)[0])
        days_to_harvest = float(np.clip(days_to_harvest, 8, 240))

        harvest_date = date.today() + timedelta(days=int(round(days_to_harvest)))
        uncertainty = int(np.clip(4 + (100 - health_score) / 10, 4, 12))
        window = f"{harvest_date.strftime('%d %B')} +/- {uncertainty} days"

        disease_label = (disease or "").lower().strip()
        severity_label = (severity or "").lower().strip()
        active_disease = disease_label not in {"", "none", "none detected", "healthy"}

        if active_disease and (severity_label in {"moderate", "severe"} or health_score < 60):
            return "Not reliable while disease is active. Treat tree, then re-estimate in 2-3 weeks."
        if active_disease:
            return f"{window} (low reliability: mild disease/stress detected)"
        return window