from __future__ import annotations

from dataclasses import dataclass
from calendar import monthrange
from datetime import date, datetime, timedelta
import logging
import re
from typing import Any

import numpy as np

from backend.services.climate_weather_service import OpenMeteoClimateService
from backend.services.cultivar_service import get_cultivar
from backend.services.harvest_image_service import HarvestImageService
from backend.services.tunisian_harvest_logic import get_harvest_window, ioc_maturity_class, normalize_cultivar

logger = logging.getLogger(__name__)

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

_TUNISIA_LOCATION_TOKENS = {
    "tunisia",
    "tunis",
    "sfax",
    "sousse",
    "mahdia",
    "kairouan",
    "bizerte",
    "zaghouan",
    "sidi bouzid",
    "nabeul",
    "gabes",
    "sahel",
    "mannouba",
    "jendouba",
    "beja",
}

_NORTH_TUNISIA_TOKENS = {"bizerte", "zaghouan", "beja", "jendouba", "nabeul", "tunis", "mannouba"}
_SOUTH_TUNISIA_TOKENS = {"sfax", "sidi bouzid", "gabes", "medenine", "tataouine", "tozeur", "kebili"}


@dataclass
class HarvestTimeInput:
    image_bytes: bytes
    image_name: str
    sample_date: str | None
    location: str | None
    latitude: float | None
    longitude: float | None
    cultivar: str | None
    cultivar_source: str | None
    intended_use: str
    tree_age: int | None = None
    irrigation_notes: str | None = None
    scene_type: str | None = None
    historical_mi: float | None = None
    debug: bool = False


