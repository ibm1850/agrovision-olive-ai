from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from tools.review_queue_app import ReviewStore, sanitize_filename


class ReviewQueueAppTests(unittest.TestCase):
    def test_sanitize_filename(self) -> None:
        self.assertEqual(sanitize_filename("a b/c:d?.jpg"), "a_b_c_d_.jpg")

    def test_save_and_apply_decision_copy(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            img_path = root / "sample image.jpg"
            Image.new("RGB", (32, 32), (120, 180, 90)).save(img_path)

            reports = root / "reports"
            reports.mkdir(parents=True, exist_ok=True)
            queue_csv = reports / "review_queue.csv"
            with queue_csv.open("w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=[
                        "source_path",
                        "source_dataset",
                        "predicted_part",
                        "predicted_label",
                        "combined_confidence",
                        "route_reason",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "source_path": str(img_path),
                        "source_dataset": "tmp",
                        "predicted_part": "leaf",
                        "predicted_label": "unknown",
                        "combined_confidence": "0.31",
                        "route_reason": "unclear",
                    }
                )

            store = ReviewStore(
                queue_csv=queue_csv,
                decisions_csv=reports / "review_decisions.csv",
                decisions_json=reports / "review_decisions.json",
                final_root=root / "final_curated",
            )
            rows = store.list_rows()
            self.assertEqual(len(rows), 1)
            row_id = rows[0]["id"]

            saved = store.save_decision(row_id=row_id, final_label="leaf/healthy_leaf", notes="ok")
            self.assertEqual(saved["final_label"], "leaf/healthy_leaf")

            result = store.apply_moves(mode="copy")
            self.assertEqual(result["moved"], 1)
            self.assertEqual(result["errors"], [])

            targets = list((root / "final_curated" / "leaf" / "healthy_leaf").glob("*.jpg"))
            self.assertEqual(len(targets), 1)


if __name__ == "__main__":
    unittest.main()

