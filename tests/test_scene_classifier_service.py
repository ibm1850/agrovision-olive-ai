from __future__ import annotations

import unittest
from pathlib import Path

from backend.services.scene_classifier_service import SceneClassifierService, normalize_scene_label


class SceneClassifierServiceTests(unittest.TestCase):
    def test_normalize_scene_label_maps_curated_router_classes(self) -> None:
        self.assertEqual(normalize_scene_label("leaf"), "leaf")
        self.assertEqual(normalize_scene_label("branch_twig"), "orchard_branch")
        self.assertEqual(normalize_scene_label("fruit"), "fruit_closeup")
        self.assertEqual(normalize_scene_label("unknown_label"), "unknown")

    def test_fruoli_branch_scene_is_not_false_pile(self) -> None:
        fixture = Path(__file__).resolve().parent / "fixtures" / "FRUOLI-CHEMLALI-2.jpg"
        self.assertTrue(fixture.exists(), f"Missing fixture: {fixture}")
        image_bytes = fixture.read_bytes()

        service = SceneClassifierService()
        # Keep this regression deterministic and independent from optional trained scene weights.
        service.model = None
        result = service.classify(image_bytes)

        self.assertEqual(result.get("scene_type"), "orchard_branch")
        self.assertNotEqual(result.get("scene_type"), "harvest_pile")


if __name__ == "__main__":
    unittest.main()