class HarvestTimeService:
    """One-photo Tunisia-first harvest estimator.

    This service intentionally avoids pseudo-precise oil percentages from a single image.
    It combines visual maturity, weather context, cultivar priors, and intended-use rules.
    """

    def __init__(
        self,
        *,
        harvest_image_service: HarvestImageService,
        weather_service: OpenMeteoClimateService,
    ) -> None:
        self.harvest_image_service = harvest_image_service
        self.weather_service = weather_service

    def predict(self, payload: HarvestTimeInput) -> dict[str, Any]:
        sample_dt = self._parse_date(payload.sample_date)
        location_text = str(payload.location or "").strip()
        cultivar_text = str(payload.cultivar or "Unknown").strip()
        intended_use = self._normalize_intended_use(payload.intended_use)
        debug_enabled = bool(payload.debug)

        debug_trace: dict[str, Any] | None = None
        if debug_enabled:
            debug_trace = {
                "request_context": {
                    "image_name": payload.image_name,
                    "sample_date": sample_dt.isoformat(),
                    "location": location_text,
                    "latitude": payload.latitude,
                    "longitude": payload.longitude,
                    "cultivar": cultivar_text,
                    "intended_use": intended_use,
                    "scene_type": payload.scene_type,
                    "historical_mi_input": payload.historical_mi,
                }
            }

        defaults_applied: list[str] = []
        if normalize_cultivar(cultivar_text) == "unknown" and self._is_tunisia_location(location_text):
            defaults_applied.append("Unknown Tunisian cultivar: cautious default priors applied.")

        cultivar_meta = get_cultivar(cultivar_text)
        target_style = self._target_style_from_use(intended_use, cultivar=str(cultivar_meta.get("cultivar", "Unknown")))
        harvest_window = get_harvest_window(str(cultivar_meta.get("cultivar", "Unknown")), target_style)

        image_analysis = self.harvest_image_service.estimate_visual_maturity(
            image_bytes=payload.image_bytes,
            scene_type=payload.scene_type,
            sample_date=payload.sample_date,
        )
        scene_profile = self._scene_profile(payload.scene_type, image_analysis)
        if debug_trace is not None:
            debug_trace["quality_result"] = {
                "quality_passed": bool(image_analysis.get("quality_passed", False)),
                "quality_warnings": image_analysis.get("quality_warnings", []),
                "blocking_issues": image_analysis.get("blocking_issues", []),
                "brightness": image_analysis.get("brightness"),
                "blur_score": image_analysis.get("blur_score"),
            }
            debug_trace["crop_detection_result"] = {
                "detected_olives": image_analysis.get("detected_olives"),
                "olive_detection_confidence": image_analysis.get("olive_detection_confidence"),
                "fruit_coverage_percent": image_analysis.get("fruit_coverage_percent"),
            }
            debug_trace["preprocessing"] = image_analysis.get("preprocessing", {})
            debug_trace["color_statistics"] = image_analysis.get("color_ratios", {})
            debug_trace["raw_stage_classification"] = image_analysis.get("visual_stage")
            debug_trace["scene_understanding"] = scene_profile
        if not bool(image_analysis.get("quality_passed", False)):
            blocking = image_analysis.get("blocking_issues", []) or ["Image quality check failed."]
            raise ValueError("; ".join(str(item) for item in blocking))

        image_mi = float(np.clip(float(image_analysis.get("image_maturity_index", 0.0)), 0.0, 7.0))

        weather_context = self._weather_context(
            latitude=payload.latitude,
            longitude=payload.longitude,
        )
        if not bool(weather_context.get("weather_available", False)):
            defaults_applied.append("Weather history unavailable; fallback climate profile used.")
        climate_mi, weather_days_adjust, weather_notes = self._climate_adjusted_mi(
            image_mi=image_mi,
            weather_context=weather_context,
        )
        cultivar_mi_adjust, cultivar_days_adjust, cultivar_notes, cautious_unknown_tn = self._cultivar_prior_adjustment(
            cultivar=str(cultivar_meta.get("cultivar", "Unknown")),
            location_text=location_text,
        )
        climate_mi = float(np.clip(climate_mi + cultivar_mi_adjust, 0.0, 7.0))
        weather_days_adjust += cultivar_days_adjust
        if cultivar_notes:
            weather_notes.extend(cultivar_notes)

        historical_mi = float(np.clip(float(payload.historical_mi if payload.historical_mi is not None else image_mi), 0.0, 7.0))
        fused_mi = float(np.clip((0.6 * image_mi) + (0.2 * climate_mi) + (0.2 * historical_mi), 0.0, 7.0))
        season_start_month, season_end_month, season_profile_note = self._season_profile(
            cultivar=str(cultivar_meta.get("cultivar", "Unknown")),
            cultivar_meta=cultivar_meta,
            location_text=location_text,
        )
        if season_profile_note:
            defaults_applied.append(season_profile_note)
        typical_harvest_season = f"{self._month_name(season_start_month)} to {self._month_name(season_end_month)}"
        season_status, next_season_start = self._season_gate(
            sample_dt=sample_dt,
            start_month=season_start_month,
            end_month=season_end_month,
        )

        current_maturity_stage = self._normalize_maturity_stage(
            str(image_analysis.get("visual_stage", "ambiguous")),
            fused_mi=fused_mi,
            image_analysis=image_analysis,
        )
        consistency = "consistent"
        possible_reasons: list[str] = []

        conflict_warning = self._season_maturity_conflict(
            season_status=season_status,
            maturity_stage=current_maturity_stage,
            maturity_index=fused_mi,
            harvest_window=harvest_window,
        )
        if debug_trace is not None:
            debug_trace["season_gate_result"] = {
                "season_status": season_status,
                "start_month": season_start_month,
                "end_month": season_end_month,
                "next_season_start": next_season_start.isoformat(),
                "typical_harvest_season": typical_harvest_season,
            }
            debug_trace["stage_after_override"] = current_maturity_stage
        if conflict_warning:
            defaults_applied.append("Image maturity and season profile conflict; confidence reduced.")
        scene_note = str(scene_profile.get("note", "")).strip()
        if scene_note:
            defaults_applied.append(scene_note)

        days_remaining: int | None = None
        estimated_harvest_date: date | None = None
        recommended_harvest_window: str
        harvest_status: str
        estimated_time_remaining: str
        season_interpretation: str
        estimated_time_until_next_harvest_season: str | None = None

        if season_status == "in season":
            days_raw = self._days_to_harvest(
                mi=fused_mi,
                low=float(harvest_window.low),
                high=float(harvest_window.high),
                weather_day_adjust=weather_days_adjust,
                intended_use=intended_use,
                tree_age=payload.tree_age,
                irrigation_notes=payload.irrigation_notes,
            )
            harvest_status = self._status_from_mi_and_days(
                maturity_stage=current_maturity_stage,
                mi=fused_mi,
                low=float(harvest_window.low),
                high=float(harvest_window.high),
                days=days_raw,
            )
            if self._is_urgent_status(harvest_status):
                days_remaining = 0
                estimated_harvest_date = sample_dt
                recommended_harvest_window = "Immediate (0-3 days)"
                estimated_time_remaining = "now"
            else:
                days_remaining = int(max(days_raw, 0))
                estimated_harvest_date = sample_dt + timedelta(days=days_remaining)
                window_start, window_end = self._recommended_window(
                    sample_dt=sample_dt,
                    days_remaining=days_remaining,
                    status=harvest_status,
                )
                recommended_harvest_window = f"{window_start.isoformat()} to {window_end.isoformat()}"
                estimated_time_remaining = self._time_remaining_text(days_remaining)
            season_interpretation = "In active harvest window"
            next_action = self._next_action(status=harvest_status, days_remaining=days_remaining)
        elif self._is_late_stage(current_maturity_stage):
            consistency = "inconsistent"
            days_to_start = max(0, (next_season_start - sample_dt).days)
            estimated_time_remaining = self._time_remaining_text(days_to_start, until_season=True)
            estimated_time_until_next_harvest_season = estimated_time_remaining
            recommended_harvest_window = self._season_window_text(next_season_start, season_start_month, season_end_month)
            harvest_status = "data inconsistency"
            season_interpretation = "data inconsistency"
            next_action = "Verify sample date and image source, then rescan with a fresh orchard photo."
            possible_reasons = [
                "Wrong sample date.",
                "Old image from another season.",
                "Incorrect cultivar/location metadata.",
            ]
            conflict_warning = "Image suggests mature olives, but current date is outside harvest season."
            defaults_applied.append("Data inconsistency detected between image maturity and harvest season.")
        elif self._is_early_stage(current_maturity_stage):
            harvest_status = "Outside current harvest season"
            days_to_start = max(0, (next_season_start - sample_dt).days)
            estimated_time_remaining = self._time_remaining_text(days_to_start, until_season=True)
            estimated_time_until_next_harvest_season = estimated_time_remaining
            recommended_harvest_window = self._season_window_text(next_season_start, season_start_month, season_end_month)
            season_interpretation = "next season cycle"
            next_action = "Not in active harvest window. This fruit likely belongs to the next cycle; rescan near season start."
        else:
            days_to_start = max(0, (next_season_start - sample_dt).days)
            estimated_time_remaining = self._time_remaining_text(days_to_start, until_season=True)
            estimated_time_until_next_harvest_season = estimated_time_remaining
            recommended_harvest_window = self._season_window_text(next_season_start, season_start_month, season_end_month)
            # Defensive fallback: non-early stage outside season should be treated as inconsistency.
            consistency = "inconsistent"
            harvest_status = "data inconsistency"
            season_interpretation = "data inconsistency"
            next_action = "Verify sample date and image source, then rescan with a fresh orchard photo."
            possible_reasons = [
                "Wrong sample date.",
                "Old image from another season.",
                "Incorrect cultivar/location metadata.",
            ]
            conflict_warning = "Image ripening stage is incompatible with the current sample date."

        season_warning = None if season_status == "in season" else "Prediction outside typical harvest season."
        if season_warning:
            if consistency == "inconsistent":
                defaults_applied.append("Sample date is outside the typical harvest season.")
            else:
                defaults_applied.append("Season gate indicates sample date is outside normal harvest season.")
        if payload.irrigation_notes:
            defaults_applied.append("Irrigation notes were included in the harvest timing adjustment.")

        readiness = self._readiness_percent(
            mi=fused_mi,
            low=float(harvest_window.low),
            high=float(harvest_window.high),
        )
        confidence_label, confidence_score = self._confidence(
            image_analysis=image_analysis,
            weather_context=weather_context,
            cultivar=str(cultivar_meta.get("cultivar", "Unknown")),
            location_text=location_text,
            intended_use=intended_use,
            season_warning=season_warning,
            cautious_unknown_tn=cautious_unknown_tn,
            season_status=season_status,
            conflict_warning=conflict_warning,
            scene_profile=scene_profile,
        )
        if consistency == "inconsistent":
            confidence_label = "Low"
            confidence_score = min(confidence_score, 0.35)

        short_reason = self._short_explanation(
            image_analysis=image_analysis,
            weather_notes=weather_notes,
            season_warning=season_warning,
            maturity_stage=current_maturity_stage,
            season_status=season_status,
            season_interpretation=season_interpretation,
            typical_harvest_season=typical_harvest_season,
            conflict_warning=conflict_warning,
            scene_note=scene_note,
        )

        defaults_applied = self._dedupe_texts(defaults_applied)
        notes = " ".join(
            self._dedupe_texts(
                [
                    "Single-photo estimate combined with cultivar and weather context.",
                    short_reason,
                    season_warning or "",
                    conflict_warning or "",
                ]
            )
        ).strip()

        if debug_trace is not None:
            debug_trace["consistency_logic_result"] = {
                "consistency": consistency,
                "season_interpretation": season_interpretation,
                "conflict_warning": conflict_warning,
                "season_warning": season_warning,
                "possible_reasons": possible_reasons,
            }
            debug_trace["final_decision_after_overrides"] = {
                "harvest_status": harvest_status,
                "estimated_harvest_date": estimated_harvest_date.isoformat() if estimated_harvest_date else None,
                "recommended_harvest_window": recommended_harvest_window,
                "days_remaining": days_remaining,
                "confidence": confidence_label,
                "next_action": next_action,
                "short_reason": short_reason,
            }
            logger.info("Harvest debug trace for %s: %s", payload.image_name, debug_trace)

        return {
            "cultivar": str(cultivar_meta.get("cultivar", "Unknown")),
            "cultivar_source": str(payload.cultivar_source or "user selected"),
            "intended_use": intended_use,
            "sample_date": sample_dt.isoformat(),
            "current_maturity_stage": current_maturity_stage,
            "typical_harvest_season": typical_harvest_season,
            "season_status": season_status,
            "season_interpretation": season_interpretation,
            "estimated_time_until_next_harvest_season": estimated_time_until_next_harvest_season,
            "estimated_time_remaining": estimated_time_remaining,
            "harvest_status": harvest_status,
            "final_harvest_decision": harvest_status,
            "estimated_harvest_date": estimated_harvest_date.isoformat() if estimated_harvest_date else None,
            "recommended_harvest_window": recommended_harvest_window,
            "days_remaining": days_remaining,
            "confidence": confidence_label,
            "confidence_score": confidence_score,
            "consistency": consistency,
            "consistency_status": consistency,
            "consistency_check": consistency,
            "possible_reasons": possible_reasons,
            "short_reason": short_reason,
            "short_explanation": short_reason,
            "next_action": next_action,
            "time_remaining": estimated_time_until_next_harvest_season or estimated_time_remaining,
            "weather_summary": weather_context,
            "defaults_applied": defaults_applied,
            "season_warning": season_warning,
            "scene_analysis": scene_profile,
            "image_analysis": {
                "visual_stage": image_analysis.get("visual_stage"),
                "sample_uniformity": image_analysis.get("sample_uniformity"),
                "stage_ambiguous": bool(image_analysis.get("stage_ambiguous", False)),
                "detected_olives": image_analysis.get("detected_olives"),
                "olive_detection_confidence": image_analysis.get("olive_detection_confidence"),
                "fruit_coverage_percent": image_analysis.get("fruit_coverage_percent"),
                "quality_warnings": image_analysis.get("quality_warnings"),
                "image_maturity_index": round(image_mi, 3),
                "color_ratios": image_analysis.get("color_ratios"),
                "preprocessing": image_analysis.get("preprocessing"),
            },
            "climate_analysis": {
                "weather_available": bool(weather_context.get("weather_available", False)),
                "forecast_available": bool(weather_context.get("forecast_available", False)),
                "temperature_avg": weather_context.get("temperature_avg"),
                "rainfall_total": weather_context.get("rainfall_total"),
                "humidity_avg": weather_context.get("humidity_avg"),
                "solar_radiation": weather_context.get("solar_radiation"),
                "climate_maturity_index": round(climate_mi, 3),
                "weather_notes": weather_notes,
            },
            "final_ai_decision": {
                "current_maturity_stage": current_maturity_stage,
                "typical_harvest_season": typical_harvest_season,
                "season_status": season_status,
                "season_interpretation": season_interpretation,
                "estimated_time_until_next_harvest_season": estimated_time_until_next_harvest_season,
                "estimated_time_remaining": estimated_time_remaining,
                "harvest_status": harvest_status,
                "estimated_harvest_date": estimated_harvest_date.isoformat() if estimated_harvest_date else None,
                "recommended_harvest_window": recommended_harvest_window,
                "days_remaining": days_remaining,
                "confidence": confidence_label,
                "consistency": consistency,
                "consistency_status": consistency,
                "consistency_check": consistency,
                "possible_reasons": possible_reasons,
                "short_reason": short_reason,
                "short_explanation": short_reason,
                "next_action": next_action,
                "final_harvest_decision": harvest_status,
                "time_remaining": estimated_time_until_next_harvest_season or estimated_time_remaining,
            },
            # Compatibility fields for current frontend/backend models.
            "model_name": "HarvestTimeService(OpenMeteo+MaturityFusion)-v1",
            "estimated_oil_content": None,
            "estimated_fcdm": None,
            "estimated_fcfw": None,
            "maturity_stage": current_maturity_stage,
            "harvest_recommendation": next_action,
            "maturity_index_estimate": round(fused_mi, 3),
            "ioc_maturity_class": ioc_maturity_class(fused_mi),
            "tunisian_window": f"{harvest_window.label}: MI {harvest_window.low:.1f}-{harvest_window.high:.1f}",
            "reliability": confidence_label.lower(),
            "ripeness_index": image_analysis.get("ripeness_index"),
            "average_capacitance": 0.0,
            "detected_olives": int(image_analysis.get("detected_olives", 0)),
            "olive_detection_confidence": float(image_analysis.get("olive_detection_confidence", 0.0)),
            "fruit_coverage_percent": float(image_analysis.get("fruit_coverage_percent", 0.0)),
            "fused_maturity_index": round(fused_mi, 3),
            "historical_maturity_index": round(historical_mi, 3),
            "harvest_readiness_percent": round(readiness, 2),
            "image_name": payload.image_name,
            "notes": notes,
            "debug_trace": debug_trace,
        }

    def _parse_date(self, value: str | None) -> date:
        if not value:
            return date.today()
        try:
            return datetime.fromisoformat(str(value)).date()
        except Exception:
            return date.today()

    def _normalize_intended_use(self, value: str | None) -> str:
        raw = str(value or "oil").strip().lower()
        if raw in {"table", "table_olives", "table olives"}:
            return "table_olives"
        return "oil"

    def _target_style_from_use(self, intended_use: str, cultivar: str) -> str:
        if intended_use == "table_olives":
            key = normalize_cultivar(cultivar)
            if key == "meski":
                return "table_green"
            return "table_olives"
        return "premium_oil"

    def _is_tunisia_location(self, location_text: str) -> bool:
        tokens = self._location_tokens(location_text)
        return bool(tokens.intersection(_TUNISIA_LOCATION_TOKENS))

    def _location_tokens(self, location_text: str) -> set[str]:
        return set(re.findall(r"[a-z]+", str(location_text or "").strip().lower()))

    def _weather_context(self, *, latitude: float | None, longitude: float | None) -> dict[str, Any]:
        if latitude is None or longitude is None:
            return {
                "temperature_avg": 23.0,
                "rainfall_total": 10.0,
                "humidity_avg": 62.0,
                "solar_radiation": 18.0,
                "recent_30_days": {},
                "recent_60_days": {},
                "recent_90_days": {},
                "forecast_7_days": {},
                "weather_available": False,
                "forecast_available": False,
                "source": "fallback",
            }

        try:
            history = self.weather_service.fetch_daily_history(
                latitude=float(latitude),
                longitude=float(longitude),
                days=90,
            )
            try:
                forecast = self.weather_service.fetch_daily_forecast(
                    latitude=float(latitude),
                    longitude=float(longitude),
                    days=10,
                )
            except Exception:
                forecast = None
            summary = self.weather_service.summarize_harvest_context(history, forecast)
            summary["source"] = "open-meteo"
            return summary
        except Exception:
            return {
                "temperature_avg": 23.0,
                "rainfall_total": 10.0,
                "humidity_avg": 62.0,
                "solar_radiation": 18.0,
                "recent_30_days": {},
                "recent_60_days": {},
                "recent_90_days": {},
                "forecast_7_days": {},
                "weather_available": False,
                "forecast_available": False,
                "source": "fallback",
            }

    def _climate_adjusted_mi(self, *, image_mi: float, weather_context: dict[str, Any]) -> tuple[float, int, list[str]]:
        notes: list[str] = []
        delta_mi = 0.0
        days_adjust = 0

        temp = float(weather_context.get("temperature_avg", 23.0))
        rain = float(weather_context.get("rainfall_total", 10.0))
        hum = float(weather_context.get("humidity_avg", 62.0))
        forecast = weather_context.get("forecast_7_days", {}) or {}
        f_temp = float(forecast.get("temperature_avg", temp))
        f_rain = float(forecast.get("rainfall_total", 0.0))

        if temp >= 27.0 or f_temp >= 28.0:
            delta_mi += 0.25
            days_adjust -= 3
            notes.append("Warm conditions are likely accelerating ripening.")
        elif temp <= 16.0 or f_temp <= 15.0:
            delta_mi -= 0.25
            days_adjust += 4
            notes.append("Cool conditions may delay ripening.")

        if rain >= 35.0 or f_rain >= 20.0:
            delta_mi -= 0.2
            days_adjust += 3
            notes.append("Recent/forecast rainfall may delay optimal harvest timing.")

        if hum >= 78.0:
            delta_mi -= 0.1
            days_adjust += 1
            notes.append("High humidity increases uncertainty in timing.")

        climate_mi = float(np.clip(image_mi + delta_mi, 0.0, 7.0))
        return climate_mi, days_adjust, notes

    def _cultivar_prior_adjustment(
        self,
        *,
        cultivar: str,
        location_text: str,
    ) -> tuple[float, int, list[str], bool]:
        key = normalize_cultivar(cultivar)
        notes: list[str] = []
        cautious_unknown_tn = False
        if key == "chemlali":
            notes.append("Chemlali prior: slightly earlier ripening tendency considered.")
            return 0.12, -2, notes, cautious_unknown_tn
        if key == "chetoui":
            notes.append("Chetoui prior: medium ripening tendency considered.")
            return 0.05, -1, notes, cautious_unknown_tn
        if key == "unknown" and self._is_tunisia_location(location_text):
            notes.append("Unknown Tunisian cultivar: cautious Tunisia default applied.")
            cautious_unknown_tn = True
            return 0.0, 1, notes, cautious_unknown_tn
        return 0.0, 0, notes, cautious_unknown_tn

    def _days_to_harvest(
        self,
        *,
        mi: float,
        low: float,
        high: float,
        weather_day_adjust: int,
        intended_use: str,
        tree_age: int | None,
        irrigation_notes: str | None,
    ) -> int:
        if mi < low:
            days = int(round(((low - mi) * 12.0) + 5.0))
        elif mi <= high:
            days = int(round(max(0.0, (high - mi) * 7.0)))
        else:
            days = int(round(-1.0 * (mi - high) * 8.0))

        if intended_use == "table_olives":
            days -= 2
        if tree_age is not None:
            try:
                age = int(tree_age)
                if age <= 4:
                    days += 2
                elif age >= 20:
                    days -= 1
            except Exception:
                pass
        notes_text = str(irrigation_notes or "").strip().lower()
        if notes_text:
            if any(token in notes_text for token in ["deficit", "water stress", "dry"]):
                days -= 1
            if any(token in notes_text for token in ["heavy irrigation", "overwater", "wet soil"]):
                days += 1

        days += int(weather_day_adjust)
        return int(np.clip(days, -30, 90))

    def _status_from_mi_and_days(self, *, maturity_stage: str, mi: float, low: float, high: float, days: int) -> str:
        stage = str(maturity_stage or "").strip().lower()
        if stage == "green":
            return "Too early"
        if stage in {"yellow-green", "early stage"}:
            return "Not ready yet"
        if stage == "start of color change":
            return "Approaching harvest"
        if stage == "mature":
            if mi > high or days < 0:
                return "Late / urgent"
            return "Harvest now"

        if mi < (low - 0.5):
            return "Too early"
        if mi < low:
            return "Early but progressing"
        if mi <= high and days > 2:
            return "Near harvest"
        if mi <= high and days <= 2:
            return "Ready now"
        # Safety fallback: never trigger urgent/harvest-now without a true mature stage.
        return "Approaching harvest"

    def _is_urgent_status(self, status: str) -> bool:
        key = str(status or "").strip().lower()
        return key in {"ready now", "late / urgent", "harvest now"} or "urgent" in key or "harvest now" in key

    def _recommended_window(self, *, sample_dt: date, days_remaining: int, status: str) -> tuple[date, date]:
        center = sample_dt + timedelta(days=max(0, days_remaining))
        if status == "Too early":
            return center - timedelta(days=2), center + timedelta(days=6)
        if status == "Not ready yet":
            return center - timedelta(days=2), center + timedelta(days=5)
        if status == "Early but progressing":
            return center - timedelta(days=2), center + timedelta(days=5)
        if status == "Approaching harvest":
            return center - timedelta(days=1), center + timedelta(days=3)
        if status == "Near harvest":
            return center - timedelta(days=1), center + timedelta(days=4)
        if status == "Ready now":
            return sample_dt, sample_dt + timedelta(days=4)
        if status == "Harvest now":
            return sample_dt, sample_dt + timedelta(days=3)
        return sample_dt - timedelta(days=1), sample_dt + timedelta(days=3)

    def _month_from_name(self, value: str | None) -> int | None:
        if not value:
            return None
        return _MONTH_MAP.get(str(value).strip().lower())

    def _month_name(self, month: int) -> str:
        for name, number in _MONTH_MAP.items():
            if number == int(month):
                return name.capitalize()
        return "Unknown"

    def _wrap_month(self, month: int) -> int:
        return ((int(month) - 1) % 12) + 1

    def _season_profile(
        self,
        *,
        cultivar: str,
        cultivar_meta: dict[str, Any],
        location_text: str,
    ) -> tuple[int, int, str | None]:
        start = self._month_from_name(str(cultivar_meta.get("typical_harvest_start") or "")) or 10
        end = self._month_from_name(str(cultivar_meta.get("typical_harvest_end") or "")) or 1
        cultivar_key = normalize_cultivar(cultivar)
        loc_tokens = self._location_tokens(location_text)
        note: str | None = None

        if cultivar_key == "chemlali" and bool(loc_tokens.intersection(_NORTH_TUNISIA_TOKENS)):
            start = self._wrap_month(start + 1)
            end = self._wrap_month(end + 1)
            note = "Regional profile adjustment: cooler north conditions can shift Chemlali harvest later."
        elif cultivar_key == "chetoui" and bool(loc_tokens.intersection(_SOUTH_TUNISIA_TOKENS)):
            start = self._wrap_month(start - 1)
            end = self._wrap_month(end - 1)
            note = "Regional profile adjustment: warmer southern conditions can shift Chetoui harvest earlier."

        return start, end, note

    def _season_gate(self, *, sample_dt: date, start_month: int, end_month: int) -> tuple[str, date]:
        month = int(sample_dt.month)
        if self._month_in_window(month, start_month, end_month):
            next_start = date(sample_dt.year + 1, start_month, 1)
            return "in season", next_start

        months_to_start = (start_month - month) % 12
        if months_to_start == 0:
            months_to_start = 12
        months_from_end = (month - end_month) % 12
        status = "before season"
        if months_from_end <= months_to_start:
            status = "after season"

        start_this_year = date(sample_dt.year, start_month, 1)
        next_start = start_this_year if sample_dt < start_this_year else date(sample_dt.year + 1, start_month, 1)
        return status, next_start

    def _month_in_window(self, month: int, start: int | None, end: int | None) -> bool:
        if start is None or end is None:
            return True
        if start <= end:
            return start <= month <= end
        return month >= start or month <= end

    def _season_window_text(self, next_start: date, start_month: int, end_month: int) -> str:
        start_label = self._month_name(start_month)
        end_label = self._month_name(end_month)
        end_year = next_start.year if end_month >= start_month else next_start.year + 1
        end_day = monthrange(end_year, end_month)[1]
        end_date = date(end_year, end_month, end_day)
        return f"{next_start.isoformat()} to {end_date.isoformat()} ({start_label} to {end_label})"

    def _time_remaining_text(self, days: int, until_season: bool = False) -> str:
        value = int(max(0, days))
        if value <= 3:
            return "now"
        if value < 21:
            return f"about {value} days"
        months = max(1, int(round(value / 30.0)))
        if until_season:
            return f"about {months} months until season start"
        return f"about {months} months"

    def _normalize_maturity_stage(
        self,
        stage: str,
        *,
        fused_mi: float,
        image_analysis: dict[str, Any] | None = None,
    ) -> str:
        raw = str(stage or "").strip().lower()
        color_ratios = (image_analysis or {}).get("color_ratios", {}) if image_analysis else {}
        black_ratio = float((color_ratios or {}).get("black", 0.0) or 0.0)
        purple_ratio = float((color_ratios or {}).get("purple", 0.0) or 0.0)
        turning_ratio = float((color_ratios or {}).get("turning", 0.0) or 0.0)
        green_ratio = float((color_ratios or {}).get("green", 0.0) or 0.0)
        yellow_ratio = float((color_ratios or {}).get("yellow", 0.0) or 0.0)
        dark_ratio = float((color_ratios or {}).get("dark", 0.0) or 0.0)
        dark_low_sat_ratio = float((color_ratios or {}).get("dark_low_sat", 0.0) or 0.0)
        dark_purple_ratio = float((color_ratios or {}).get("dark_purple", 0.0) or 0.0)
        ripeness_index = float((image_analysis or {}).get("ripeness_index", 0.0) or 0.0)
        early_total = green_ratio + yellow_ratio
        early_dominance = early_total >= 0.5
        dark_dominant = black_ratio >= max(0.50, early_total + 0.08)
        has_color_evidence = bool(color_ratios)

        # Mature stage requires strong dark-ripe evidence; strong dark dominance can override mixed foliage noise.
        raw_mature_hint = any(token in raw for token in {"black", "dark", "very mature", "mature"})
        strong_dark_mature = (
            (not early_dominance or dark_dominant)
            and black_ratio >= 0.58
            and dark_ratio >= 0.60
            and (dark_low_sat_ratio >= 0.30 or dark_purple_ratio >= 0.22 or purple_ratio >= 0.10)
        )
        strong_purple_dark_mature = (
            (not early_dominance or dark_dominant)
            and black_ratio >= 0.42
            and purple_ratio >= 0.20
            and dark_ratio >= 0.55
            and fused_mi >= 3.8
        )
        strong_blue_dark_mature = (
            (not early_dominance or dark_dominant)
            and black_ratio >= 0.50
            and dark_ratio >= 0.65
            and dark_purple_ratio >= 0.25
            and fused_mi >= 3.8
        )
        if strong_dark_mature or strong_purple_dark_mature or strong_blue_dark_mature:
            return "mature"
        if raw_mature_hint and not has_color_evidence:
            return "mature"
        if raw_mature_hint and not early_dominance and (black_ratio >= 0.40 or purple_ratio >= 0.35 or dark_purple_ratio >= 0.25):
            return "mature"

        # Mixed green+purple/turning cues should be treated as color-change (ripening).
        if (
            "start of color change" in raw
            or "turning" in raw
            or "mostly purple" in raw
            or "ripening stage" in raw
            or "purple" in raw
            or "violet" in raw
            or purple_ratio >= 0.08
            or turning_ratio >= 0.16
            or (green_ratio >= 0.22 and purple_ratio >= 0.06)
            or (yellow_ratio >= 0.18 and purple_ratio >= 0.06)
            or (ripeness_index >= 0.40 and (purple_ratio >= 0.06 or turning_ratio >= 0.14))
        ):
            return "start of color change"

        # Green-only and green/yellow-green stages.
        if "deep green" in raw:
            return "green"
        if "yellow-green" in raw:
            return "yellow-green"
        if green_ratio >= 0.68 and turning_ratio < 0.22 and purple_ratio < 0.14:
            return "green"
        if green_ratio >= 0.38 and turning_ratio < 0.22 and purple_ratio < 0.14:
            return "yellow-green"

        # Fallbacks.
        if fused_mi >= 3.2:
            return "start of color change"
        if fused_mi >= 2.3:
            return "yellow-green"
        return "green"

    def _season_maturity_conflict(
        self,
        *,
        season_status: str,
        maturity_stage: str,
        maturity_index: float,
        harvest_window: Any,
    ) -> str | None:
        low = float(harvest_window.low)
        if season_status != "in season" and self._is_late_stage(maturity_stage):
            return "Image ripening stage is incompatible with the current sample date."
        if season_status == "before season" and (maturity_stage in {"start of color change"} or maturity_index >= low):
            return "Image ripening stage is incompatible with the current sample date."
        if season_status == "after season" and (maturity_stage in {"green", "early stage"} or maturity_index <= low):
            return "Visual maturity appears early while sample date is after the typical season."
        return None

    def _is_early_stage(self, maturity_stage: str) -> bool:
        return maturity_stage in {"green", "yellow-green", "early stage", "deep green"}

    def _is_late_stage(self, maturity_stage: str) -> bool:
        return maturity_stage in {"start of color change", "mature"}

    def _readiness_percent(self, *, mi: float, low: float, high: float) -> float:
        low = max(0.1, float(low))
        high = max(low + 0.1, float(high))
        if mi < low:
            return float(np.clip((mi / low) * 65.0, 0.0, 65.0))
        if mi <= high:
            return float(np.clip(70.0 + ((mi - low) / (high - low)) * 30.0, 70.0, 100.0))
        return float(np.clip(100.0 - ((mi - high) * 20.0), 15.0, 100.0))

    def _confidence(
        self,
        *,
        image_analysis: dict[str, Any],
        weather_context: dict[str, Any],
        cultivar: str,
        location_text: str,
        intended_use: str,
        season_warning: str | None,
        cautious_unknown_tn: bool,
        season_status: str,
        conflict_warning: str | None,
        scene_profile: dict[str, Any] | None = None,
    ) -> tuple[str, float]:
        score = 0
        weather_available = bool(weather_context.get("weather_available", False))
        warnings = image_analysis.get("quality_warnings", []) or []
        if len(warnings) <= 1:
            score += 1
        if float(image_analysis.get("olive_detection_confidence", 0.0)) >= 0.45:
            score += 1
        if float(image_analysis.get("fruit_coverage_percent", 0.0)) >= 0.4:
            score += 1
        if str(image_analysis.get("sample_uniformity", "")) in {"uniform", "moderately_uniform"}:
            score += 1
        if normalize_cultivar(cultivar) != "unknown":
            score += 1
        else:
            score -= 1
        if location_text:
            score += 1
        if intended_use in {"oil", "table_olives"}:
            score += 1
        if weather_available:
            score += 1
        else:
            score -= 2
        if bool(image_analysis.get("mi_uncertain", False)):
            score -= 1
        if bool(image_analysis.get("stage_ambiguous", False)):
            score -= 1
        if season_warning:
            score -= 1
        if cautious_unknown_tn:
            score -= 1
        if season_status != "in season":
            score -= 2
        if conflict_warning:
            score -= 2
        scene_kind = str((scene_profile or {}).get("normalized_scene", "olives_on_tree"))
        scene_penalty = int((scene_profile or {}).get("confidence_penalty", 0))
        if scene_kind == "olives_on_tree":
            score += 1
        score -= scene_penalty

        normalized = float(np.clip((score + 1) / 8.0, 0.2, 0.95))
        scene_kind = str((scene_profile or {}).get("normalized_scene", "olives_on_tree"))
        capped_to_medium = cautious_unknown_tn or scene_kind in {"harvested_olives_in_hand", "harvested_olives_in_pile", "unclear_scene"}
        if score >= 6 and weather_available and season_status == "in season":
            if capped_to_medium:
                return "Medium", round(min(normalized, 0.79), 2)
            return "High", round(normalized, 2)
        if score >= 3:
            return "Medium", round(normalized, 2)
        return "Low", round(normalized, 2)

    def _short_explanation(
        self,
        *,
        image_analysis: dict[str, Any],
        weather_notes: list[str],
        season_warning: str | None,
        maturity_stage: str,
        season_status: str,
        season_interpretation: str,
        typical_harvest_season: str,
        conflict_warning: str | None,
        scene_note: str | None = None,
    ) -> str:
        stage = str(maturity_stage).replace("_", " ")
        uniformity = str(image_analysis.get("sample_uniformity", "mixed")).replace("_", " ")
        if season_interpretation == "data inconsistency":
            return (
                "Ripening stage and sample date do not match the expected harvest season."
            )
        if season_status == "in season" and maturity_stage == "start of color change":
            return (
                "The olives are in the start-of-color-change stage and the sample date is within the active harvest season. "
                "Harvest is approaching, but the fruit is not yet at full maturity."
            )

        parts = [
            f"Visual stage appears {stage} (sample is {uniformity}). Typical season: {typical_harvest_season}.",
        ]
        if season_status != "in season":
            parts.append(f"Season gate: {season_status}. {season_interpretation}.")
        if season_interpretation == "next season cycle":
            parts.append("Fruit likely belongs to the next production cycle.")
        if scene_note:
            parts.append(scene_note)
        if weather_notes:
            parts.append(weather_notes[0])
        if season_warning:
            parts.append(season_warning)
        if conflict_warning:
            parts.append(conflict_warning)
        return " ".join(self._dedupe_texts(parts))

    def _dedupe_texts(self, values: list[str]) -> list[str]:
        seen: set[str] = set()
        ordered: list[str] = []
        for value in values:
            text = str(value or "").strip()
            if not text:
                continue
            key = text.lower()
            if key in seen:
                continue
            seen.add(key)
            ordered.append(text)
        return ordered

    def _next_action(self, *, status: str, days_remaining: int) -> str:
        if status == "Too early":
            return f"Wait about {max(days_remaining, 7)} days and recheck next week."
        if status == "Not ready yet":
            return "Not ready yet. Monitor color change and recheck in 5-7 days."
        if status == "Early but progressing":
            return "Recheck in 7 days and monitor fruit color progression."
        if status == "Approaching harvest":
            return "Approaching harvest. Recheck in 3-5 days and prepare operations."
        if status == "Near harvest":
            return "Begin harvest preparation and recheck in 3-5 days."
        if status == "Ready now":
            return "Start harvesting now."
        if status == "Harvest now":
            return "Start harvesting now."
        return "Harvest immediately to reduce quality losses."

    def _scene_profile(self, scene_type: str | None, image_analysis: dict[str, Any]) -> dict[str, Any]:
        raw = str(scene_type or "").strip().lower()
        detected = int(image_analysis.get("detected_olives", 0) or 0)
        coverage = float(image_analysis.get("fruit_coverage_percent", 0.0) or 0.0)

        normalized = "olives_on_tree"
        note = ""
        penalty = 0
        reliability = "high"

        if raw in {"harvest_pile", "harvested_olives_in_pile"}:
            normalized = "harvested_olives_in_pile"
            reliability = "medium"
            penalty = 2
            note = "Scene is harvested olives in pile; timing reliability is lower than on-tree sampling."
        elif raw in {"harvested_olives_in_hand", "hand"}:
            normalized = "harvested_olives_in_hand"
            reliability = "medium"
            penalty = 1
            note = "Scene is harvested olives in hand; timing reliability is lower than on-tree sampling."
        elif raw == "fruit_closeup" and detected <= 2 and coverage >= 12.0:
            normalized = "harvested_olives_in_hand"
            reliability = "medium"
            penalty = 1
            note = "Close-up scene may be hand-harvested fruit; timing reliability is lower than on-tree sampling."
        elif raw in {"leaf", "unknown", "unclear_scene"}:
            normalized = "unclear_scene"
            reliability = "low"
            penalty = 2
            note = "Scene is unclear for harvest timing. Prefer olives-on-tree photo for stronger reliability."
        elif raw in {"orchard_branch", "olives_on_tree", "fruit_closeup"}:
            normalized = "olives_on_tree"
            reliability = "high"
            penalty = 0
            note = "Scene appears suitable for on-tree harvest timing."

        return {
            "input_scene_type": raw or "unknown",
            "normalized_scene": normalized,
            "reliability": reliability,
            "confidence_penalty": penalty,
            "note": note,
        }
