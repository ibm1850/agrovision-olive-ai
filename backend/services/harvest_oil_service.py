from __future__ import annotations

from pathlib import Path
from typing import Any

import joblib

from backend.core.config import settings
from backend.services.tunisian_harvest_logic import harvest_decision
from models.train_harvest_model import predict_olive_harvest


class HarvestOilService:
    def __init__(self) -> None:
        self.model_path = Path(settings.harvest_oil_model_path)
        self.bundle: dict[str, Any] | None = None
        self._try_load()

    def _try_load(self) -> None:
        if not self.model_path.exists():
            self.bundle = None
            return

        loaded = joblib.load(self.model_path)
        if not isinstance(loaded, dict) or "pipeline" not in loaded:
            raise RuntimeError(
                f"Invalid harvest model bundle: {self.model_path}. Re-train with models/train_harvest_model.py"
            )
        self.bundle = loaded

    def reload(self) -> None:
        self._try_load()

    def predict(self, measurements: dict[str, Any]) -> dict[str, Any]:
        if not measurements:
            raise ValueError("measurements cannot be empty")

        if self.bundle is None:
            raise RuntimeError(
                "Harvest model not found. Train it first: "
                "python models/train_harvest_model.py --dataset C:\\Users\\Win11\\Downloads\\14754498\\olive-ripening-dataset.csv"
            )

        result = predict_olive_harvest(measurements, self.bundle)
        result["model_name"] = str(self.bundle.get("best_model_name", "unknown"))

        cultivar = str(measurements.get("cultivar") or measurements.get("variety") or "Chemlali")
        target_style = str(measurements.get("target_style") or "premium_oil")
        estimated_oil = float(result.get("estimated_oil_content", 0.0))
        mi_from_oil = max(0.0, min(7.0, (estimated_oil - 10.0) / 2.0))

        decision = harvest_decision(
            cultivar=cultivar,
            target_style=target_style,
            maturity_index=mi_from_oil,
            estimated_oil_content=estimated_oil,
            disease=str(measurements.get("disease") or ""),
            health_score=int(measurements.get("health_score", 0)) if measurements.get("health_score") is not None else None,
        )

        result["maturity_stage"] = str(decision["maturity_stage"])
        result["harvest_recommendation"] = str(decision["harvest_recommendation"])
        result["maturity_index_estimate"] = float(decision["maturity_index_estimate"])
        result["ioc_maturity_class"] = str(decision["ioc_maturity_class"])
        result["tunisian_window"] = str(decision["tunisian_window"])
        result["reliability"] = str(decision["reliability"])
        return result
