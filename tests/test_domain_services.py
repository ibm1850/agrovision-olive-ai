from __future__ import annotations

import unittest

from backend.services.alert_service import generate_alerts
from backend.services.climate_harvest_service import ClimateHarvestInput, ClimateHarvestService
from backend.services.cultivar_service import resolve_cultivar
from backend.services.tunisian_harvest_logic import (
    estimate_maturity_index,
    get_harvest_window,
    harvest_decision,
    ioc_maturity_class,
)
from backend.services.tunisia_geo_service import nearest_region
from backend.services.weather_service import WeatherRiskService


class DomainServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.climate_service = ClimateHarvestService()

    def test_resolve_cultivar_prefers_user_selection(self) -> None:
        resolved = resolve_cultivar(
            user_selected="Meski",
            ai_detected="Chemlali",
            location="Sfax",
        )

        self.assertEqual(resolved["cultivar"], "Meski")
        self.assertEqual(resolved["source"], "user selected")

    def test_resolve_cultivar_falls_back_to_regional_estimate(self) -> None:
        resolved = resolve_cultivar(
            user_selected="Unknown",
            ai_detected="Unknown",
            location="Sfax, Tunisia",
        )

        self.assertEqual(resolved["cultivar"], "Chemlali Sfax")
        self.assertEqual(resolved["source"], "regional estimate")

    def test_nearest_region_matches_sfax_coordinates(self) -> None:
        region = nearest_region(34.7406, 10.7603)

        self.assertEqual(region["region"], "Sfax")
        self.assertAlmostEqual(region["distance_km"], 0.0, places=2)

    def test_generate_alerts_combines_harvest_disease_and_weather_signals(self) -> None:
        alerts = generate_alerts(
            latest_analysis={"disease": "Olive Peacock Spot", "health_score": 51},
            weather={"humidity_avg": 78, "temperature_avg": 16, "rainfall_total": 4},
            climate_prediction={"harvest_window_days": 10},
        )

        alert_types = {item["type"] for item in alerts}
        self.assertSetEqual(
            alert_types,
            {"harvest_approaching", "high_disease_risk", "fruit_fly_risk"},
        )

    def test_harvest_decision_flags_disease_limited_cases(self) -> None:
        decision = harvest_decision(
            cultivar="Chemlali",
            target_style="premium_oil",
            maturity_index=3.2,
            estimated_oil_content=19.5,
            disease="Olive Peacock Spot",
            health_score=42,
        )

        self.assertEqual(decision["maturity_stage"], "Disease-limited decision")
        self.assertEqual(decision["reliability"], "low")

    def test_harvest_window_and_ioc_helpers_return_expected_ranges(self) -> None:
        window = get_harvest_window("Chemlali", "premium_oil")
        maturity_index = estimate_maturity_index(0.5)

        self.assertEqual(window.label, "Chemlali premium oil window")
        self.assertEqual((window.low, window.high), (3.0, 4.0))
        self.assertEqual(maturity_index, 3.5)
        self.assertEqual(ioc_maturity_class(maturity_index), "MI 3-4 (mid veraison)")

    def test_climate_harvest_prediction_stays_within_safe_bounds(self) -> None:
        prediction = self.climate_service.predict(
            ClimateHarvestInput(
                cultivar="Chemlali",
                location="Sfax",
                maturity_stage="Optimal Harvest Stage",
                temperature_avg=29.5,
                rainfall_total=18.0,
                humidity_avg=60.0,
                solar_radiation=21.0,
                disease="None",
                health_score=88,
            )
        )

        self.assertGreaterEqual(prediction["estimated_oil_content"], 8.0)
        self.assertLessEqual(prediction["estimated_oil_content"], 30.0)
        self.assertGreaterEqual(prediction["harvest_window_days"], 3)
        self.assertLessEqual(prediction["harvest_window_days"], 45)
        self.assertGreaterEqual(prediction["harvest_readiness_percent"], 0.0)
        self.assertLessEqual(prediction["harvest_readiness_percent"], 100.0)
        self.assertEqual(prediction["model_name"], "RandomForestRegressor")

    def test_weather_service_returns_safe_defaults_without_inputs(self) -> None:
        service = WeatherRiskService()
        service.api_key = ""

        no_location = service.peacock_spot_risk(None)
        unavailable = service.peacock_spot_risk("Sfax")

        self.assertEqual(no_location["status"], "not_requested")
        self.assertEqual(unavailable["status"], "unavailable")
        self.assertEqual(unavailable["risk"], "unknown")


if __name__ == "__main__":
    unittest.main()
