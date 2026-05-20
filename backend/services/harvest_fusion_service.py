from __future__ import annotations

from datetime import date, datetime
from typing import Any

import numpy as np

from backend.services.tunisian_harvest_logic import get_harvest_window, harvest_decision

_MONTH_MAP = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}


class HarvestFusionService:
    def _month_to_int(self, value: str | None) -> int | None:
        if not value:
            return None
        return _MONTH_MAP.get(str(value).strip().lower())

    def _month_in_window(self, month: int, start_month: int | None, end_month: int | None) -> bool:
        if start_month is None or end_month is None:
            return True
        if start_month <= end_month:
            return start_month <= month <= end_month
        return month >= start_month or month <= end_month

    def _parse_harvest_start(self, harvest_window: str | None) -> date | None:
        if not harvest_window:
            return None
        raw = str(harvest_window).strip()
        if not raw:
            return None
        left = raw.split("to")[0].strip()
        try:
            return datetime.fromisoformat(left).date()
        except Exception:
            return None

    def _readiness_percent(self, mi: float, low: float, high: float) -> float:
        if low <= 0:
            low = 0.1
        if high <= low:
            high = low + 0.1

        if mi < low:
            return float(np.clip((mi / low) * 65.0, 0.0, 65.0))
        if mi <= high:
            pos = (mi - low) / (high - low)
            return float(np.clip(70.0 + (pos * 30.0), 70.0, 100.0))
        penalty = (mi - high) * 22.0
        return float(np.clip(100.0 - penalty, 15.0, 100.0))

    def fuse(
        self,
        *,
        image_mi: float,
        image_oil_estimate: float,
        climate_mi: float,
        climate_oil_estimate: float,
        historical_mi: float,
        cultivar: str,
        target_style: str,
        cultivar_harvest_start: str | None,
        cultivar_harvest_end: str | None,
        predicted_harvest_window: str | None,
        disease: str | None = None,
        health_score: int | None = None,
        scene_type: str | None = None,
        reference_date: date | None = None,
    ) -> dict[str, Any]:
        image_mi = float(np.clip(image_mi, 0.0, 7.0))
        climate_mi = float(np.clip(climate_mi, 0.0, 7.0))
        historical_mi = float(np.clip(historical_mi, 0.0, 7.0))
        image_oil_estimate = float(np.clip(image_oil_estimate, 0.0, 100.0))
        climate_oil_estimate = float(np.clip(climate_oil_estimate, 0.0, 100.0))

        fused_mi = float(
            np.clip(
                (0.6 * image_mi) + (0.2 * climate_mi) + (0.2 * historical_mi),
                0.0,
                7.0,
            )
        )
        fused_oil = float((image_oil_estimate + climate_oil_estimate) / 2.0)

        window = get_harvest_window(cultivar, target_style)
        final = harvest_decision(
            cultivar=cultivar,
            target_style=target_style,
            maturity_index=fused_mi,
            estimated_oil_content=fused_oil,
            disease=disease,
            health_score=health_score,
        )

        image_override_after_window = image_mi > float(window.high)
        if image_override_after_window:
            final["maturity_stage"] = "After target window"
            final["harvest_recommendation"] = (
                f"After target window: image maturity index ({image_mi:.2f}) is above the cultivar limit "
                f"({window.high:.2f}). Climate estimate cannot override image maturity evidence."
            )
            final["reliability"] = "high"

        readiness = self._readiness_percent(fused_mi, float(window.low), float(window.high))

        start_month = self._month_to_int(cultivar_harvest_start)
        end_month = self._month_to_int(cultivar_harvest_end)
        predicted_start = self._parse_harvest_start(predicted_harvest_window)
        effective_date = predicted_start or reference_date or date.today()
        in_season = self._month_in_window(effective_date.month, start_month, end_month)

        season_warning = None
        if not in_season and not image_override_after_window:
            season_warning = "Prediction outside typical harvest season."
            final["maturity_stage"] = "Prediction rejected"
            final["harvest_recommendation"] = season_warning
            final["reliability"] = "low"
            readiness = float(min(readiness, 35.0))
        elif not in_season:
            season_warning = "Prediction outside typical harvest season."
            final["harvest_recommendation"] = (
                str(final["harvest_recommendation"]).strip() + " " + season_warning
            ).strip()

        if str(scene_type or "").strip().lower() == "harvest_pile":
            note_prefix = "Scene correction applied: harvest_pile -> fruit counting disabled. "
        else:
            note_prefix = ""

        return {
            "image_analysis": {
                "maturity_index": round(image_mi, 3),
                "oil_estimate": round(image_oil_estimate, 3),
            },
            "climate_analysis": {
                "maturity_index": round(climate_mi, 3),
                "oil_estimate": round(climate_oil_estimate, 3),
                "harvest_window": predicted_harvest_window,
            },
            "final_ai_decision": {
                "maturity_stage": str(final["maturity_stage"]),
                "harvest_recommendation": str(final["harvest_recommendation"]),
                "ioc_maturity_class": str(final["ioc_maturity_class"]),
                "tunisian_window": str(final["tunisian_window"]),
                "reliability": str(final["reliability"]),
            },
            "fused_maturity_index": round(fused_mi, 3),
            "fused_oil_estimate": round(fused_oil, 3),
            "historical_maturity_index": round(historical_mi, 3),
            "harvest_readiness_percent": round(readiness, 2),
            "season_valid": in_season,
            "season_warning": season_warning,
            "notes": note_prefix + str(final.get("notes", "")),
        }
