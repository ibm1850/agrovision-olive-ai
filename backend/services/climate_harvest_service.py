from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import numpy as np
from sklearn.ensemble import RandomForestRegressor

from backend.services.cultivar_service import get_cultivar
from backend.services.tunisian_harvest_logic import get_harvest_window, harvest_decision


@dataclass
class ClimateHarvestInput:
    cultivar: str
    location: str
    maturity_stage: str
    temperature_avg: float
    rainfall_total: float
    humidity_avg: float
    solar_radiation: float
    disease: str = "None"
    health_score: int = 85


class ClimateHarvestService:
    def __init__(self) -> None:
        self.model = self._build_bootstrap_model()

    def _build_bootstrap_model(self):
        rng = np.random.default_rng(42)
        n = 1200
        temp = rng.uniform(12, 34, n)
        rain = rng.uniform(0, 120, n)
        hum = rng.uniform(35, 90, n)
        solar = rng.uniform(8, 28, n)
        maturity_index = rng.uniform(0.2, 6.8, n)
        cultivar_idx = rng.integers(0, 5, n)

        fcfw = (
            10.5
            + 1.6 * maturity_index
            + 0.08 * (24 - np.abs(temp - 24))
            - 0.018 * np.maximum(0, rain - 55)
            + 0.012 * solar
            - 0.008 * np.maximum(0, hum - 75)
            + 0.35 * cultivar_idx
            + rng.normal(0, 0.45, n)
        )
        fcfw = np.clip(fcfw, 10, 26)
        fcdm = (fcfw * 2.35) + 4.0 + rng.normal(0, 0.9, n)
        fcdm = np.clip(fcdm, 26, 58)

        x = np.vstack([maturity_index, temp, rain, hum, solar, cultivar_idx]).T
        y = np.vstack([fcdm, fcfw]).T
        model = RandomForestRegressor(
            n_estimators=320,
            max_depth=14,
            min_samples_leaf=2,
            random_state=42,
            # Keep bootstrap training portable in restricted environments.
            n_jobs=1,
        )
        model.fit(x, y)
        return model

    def _stage_to_numeric(self, maturity_stage: str) -> float:
        s = (maturity_stage or "").lower()
        if "immature" in s or "green" in s:
            return 0.2
        if "early" in s:
            return 0.4
        if "optimal" in s or "purple" in s or "mid" in s:
            return 0.65
        if "late" in s or "black" in s:
            return 0.85
        return 0.55

    def _cultivar_to_idx(self, cultivar: str) -> int:
        options = ["chemlali", "chetoui", "meski", "oueslati", "zarrazi"]
        raw = (cultivar or "").strip().lower()
        for idx, value in enumerate(options):
            if value in raw:
                return idx
        return 0

    def _apply_agronomic_rules(self, payload: ClimateHarvestInput, base_days: int) -> tuple[int, list[str]]:
        notes: list[str] = []
        days = int(base_days)
        cultivar_key = (payload.cultivar or "").lower()
        region_key = (payload.location or "").lower()

        if "chemlali" in cultivar_key and "sfax" in region_key:
            notes.append("Chemlali in Sfax: expected harvest season November-January.")

        if payload.rainfall_total > 40:
            days += 4
            notes.append("Recent rainfall is high: delaying harvest estimate slightly.")

        if payload.temperature_avg > 30:
            days -= 4
            notes.append("High average temperature: ripening likely accelerated.")

        if payload.humidity_avg > 75:
            days += 2
            notes.append("High humidity: increased disease/quality risk, be cautious with delay.")

        return max(3, min(45, days)), notes

    def predict(self, payload: ClimateHarvestInput) -> dict[str, Any]:
        stage_num = self._stage_to_numeric(payload.maturity_stage)
        maturity_index = float(np.clip(stage_num * 7.0, 0.0, 7.0))
        cultivar_idx = self._cultivar_to_idx(payload.cultivar)
        x = np.array(
            [
                [
                    maturity_index,
                    payload.temperature_avg,
                    payload.rainfall_total,
                    payload.humidity_avg,
                    payload.solar_radiation,
                    cultivar_idx,
                ]
            ],
            dtype=float,
        )
        pred = self.model.predict(x)[0]
        fcdm_pred = float(np.clip(pred[0], 20.0, 65.0))
        fcfw_pred = float(np.clip(pred[1], 8.0, 30.0))
        oil_pred = fcfw_pred

        base_days = int(round(32 - (oil_pred - 12) * 1.7 - stage_num * 8))
        adjusted_days, notes = self._apply_agronomic_rules(payload, base_days=base_days)
        start = datetime.now().date() + timedelta(days=max(1, adjusted_days - 2))
        end = datetime.now().date() + timedelta(days=adjusted_days + 2)

        climate_mi = float(np.clip((oil_pred - 10.0) / 2.0, 0.0, 7.0))
        mi_guess = climate_mi
        decision = harvest_decision(
            cultivar=payload.cultivar,
            target_style="premium_oil",
            maturity_index=mi_guess,
            estimated_oil_content=oil_pred,
            disease=payload.disease,
            health_score=payload.health_score,
        )

        confidence = 0.82
        if payload.rainfall_total > 60:
            confidence -= 0.08
        if payload.humidity_avg > 80:
            confidence -= 0.05
        if payload.temperature_avg < 12 or payload.temperature_avg > 34:
            confidence -= 0.07
        confidence = float(max(0.55, min(0.95, confidence)))

        window = get_harvest_window(payload.cultivar, "premium_oil")
        if mi_guess < float(window.low):
            readiness = float(np.clip((mi_guess / max(window.low, 0.1)) * 65.0, 0.0, 65.0))
        elif mi_guess <= float(window.high):
            readiness = 70.0 + float(np.clip((mi_guess - window.low) / max(window.high - window.low, 0.1), 0.0, 1.0)) * 30.0
        else:
            readiness = float(np.clip(100.0 - ((mi_guess - window.high) * 22.0), 15.0, 100.0))

        cultivar_meta = get_cultivar(payload.cultivar)
        return {
            "location": payload.location,
            "cultivar": payload.cultivar,
            "cultivar_metadata": cultivar_meta,
            "maturity_stage": payload.maturity_stage,
            "temperature_avg": round(payload.temperature_avg, 3),
            "rainfall_last_30_days": round(payload.rainfall_total, 3),
            "humidity_avg": round(payload.humidity_avg, 3),
            "solar_radiation": round(payload.solar_radiation, 3),
            "estimated_oil_content": round(oil_pred, 3),
            "predicted_oil_content": round(oil_pred, 3),
            "estimated_fcdm": round(fcdm_pred, 3),
            "estimated_fcfw": round(fcfw_pred, 3),
            "harvest_window_days": adjusted_days,
            "harvest_window": f"{start.isoformat()} to {end.isoformat()}",
            "harvest_recommendation": decision["harvest_recommendation"],
            "recommendation": decision["harvest_recommendation"],
            "confidence_score": round(confidence, 3),
            "climate_maturity_index": round(mi_guess, 3),
            "harvest_readiness_percent": round(readiness, 2),
            "ioc_maturity_class": decision["ioc_maturity_class"],
            "tunisian_window": decision["tunisian_window"],
            "agronomic_notes": notes,
            "model_name": "RandomForestRegressor",
        }
