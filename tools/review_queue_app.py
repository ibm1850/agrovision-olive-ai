from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parents[1]
UI_INDEX = BASE_DIR / "tools" / "review_queue_ui" / "index.html"

LABEL_CHOICES: list[dict[str, str]] = [
    {"label": "leaf/healthy_leaf", "shortcut": "1"},
    {"label": "leaf/olive_peacock_spot", "shortcut": "2"},
    {"label": "leaf/aculus_olearius", "shortcut": "3"},
    {"label": "leaf/uncertain_leaf", "shortcut": "4"},
    {"label": "fruit/healthy_fruit", "shortcut": "5"},
    {"label": "fruit/olive_anthracnose", "shortcut": "6"},
    {"label": "fruit/uncertain_fruit", "shortcut": "7"},
    {"label": "branch/healthy_branch", "shortcut": "8"},
    {"label": "branch/olive_scab_tuberculosis", "shortcut": "9"},
    {"label": "branch/uncertain_branch", "shortcut": "0"},
    {"label": "reject/no_visible_symptom", "shortcut": "q"},
    {"label": "reject/wrong_part", "shortcut": "w"},
    {"label": "reject/blurry", "shortcut": "e"},
]


def sanitize_filename(name: str, max_len: int = 100) -> str:
    allowed = []
    for ch in name:
        if ch.isalnum() or ch in {".", "_", "-"}:
            allowed.append(ch)
        else:
            allowed.append("_")
    value = "".join(allowed).strip("._-")
    if not value:
        value = "image"
    return value[:max_len]


class SaveDecisionRequest(BaseModel):
    row_id: str
    final_label: str
    notes: str = ""


class ApplyMovesRequest(BaseModel):
    mode: str = "move"  # move | copy


