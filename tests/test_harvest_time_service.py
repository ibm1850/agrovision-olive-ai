from __future__ import annotations

import unittest
from pathlib import Path

from backend.services.harvest_image_service import HarvestImageService
from backend.services.harvest_oil_service import HarvestOilService
from backend.services.harvest_time_service import HarvestTimeInput, HarvestTimeService


class _FakeHarvestImageService:
    def __init__(self, analysis: dict) -> None:
        self.analysis = analysis

    def estimate_visual_maturity(self, **_: object) -> dict:
        return dict(self.analysis)


class _FakeWeatherService:
    def __init__(self, summary: dict | None = None, fail: bool = False) -> None:
        self.summary = summary or {}
        self.fail = fail

    def fetch_daily_history(self, latitude: float, longitude: float, days: int = 90) -> dict:
        if self.fail:
            raise RuntimeError("weather unavailable")
        return {"latitude": latitude, "longitude": longitude, "days": days}

    def fetch_daily_forecast(self, latitude: float, longitude: float, days: int = 10) -> dict:
        if self.fail:
            raise RuntimeError("forecast unavailable")
        return {"latitude": latitude, "longitude": longitude, "days": days}

    def summarize_harvest_context(self, history_payload: dict, forecast_payload: dict) -> dict:
        if self.fail:
            raise RuntimeError("summary unavailable")
        payload = dict(self.summary)
        payload.setdefault("temperature_avg", 23.0)
        payload.setdefault("rainfall_total", 8.0)
        payload.setdefault("humidity_avg", 62.0)
        payload.setdefault("solar_radiation", 18.0)
        payload.setdefault("recent_30_days", {})
        payload.setdefault("recent_60_days", {})
        payload.setdefault("recent_90_days", {})
        payload.setdefault("forecast_7_days", {})
        payload.setdefault("weather_available", True)
        payload.setdefault("forecast_available", True)
        payload.setdefault("history_series", [])
        payload.setdefault("forecast_series", [])
        return payload


def _base_analysis(mi: float, stage: str) -> dict:
    return {
        "quality_passed": True,
        "blocking_issues": [],
        "image_maturity_index": mi,
        "visual_stage": stage,
        "sample_uniformity": "uniform",
        "quality_warnings": [],
        "mi_uncertain": False,
        "stage_ambiguous": False,
        "detected_olives": 4,
        "olive_detection_confidence": 0.74,
        "fruit_coverage_percent": 2.4,
        "ripeness_index": 0.48,
    }


