from __future__ import annotations

import unittest
from uuid import uuid4
from pathlib import Path

from backend.core.config import settings
from backend.db import history_repo


class HistoryRepoTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_root = Path(__file__).resolve().parents[1] / "tmp"
        self.tmp_root.mkdir(parents=True, exist_ok=True)
        self.original_history_db_path = settings.history_db_path
        self.test_db_path = self.tmp_root / f"analysis_history_{uuid4().hex}.db"
        settings.history_db_path = self.test_db_path
        history_repo.init_db()

    def tearDown(self) -> None:
        settings.history_db_path = self.original_history_db_path
        if self.test_db_path.exists():
            try:
                self.test_db_path.unlink()
            except PermissionError:
                pass

    def test_save_analysis_round_trip(self) -> None:
        history_repo.save_analysis(
            {
                "variety": "Chemlali",
                "health_status": "Healthy",
                "disease": "None",
                "severity": "Mild",
                "health_score": 91,
                "risk_level": "low",
                "harvest_window": "November",
                "image_name": "leaf.jpg",
            }
        )

        rows = history_repo.list_history(limit=5)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["variety"], "Chemlali")
        self.assertEqual(rows[0]["image_name"], "leaf.jpg")

    def test_orchard_record_feedback_round_trip(self) -> None:
        history_repo.save_orchard_record(
            {
                "tree_id": "tree-42",
                "location": "Sfax",
                "disease": "Olive Peacock Spot",
                "leaf_severity": "Moderate",
                "leaf_health_score": 58,
                "infection_percentage": 16.5,
                "confidence": "84%",
                "weather_risk": "high",
                "image_name": "leaf-42.jpg",
            }
        )
        history_repo.update_tree_feedback(
            "tree-42",
            treatment_history="Copper spray",
            farmer_feedback="Symptoms reduced after one week",
        )

        rows = history_repo.list_tree_history("tree-42", limit=5)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["tree_id"], "tree-42")
        self.assertEqual(rows[0]["treatment_history"], "Copper spray")
        self.assertEqual(rows[0]["farmer_feedback"], "Symptoms reduced after one week")

    def test_save_orchard_record_ignores_missing_tree_id(self) -> None:
        history_repo.save_orchard_record(
            {
                "tree_id": "   ",
                "disease": "None",
                "health_score": 100,
            }
        )

        rows = history_repo.list_tree_history("tree-blank", limit=5)
        self.assertEqual(rows, [])

    def test_climate_prediction_round_trip(self) -> None:
        history_repo.save_climate_prediction(
            {
                "user_location": "Sfax",
                "region": "Sfax",
                "latitude": 34.7406,
                "longitude": 10.7603,
                "cultivar": "Chemlali",
                "weather_data": {"temperature_avg": 24.5},
                "maturity_stage": "Optimal Harvest Stage",
                "prediction": {"harvest_window_days": 12},
                "actual_harvest_date": None,
            }
        )

        rows = history_repo.list_climate_predictions(limit=5)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["cultivar"], "Chemlali")
        self.assertEqual(rows[0]["prediction"]["harvest_window_days"], 12)

    def test_observation_analysis_round_trip(self) -> None:
        orchard = history_repo.create_orchard(
            {
                "user_id": "farmer-demo",
                "location": "Sfax",
                "cultivar": "Chemlali",
                "tree_density": 180,
                "planting_year": 2017,
                "latitude": 34.7406,
                "longitude": 10.7603,
            }
        )

        observation_id = history_repo.create_observation(
            {
                "orchard_id": orchard["id"],
                "date": "2026-03-14",
                "image_path": "observations/obs-1.jpg",
                "weather_data": {"humidity_avg": 61.0},
                "scene_type": "fruit_closeup",
                "week_no": 11,
            }
        )
        history_repo.save_observation_analysis(
            observation_id=observation_id,
            maturity_index=3.4,
            oil_estimate=19.2,
            fruit_count=17,
            disease_score=0.1,
            confidence=0.93,
            details={"route": "harvest", "cultivar": "Chemlali"},
        )

        orchard_rows = history_repo.list_orchard_observations(orchard["id"], limit=5)
        series_rows = history_repo.list_orchard_series(orchard["id"])
        orchard_record = history_repo.get_orchard(orchard["id"])

        self.assertEqual(orchard_record["location"], "Sfax")
        self.assertEqual(len(orchard_rows), 1)
        self.assertEqual(orchard_rows[0]["analysis"]["route"], "harvest")
        self.assertEqual(orchard_rows[0]["analysis"]["fruit_count"], 17)
        self.assertEqual(len(series_rows), 1)
        self.assertEqual(series_rows[0]["week_no"], 11)


if __name__ == "__main__":
    unittest.main()