class ReviewStore:
    def __init__(
        self,
        *,
        queue_csv: Path,
        decisions_csv: Path,
        decisions_json: Path,
        final_root: Path,
    ) -> None:
        self.queue_csv = queue_csv
        self.decisions_csv = decisions_csv
        self.decisions_json = decisions_json
        self.final_root = final_root
        self.rows: list[dict[str, Any]] = []
        self.row_index: dict[str, dict[str, Any]] = {}
        self.decisions: dict[str, dict[str, Any]] = {}
        self._load_queue()
        self._load_decisions()

    def _load_queue(self) -> None:
        if not self.queue_csv.exists():
            raise FileNotFoundError(f"review_queue.csv not found: {self.queue_csv}")
        rows: list[dict[str, Any]] = []
        with self.queue_csv.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for idx, raw in enumerate(reader):
                source_path = str(raw.get("source_path", "")).strip()
                destination_path = str(raw.get("destination_path", "")).strip()
                image_path = source_path if source_path else destination_path
                row_id = hashlib.sha1(f"{idx}|{image_path}".encode("utf-8")).hexdigest()[:16]
                row: dict[str, Any] = {
                    "id": row_id,
                    "index": idx,
                    "image_path": image_path,
                    "source_path": source_path,
                    "source_dataset": str(raw.get("source_dataset", "")),
                    "predicted_route": str(raw.get("predicted_part", "")),
                    "predicted_label": str(raw.get("predicted_label", "")),
                    "confidence": self._as_float(raw.get("combined_confidence")),
                    "route_reason": str(raw.get("route_reason", "")),
                    "raw": raw,
                }
                rows.append(row)
        self.rows = rows
        self.row_index = {r["id"]: r for r in rows}

    def _load_decisions(self) -> None:
        self.decisions = {}
        if self.decisions_csv.exists():
            with self.decisions_csv.open("r", encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    row_id = str(row.get("row_id", "")).strip()
                    if row_id:
                        self.decisions[row_id] = dict(row)

    def _write_decisions(self) -> None:
        self.decisions_csv.parent.mkdir(parents=True, exist_ok=True)
        fields = [
            "row_id",
            "timestamp",
            "source_path",
            "final_label",
            "notes",
            "applied",
            "applied_at",
            "target_path",
        ]
        with self.decisions_csv.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            for row_id in sorted(self.decisions):
                row = self.decisions[row_id]
                out = {k: row.get(k, "") for k in fields}
                writer.writerow(out)
        payload = {"updated_at": now_iso(), "decisions": self.decisions}
        self.decisions_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    @staticmethod
    def _as_float(value: Any) -> float:
        try:
            return float(value)
        except Exception:
            return 0.0

    def list_rows(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for row in self.rows:
            d = self.decisions.get(row["id"], {})
            out.append(
                {
                    "id": row["id"],
                    "index": row["index"],
                    "source_path": row["source_path"],
                    "source_dataset": row["source_dataset"],
                    "predicted_route": row["predicted_route"],
                    "predicted_label": row["predicted_label"],
                    "confidence": row["confidence"],
                    "route_reason": row["route_reason"],
                    "final_label": d.get("final_label", ""),
                    "notes": d.get("notes", ""),
                    "applied": str(d.get("applied", "")).lower() == "true",
                }
            )
        return out

    def image_path_for(self, row_id: str) -> Path:
        row = self.row_index.get(row_id)
        if row is None:
            raise KeyError(row_id)
        p = Path(row["image_path"])
        if not p.exists() or not p.is_file():
            raise FileNotFoundError(str(p))
        return p

    def save_decision(self, *, row_id: str, final_label: str, notes: str) -> dict[str, Any]:
        if row_id not in self.row_index:
            raise KeyError(row_id)
        valid_labels = {item["label"] for item in LABEL_CHOICES}
        if final_label not in valid_labels:
            raise ValueError(f"Invalid final_label: {final_label}")
        row = self.row_index[row_id]
        existing = self.decisions.get(row_id, {})
        self.decisions[row_id] = {
            "row_id": row_id,
            "timestamp": existing.get("timestamp", now_iso()),
            "source_path": row["source_path"],
            "final_label": final_label,
            "notes": notes or "",
            "applied": existing.get("applied", "false"),
            "applied_at": existing.get("applied_at", ""),
            "target_path": existing.get("target_path", ""),
        }
        self._write_decisions()
        return self.decisions[row_id]

    def apply_moves(self, *, mode: str = "move") -> dict[str, Any]:
        if mode not in {"move", "copy"}:
            raise ValueError("mode must be 'move' or 'copy'")
        self.final_root.mkdir(parents=True, exist_ok=True)
        moved = 0
        skipped = 0
        errors: list[dict[str, str]] = []
        for row_id, dec in self.decisions.items():
            if str(dec.get("applied", "")).lower() == "true":
                continue
            src = Path(str(dec.get("source_path", "")))
            if not src.exists():
                errors.append({"row_id": row_id, "error": f"Source missing: {src}"})
                skipped += 1
                continue
            final_label = str(dec.get("final_label", "")).strip()
            if not final_label:
                skipped += 1
                continue
            target_dir = self.final_root / final_label
            target_dir.mkdir(parents=True, exist_ok=True)
            target_name = f"{sanitize_filename(src.stem)}__{hashlib.sha1(str(src).encode('utf-8')).hexdigest()[:10]}{src.suffix.lower()}"
            target = target_dir / target_name
            try:
                if target.exists():
                    skipped += 1
                else:
                    if mode == "copy":
                        shutil.copy2(src, target)
                    else:
                        shutil.move(str(src), str(target))
                    moved += 1
                dec["applied"] = "true"
                dec["applied_at"] = now_iso()
                dec["target_path"] = str(target)
            except Exception as exc:
                errors.append({"row_id": row_id, "error": str(exc)})
                skipped += 1
        self._write_decisions()
        return {"moved": moved, "skipped": skipped, "errors": errors, "mode": mode}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_app(store: ReviewStore) -> FastAPI:
    app = FastAPI(title="Disease Review Queue", version="1.0.0")

    @app.get("/")
    def index() -> FileResponse:
        if not UI_INDEX.exists():
            raise HTTPException(status_code=500, detail=f"UI file missing: {UI_INDEX}")
        return FileResponse(UI_INDEX)

    @app.get("/api/labels")
    def labels() -> dict[str, Any]:
        return {"labels": LABEL_CHOICES}

    @app.get("/api/queue")
    def queue() -> dict[str, Any]:
        rows = store.list_rows()
        labeled = sum(1 for r in rows if r.get("final_label"))
        return {"rows": rows, "total": len(rows), "labeled": labeled}

    @app.get("/api/image/{row_id}")
    def image(row_id: str) -> FileResponse:
        try:
            p = store.image_path_for(row_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="Row not found")
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Image file not found")
        return FileResponse(p)

    @app.post("/api/decision")
    def save_decision(req: SaveDecisionRequest) -> dict[str, Any]:
        try:
            row = store.save_decision(row_id=req.row_id, final_label=req.final_label, notes=req.notes)
            return {"ok": True, "decision": row}
        except KeyError:
            raise HTTPException(status_code=404, detail="Row not found")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.post("/api/apply")
    def apply_moves(req: ApplyMovesRequest) -> JSONResponse:
        try:
            result = store.apply_moves(mode=req.mode)
            return JSONResponse(content={"ok": True, "result": result})
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    return app


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Tiny local review web page for disease review queue.")
    parser.add_argument("--queue-csv", type=Path, default=BASE_DIR / "data" / "disease_training_data" / "reports" / "review_queue.csv")
    parser.add_argument("--decisions-csv", type=Path, default=BASE_DIR / "data" / "disease_training_data" / "reports" / "review_decisions.csv")
    parser.add_argument("--decisions-json", type=Path, default=BASE_DIR / "data" / "disease_training_data" / "reports" / "review_decisions.json")
    parser.add_argument("--final-root", type=Path, default=BASE_DIR / "data" / "disease_training_data" / "final_curated")
    parser.add_argument("--host", type=str, default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    store = ReviewStore(
        queue_csv=args.queue_csv.resolve(),
        decisions_csv=args.decisions_csv.resolve(),
        decisions_json=args.decisions_json.resolve(),
        final_root=args.final_root.resolve(),
    )
    app = build_app(store)
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()