class HarvestTimeServiceTests(unittest.TestCase):
    def _service(self, analysis: dict, weather_summary: dict | None = None, weather_fail: bool = False) -> HarvestTimeService:
        return HarvestTimeService(
            harvest_image_service=_FakeHarvestImageService(analysis),
            weather_service=_FakeWeatherService(summary=weather_summary, fail=weather_fail),
        )

    def _payload(self, **overrides: object) -> HarvestTimeInput:
        base = {
            "image_bytes": b"fake-image",
            "image_name": "olive.jpg",
            "sample_date": "2026-12-15",
            "location": "Sfax, Tunisia",
            "latitude": 34.74,
            "longitude": 10.76,
            "cultivar": "Chemlali Sfax",
            "cultivar_source": "user selected",
            "intended_use": "oil",
            "tree_age": 10,
            "irrigation_notes": None,
            "scene_type": "fruit_closeup",
            "historical_mi": None,
        }
        base.update(overrides)
        return HarvestTimeInput(**base)

    def test_green_olives_are_too_early(self) -> None:
        service = self._service(_base_analysis(0.9, "deep green"))
        result = service.predict(self._payload(sample_date="2026-08-15"))
        self.assertEqual(result["season_status"], "before season")
        self.assertEqual(result["harvest_status"], "Outside current harvest season")
        self.assertEqual(result["season_interpretation"], "next season cycle")
        self.assertIsNone(result["estimated_harvest_date"])
        self.assertIsNotNone(result["estimated_time_until_next_harvest_season"])
        self.assertIn("until season start", result["estimated_time_until_next_harvest_season"])
        self.assertEqual(result["current_maturity_stage"], "green")
        self.assertIn("recommended_harvest_window", result)
        self.assertIn("typical_harvest_season", result)

    def test_turning_olives_are_near_harvest(self) -> None:
        service = self._service(_base_analysis(3.45, "start of color change"))
        result = service.predict(self._payload())
        self.assertEqual(result["season_status"], "in season")
        self.assertEqual(result["harvest_status"], "Approaching harvest")
        self.assertLessEqual(result["days_remaining"], 14)
        self.assertIsNotNone(result["estimated_harvest_date"])

    def test_mature_olives_can_be_ready_now(self) -> None:
        warm_weather = {
            "temperature_avg": 30.0,
            "rainfall_total": 3.0,
            "humidity_avg": 55.0,
            "solar_radiation": 21.0,
            "forecast_7_days": {"temperature_avg": 31.0, "rainfall_total": 0.0, "humidity_avg": 52.0},
            "weather_available": True,
            "forecast_available": True,
        }
        service = self._service(_base_analysis(3.6, "mostly purple"), weather_summary=warm_weather)
        result = service.predict(self._payload())
        self.assertEqual(result["season_status"], "in season")
        # mostly-purple maps to start-of-color-change, so should be approaching harvest (not too early).
        self.assertEqual(result["harvest_status"], "Approaching harvest")
        self.assertGreaterEqual(result["days_remaining"], 0)
        self.assertEqual(result["current_maturity_stage"], "start of color change")

    def test_missing_weather_degrades_confidence(self) -> None:
        service = self._service(_base_analysis(3.3, "start of color change"), weather_fail=True)
        result = service.predict(self._payload())
        self.assertFalse(result["weather_summary"]["weather_available"])
        self.assertIn(result["confidence"], {"Low", "Medium"})
        self.assertTrue(any("Weather history unavailable" in note for note in result["defaults_applied"]))

    def test_poor_quality_blocks_prediction(self) -> None:
        analysis = _base_analysis(2.8, "ambiguous")
        analysis["quality_passed"] = False
        analysis["blocking_issues"] = ["Image is too blurry for reliable maturity estimation."]
        service = self._service(analysis)

        with self.assertRaises(ValueError) as ctx:
            service.predict(self._payload())

        self.assertIn("too blurry", str(ctx.exception).lower())

    def test_unknown_cultivar_in_tunisia_uses_cautious_defaults(self) -> None:
        service = self._service(_base_analysis(3.0, "start of color change"))
        result = service.predict(
            self._payload(
                cultivar="Unknown",
                cultivar_source="user selected",
                location="Mahdia, Tunisia",
            )
        )
        self.assertEqual(result["cultivar"], "Unknown")
        self.assertIn("Unknown Tunisian cultivar", " ".join(result["defaults_applied"]))
        self.assertIn(result["confidence"], {"Low", "Medium"})

    def test_after_season_returns_post_season_without_exact_date(self) -> None:
        service = self._service(_base_analysis(2.9, "yellow-green"))
        result = service.predict(self._payload(sample_date="2026-03-10"))
        self.assertEqual(result["season_status"], "after season")
        self.assertEqual(result["harvest_status"], "Outside current harvest season")
        self.assertEqual(result["season_interpretation"], "next season cycle")
        self.assertIsNone(result["estimated_harvest_date"])
        self.assertIsNotNone(result["estimated_time_until_next_harvest_season"])
        self.assertIn("until season start", result["estimated_time_until_next_harvest_season"])

    def test_after_season_advanced_stage_is_not_active_window(self) -> None:
        service = self._service(_base_analysis(4.8, "mature black"))
        result = service.predict(self._payload(sample_date="2026-03-10"))
        self.assertEqual(result["season_status"], "after season")
        self.assertEqual(result["harvest_status"], "data inconsistency")
        self.assertEqual(result["season_interpretation"], "data inconsistency")
        self.assertEqual(result["consistency"], "inconsistent")
        self.assertEqual(result["consistency_status"], "inconsistent")
        self.assertEqual(result["confidence"], "Low")
        self.assertTrue(result["possible_reasons"])
        self.assertIn("do not match the expected harvest season", result["short_reason"])
        self.assertIsNone(result["estimated_harvest_date"])

    def test_black_visual_stage_outside_season_is_inconsistent(self) -> None:
        service = self._service(_base_analysis(2.6, "black / very mature"))
        result = service.predict(self._payload(sample_date="2026-04-15"))
        self.assertEqual(result["current_maturity_stage"], "mature")
        self.assertEqual(result["consistency"], "inconsistent")
        self.assertEqual(result["harvest_status"], "data inconsistency")
        self.assertIn("do not match the expected harvest season", result["short_reason"])

    def test_turning_stage_outside_season_is_inconsistent(self) -> None:
        service = self._service(_base_analysis(2.8, "start of color change"))
        result = service.predict(self._payload(sample_date="2026-04-15"))
        self.assertEqual(result["season_status"], "after season")
        self.assertEqual(result["current_maturity_stage"], "start of color change")
        self.assertEqual(result["season_interpretation"], "data inconsistency")
        self.assertEqual(result["consistency"], "inconsistent")
        self.assertEqual(result["harvest_status"], "data inconsistency")

    def test_yellow_green_outside_season_stays_next_cycle(self) -> None:
        # Guard against false mature labels for green/yellow-green fruit.
        service = self._service(_base_analysis(3.8, "yellow-green"))
        result = service.predict(self._payload(sample_date="2026-04-15"))
        self.assertEqual(result["season_status"], "after season")
        self.assertEqual(result["current_maturity_stage"], "yellow-green")
        self.assertEqual(result["season_interpretation"], "next season cycle")
        self.assertEqual(result["consistency"], "consistent")
        self.assertEqual(result["harvest_status"], "Outside current harvest season")

    def test_yellow_green_in_season_is_not_ready_yet(self) -> None:
        service = self._service(_base_analysis(2.4, "yellow-green"))
        result = service.predict(self._payload(sample_date="2026-12-15"))
        self.assertEqual(result["season_status"], "in season")
        self.assertEqual(result["current_maturity_stage"], "yellow-green")
        self.assertEqual(result["harvest_status"], "Not ready yet")

    def test_mixed_color_in_season_is_approaching_harvest(self) -> None:
        analysis = _base_analysis(2.6, "yellow-green")
        analysis["color_ratios"] = {
            "green": 0.46,
            "turning": 0.31,
            "purple": 0.18,
            "black": 0.12,
        }
        service = self._service(analysis)
        result = service.predict(self._payload(sample_date="2026-12-15"))
        self.assertEqual(result["season_status"], "in season")
        self.assertEqual(result["current_maturity_stage"], "start of color change")
        self.assertEqual(result["harvest_status"], "Approaching harvest")
        self.assertIn("Harvest is approaching", result["short_reason"])

    def test_purple_mixed_in_season_does_not_fall_back_to_green(self) -> None:
        analysis = _base_analysis(2.5, "green")
        analysis["ripeness_index"] = 0.52
        analysis["color_ratios"] = {
            "green": 0.51,
            "turning": 0.18,
            "purple": 0.09,
            "black": 0.1,
        }
        service = self._service(analysis)
        result = service.predict(self._payload(sample_date="2026-12-15"))
        self.assertEqual(result["season_status"], "in season")
        self.assertEqual(result["current_maturity_stage"], "start of color change")
        self.assertEqual(result["harvest_status"], "Approaching harvest")
        self.assertEqual(result["consistency"], "consistent")
        self.assertIn("start-of-color-change", result["short_reason"])

    def test_late_urgent_in_season_uses_immediate_window_and_today_date(self) -> None:
        service = self._service(_base_analysis(6.2, "mature black"))
        result = service.predict(self._payload(sample_date="2026-12-20"))
        self.assertEqual(result["season_status"], "in season")
        self.assertEqual(result["harvest_status"], "Late / urgent")
        self.assertEqual(result["days_remaining"], 0)
        self.assertEqual(result["estimated_harvest_date"], "2026-12-20")
        self.assertEqual(result["recommended_harvest_window"], "Immediate (0-3 days)")

    def test_mature_in_season_can_be_harvest_now(self) -> None:
        service = self._service(_base_analysis(4.5, "mature black"))
        result = service.predict(self._payload(sample_date="2026-12-10"))
        self.assertEqual(result["season_status"], "in season")
        self.assertIn(result["harvest_status"], {"Harvest now", "Late / urgent"})

    def test_shadowy_green_image_is_not_false_mature(self) -> None:
        analysis = _base_analysis(4.9, "black / very mature")
        analysis["ripeness_index"] = 0.34
        analysis["color_ratios"] = {
            "green": 0.43,
            "yellow": 0.22,
            "turning": 0.08,
            "purple": 0.04,
            "black": 0.24,
            "dark": 0.34,
            "dark_low_sat": 0.29,
        }
        service = self._service(analysis)
        result = service.predict(self._payload(sample_date="2026-12-15"))
        self.assertNotEqual(result["current_maturity_stage"], "mature")
        self.assertNotIn(result["harvest_status"], {"Harvest now", "Late / urgent"})
        self.assertEqual(result["consistency"], "consistent")

    def test_true_dark_mature_signal_stays_mature(self) -> None:
        analysis = _base_analysis(5.4, "black / very mature")
        analysis["ripeness_index"] = 0.78
        analysis["color_ratios"] = {
            "green": 0.06,
            "yellow": 0.03,
            "turning": 0.09,
            "purple": 0.34,
            "black": 0.72,
            "dark": 0.77,
            "dark_low_sat": 0.71,
        }
        service = self._service(analysis)
        result = service.predict(self._payload(sample_date="2026-12-15"))
        self.assertEqual(result["current_maturity_stage"], "mature")
        self.assertIn(result["harvest_status"], {"Harvest now", "Late / urgent"})

    def test_regression_exact_image_olive_wood_578415(self) -> None:
        fixture = Path(__file__).resolve().parent / "fixtures" / "olive-wood-artisans-of-tunisia-578415.webp"
        self.assertTrue(fixture.exists(), f"Missing fixture: {fixture}")
        image_bytes = fixture.read_bytes()

        service = HarvestTimeService(
            harvest_image_service=HarvestImageService(HarvestOilService()),
            weather_service=_FakeWeatherService(),
        )
        result = service.predict(
            HarvestTimeInput(
                image_bytes=image_bytes,
                image_name=fixture.name,
                sample_date="2026-11-09",
                location="Sfax, Tunisia",
                latitude=34.7406,
                longitude=10.7603,
                cultivar="Chemlali",
                cultivar_source="user selected",
                intended_use="oil",
                scene_type="harvest_pile",
                historical_mi=None,
                debug=True,
            )
        )

        self.assertEqual(result["season_status"], "in season")
        self.assertEqual(result["current_maturity_stage"], "start of color change")
        self.assertEqual(result["harvest_status"], "Approaching harvest")
        self.assertEqual(result["consistency"], "consistent")
        self.assertIsInstance(result.get("debug_trace"), dict)
        self.assertIn("quality_result", result["debug_trace"])
        self.assertIn("color_statistics", result["debug_trace"])
        self.assertIn("final_decision_after_overrides", result["debug_trace"])

    def test_regression_exact_image_fruoli_chemlali_dark_ripe(self) -> None:
        fixture = Path(__file__).resolve().parent / "fixtures" / "FRUOLI-CHEMLALI-2.jpg"
        self.assertTrue(fixture.exists(), f"Missing fixture: {fixture}")
        image_bytes = fixture.read_bytes()

        service = HarvestTimeService(
            harvest_image_service=HarvestImageService(HarvestOilService()),
            weather_service=_FakeWeatherService(),
        )
        result = service.predict(
            HarvestTimeInput(
                image_bytes=image_bytes,
                image_name=fixture.name,
                sample_date="2026-12-09",
                location="Sfax, Tunisia",
                latitude=34.7406,
                longitude=10.7603,
                cultivar="Chemlali Sfax",
                cultivar_source="user selected",
                intended_use="oil",
                scene_type="orchard_branch",
                historical_mi=None,
                debug=True,
            )
        )

        self.assertEqual(result["season_status"], "in season")
        self.assertEqual(result["current_maturity_stage"], "mature")
        self.assertIn(result["harvest_status"], {"Harvest now", "Late / urgent"})
        self.assertEqual(result["consistency"], "consistent")
        self.assertIn(result["recommended_harvest_window"], {"Immediate (0-3 days)", "today to 3 days"})

    def test_green_on_tree_in_april_is_outside_season_next_cycle(self) -> None:
        service = self._service(_base_analysis(0.9, "deep green"))
        result = service.predict(self._payload(sample_date="2026-04-15", scene_type="orchard_branch"))
        self.assertEqual(result["current_maturity_stage"], "green")
        self.assertEqual(result["harvest_status"], "Outside current harvest season")
        self.assertEqual(result["season_interpretation"], "next season cycle")
        self.assertEqual(result["consistency"], "consistent")
        self.assertIsNone(result["estimated_harvest_date"])

    def test_turning_on_tree_in_april_is_inconsistent(self) -> None:
        service = self._service(_base_analysis(3.1, "start of color change"))
        result = service.predict(self._payload(sample_date="2026-04-15", scene_type="orchard_branch"))
        self.assertEqual(result["current_maturity_stage"], "start of color change")
        self.assertEqual(result["harvest_status"], "data inconsistency")
        self.assertEqual(result["consistency"], "inconsistent")
        self.assertIsNone(result["estimated_harvest_date"])

    def test_mature_on_tree_in_april_is_inconsistent(self) -> None:
        service = self._service(_base_analysis(5.2, "black / very mature"))
        result = service.predict(self._payload(sample_date="2026-04-15", scene_type="orchard_branch"))
        self.assertEqual(result["current_maturity_stage"], "mature")
        self.assertEqual(result["harvest_status"], "data inconsistency")
        self.assertEqual(result["consistency"], "inconsistent")
        self.assertIsNone(result["estimated_harvest_date"])

    def test_mixed_purple_green_in_november_is_approaching_harvest(self) -> None:
        analysis = _base_analysis(2.7, "yellow-green")
        analysis["color_ratios"] = {
            "green": 0.42,
            "yellow": 0.18,
            "turning": 0.26,
            "purple": 0.16,
            "black": 0.11,
            "dark": 0.14,
            "dark_low_sat": 0.09,
        }
        service = self._service(analysis)
        result = service.predict(self._payload(sample_date="2026-11-20", scene_type="orchard_branch"))
        self.assertEqual(result["current_maturity_stage"], "start of color change")
        self.assertEqual(result["harvest_status"], "Approaching harvest")
        self.assertEqual(result["consistency"], "consistent")
        self.assertIsNotNone(result["estimated_harvest_date"])

    def test_green_or_yellow_green_in_november_is_not_ready(self) -> None:
        green_service = self._service(_base_analysis(1.0, "deep green"))
        green_result = green_service.predict(self._payload(sample_date="2026-11-20", scene_type="orchard_branch"))
        self.assertEqual(green_result["current_maturity_stage"], "green")
        self.assertEqual(green_result["harvest_status"], "Too early")
        self.assertEqual(green_result["consistency"], "consistent")
        self.assertIsNotNone(green_result["estimated_harvest_date"])

        yellow_service = self._service(_base_analysis(2.4, "yellow-green"))
        yellow_result = yellow_service.predict(self._payload(sample_date="2026-11-20", scene_type="orchard_branch"))
        self.assertEqual(yellow_result["current_maturity_stage"], "yellow-green")
        self.assertEqual(yellow_result["harvest_status"], "Not ready yet")
        self.assertEqual(yellow_result["consistency"], "consistent")
        self.assertIsNotNone(yellow_result["estimated_harvest_date"])

    def test_harvested_olives_in_hand_reduces_confidence(self) -> None:
        service = self._service(_base_analysis(3.2, "start of color change"))
        result = service.predict(self._payload(sample_date="2026-12-10", scene_type="harvested_olives_in_hand"))
        self.assertEqual(result["scene_analysis"]["normalized_scene"], "harvested_olives_in_hand")
        self.assertIn(result["scene_analysis"]["reliability"], {"medium", "low"})
        self.assertIn(result["confidence"], {"Medium", "Low"})
        self.assertTrue(any("lower than on-tree" in note.lower() for note in result["defaults_applied"]))

    def test_harvested_olives_in_pile_reduces_confidence(self) -> None:
        service = self._service(_base_analysis(3.2, "start of color change"))
        result = service.predict(self._payload(sample_date="2026-12-10", scene_type="harvested_olives_in_pile"))
        self.assertEqual(result["scene_analysis"]["normalized_scene"], "harvested_olives_in_pile")
        self.assertIn(result["scene_analysis"]["reliability"], {"medium", "low"})
        self.assertIn(result["confidence"], {"Medium", "Low"})
        self.assertTrue(any("lower than on-tree" in note.lower() for note in result["defaults_applied"]))


if __name__ == "__main__":
    unittest.main()
