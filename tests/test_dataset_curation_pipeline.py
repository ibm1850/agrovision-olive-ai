from __future__ import annotations

import unittest
from pathlib import Path

import numpy as np

from models.curate_disease_dataset import (
    QualityMetrics,
    compute_quality,
    decide_destination,
    detect_source_label,
    map_leaf_disease,
)


class DatasetCurationPipelineTests(unittest.TestCase):
    def test_detect_source_label_from_keywords(self) -> None:
        label, conf = detect_source_label("train/maladie_oeil_de_paon-20.jpg")
        self.assertEqual(label, "olive_peacock_spot")
        self.assertGreater(conf, 0.5)

    def test_map_leaf_disease(self) -> None:
        self.assertEqual(map_leaf_disease("Olive Peacock Spot (Spilocaea oleaginea)"), "olive_peacock_spot")
        self.assertEqual(map_leaf_disease("Aculus Olearius (olive mite damage)"), "aculus_olearius")
        self.assertEqual(map_leaf_disease("Healthy leaf"), "healthy_leaf")
        self.assertIsNone(map_leaf_disease("Diagnosis uncertain - upload clearer leaf image"))

    def test_compute_quality_flags_blur_and_small_images(self) -> None:
        img = np.full((120, 120, 3), 180, dtype=np.uint8)
        q = compute_quality(img)
        self.assertTrue(q.too_small)
        self.assertTrue(q.is_blurry)

    def test_decide_destination_auto_label(self) -> None:
        q = QualityMetrics(
            blur_score=90.0,
            brightness=130.0,
            saturation=70.0,
            texture_std=32.0,
            is_blurry=False,
            too_dark=False,
            too_bright=False,
            too_small=False,
            no_visible_symptom_like=False,
        )
        split, reason, _ = decide_destination(
            output_root=Path("data/disease_training_data"),
            part="leaf",
            predicted_label="olive_peacock_spot",
            conf=0.9,
            quality=q,
            conflicting=False,
            high_conf=0.82,
            medium_conf=0.62,
        )
        self.assertEqual(split, "auto_labeled")
        self.assertEqual(reason, "high_confidence")

    def test_decide_destination_review_conflict(self) -> None:
        q = QualityMetrics(
            blur_score=90.0,
            brightness=130.0,
            saturation=70.0,
            texture_std=32.0,
            is_blurry=False,
            too_dark=False,
            too_bright=False,
            too_small=False,
            no_visible_symptom_like=False,
        )
        split, reason, _ = decide_destination(
            output_root=Path("data/disease_training_data"),
            part="leaf",
            predicted_label="healthy_leaf",
            conf=0.95,
            quality=q,
            conflicting=True,
            high_conf=0.82,
            medium_conf=0.62,
        )
        self.assertEqual(split, "review_needed")
        self.assertEqual(reason, "conflicting_labels")


if __name__ == "__main__":
    unittest.main()

