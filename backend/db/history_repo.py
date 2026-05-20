from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from threading import Lock
from typing import Any

from backend.core.config import settings

_DB_LOCK = Lock()


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _connect() -> sqlite3.Connection:
    settings.history_db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(settings.history_db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _DB_LOCK:
        with _connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS analyses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    variety TEXT NOT NULL,
                    health_status TEXT NOT NULL,
                    disease TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    health_score INTEGER NOT NULL,
                    risk_level TEXT NOT NULL,
                    harvest_window TEXT NOT NULL,
                    image_name TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS orchard_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    tree_id TEXT NOT NULL,
                    location TEXT,
                    disease_prediction TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    leaf_health_score INTEGER NOT NULL,
                    infection_percentage REAL NOT NULL,
                    confidence TEXT NOT NULL,
                    weather_risk TEXT,
                    image_record TEXT NOT NULL,
                    treatment_history TEXT,
                    farmer_feedback TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS climate_predictions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    user_location TEXT,
                    region TEXT,
                    latitude REAL,
                    longitude REAL,
                    cultivar TEXT NOT NULL,
                    weather_data TEXT NOT NULL,
                    maturity_stage TEXT NOT NULL,
                    prediction TEXT NOT NULL,
                    actual_harvest_date TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS orchards (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    location TEXT NOT NULL,
                    cultivar TEXT NOT NULL,
                    tree_density REAL NOT NULL,
                    planting_year INTEGER NOT NULL,
                    latitude REAL,
                    longitude REAL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS observations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    orchard_id INTEGER NOT NULL,
                    date TEXT NOT NULL,
                    image_path TEXT NOT NULL,
                    weather_data TEXT NOT NULL,
                    scene_type TEXT NOT NULL,
                    week_no INTEGER,
                    FOREIGN KEY (orchard_id) REFERENCES orchards(id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS analysis_results (
                    observation_id INTEGER PRIMARY KEY,
                    maturity_index REAL,
                    oil_estimate REAL,
                    fruit_count INTEGER,
                    disease_score REAL,
                    confidence REAL,
                    details TEXT NOT NULL,
                    FOREIGN KEY (observation_id) REFERENCES observations(id)
                )
                """
            )
            conn.commit()


def save_analysis(record: dict[str, Any]) -> None:
    created_at = _utcnow_iso()
    with _DB_LOCK:
        with _connect() as conn:
            conn.execute(
                """
                INSERT INTO analyses (
                    created_at, variety, health_status, disease, severity,
                    health_score, risk_level, harvest_window, image_name
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    created_at,
                    record["variety"],
                    record["health_status"],
                    record["disease"],
                    record["severity"],
                    int(record["health_score"]),
                    record["risk_level"],
                    record["harvest_window"],
                    record.get("image_name", "upload.jpg"),
                ),
            )
            conn.commit()


def list_history(limit: int = 100) -> list[dict[str, Any]]:
    with _DB_LOCK:
        with _connect() as conn:
            rows = conn.execute(
                """
                SELECT id, created_at, variety, health_status, disease, severity,
                       health_score, risk_level, harvest_window, image_name
                FROM analyses
                ORDER BY datetime(created_at) DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

    result: list[dict[str, Any]] = []
    for row in rows:
        result.append(
            {
                "id": row["id"],
                "created_at": datetime.fromisoformat(row["created_at"]),
                "variety": row["variety"],
                "health_status": row["health_status"],
                "disease": row["disease"],
                "severity": row["severity"],
                "health_score": row["health_score"],
                "risk_level": row["risk_level"],
                "harvest_window": row["harvest_window"],
                "image_name": row["image_name"],
            }
        )
    return result


def save_orchard_record(record: dict[str, Any]) -> None:
    tree_id = (record.get("tree_id") or "").strip()
    if not tree_id:
        return

    created_at = _utcnow_iso()
    with _DB_LOCK:
        with _connect() as conn:
            conn.execute(
                """
                INSERT INTO orchard_records (
                    created_at, tree_id, location, disease_prediction, severity,
                    leaf_health_score, infection_percentage, confidence, weather_risk,
                    image_record, treatment_history, farmer_feedback
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    created_at,
                    tree_id,
                    record.get("location"),
                    record.get("disease", "Unknown"),
                    record.get("leaf_severity", record.get("severity", "Unknown")),
                    int(record.get("leaf_health_score", record.get("health_score", 0))),
                    float(record.get("infection_percentage", 0.0)),
                    record.get("confidence", "0%"),
                    record.get("weather_risk"),
                    record.get("image_name", "upload.jpg"),
                    record.get("treatment_history"),
                    record.get("farmer_feedback"),
                ),
            )
            conn.commit()


def list_tree_history(tree_id: str, limit: int = 200) -> list[dict[str, Any]]:
    with _DB_LOCK:
        with _connect() as conn:
            rows = conn.execute(
                """
                SELECT id, created_at, tree_id, location, disease_prediction, severity,
                       leaf_health_score, infection_percentage, confidence, weather_risk,
                       image_record, treatment_history, farmer_feedback
                FROM orchard_records
                WHERE tree_id = ?
                ORDER BY datetime(created_at) DESC
                LIMIT ?
                """,
                (tree_id, limit),
            ).fetchall()

    result: list[dict[str, Any]] = []
    for row in rows:
        result.append(
            {
                "id": row["id"],
                "created_at": datetime.fromisoformat(row["created_at"]),
                "tree_id": row["tree_id"],
                "location": row["location"],
                "disease_prediction": row["disease_prediction"],
                "severity": row["severity"],
                "leaf_health_score": row["leaf_health_score"],
                "infection_percentage": row["infection_percentage"],
                "confidence": row["confidence"],
                "weather_risk": row["weather_risk"],
                "image_record": row["image_record"],
                "treatment_history": row["treatment_history"],
                "farmer_feedback": row["farmer_feedback"],
            }
        )
    return result


def update_tree_feedback(tree_id: str, treatment_history: str | None, farmer_feedback: str | None) -> None:
    with _DB_LOCK:
        with _connect() as conn:
            conn.execute(
                """
                UPDATE orchard_records
                SET treatment_history = COALESCE(?, treatment_history),
                    farmer_feedback = COALESCE(?, farmer_feedback)
                WHERE tree_id = ?
                """,
                (treatment_history, farmer_feedback, tree_id),
            )
            conn.commit()


def save_climate_prediction(record: dict[str, Any]) -> None:
    created_at = _utcnow_iso()
    with _DB_LOCK:
        with _connect() as conn:
            conn.execute(
                """
                INSERT INTO climate_predictions (
                    created_at, user_location, region, latitude, longitude, cultivar,
                    weather_data, maturity_stage, prediction, actual_harvest_date
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    created_at,
                    record.get("user_location"),
                    record.get("region"),
                    record.get("latitude"),
                    record.get("longitude"),
                    record.get("cultivar", "Chemlali"),
                    json.dumps(record.get("weather_data", {})),
                    record.get("maturity_stage", "Unknown"),
                    json.dumps(record.get("prediction", {})),
                    record.get("actual_harvest_date"),
                ),
            )
            conn.commit()


def list_climate_predictions(limit: int = 200) -> list[dict[str, Any]]:
    with _DB_LOCK:
        with _connect() as conn:
            rows = conn.execute(
                """
                SELECT id, created_at, user_location, region, latitude, longitude,
                       cultivar, weather_data, maturity_stage, prediction, actual_harvest_date
                FROM climate_predictions
                ORDER BY datetime(created_at) DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

    result: list[dict[str, Any]] = []
    for row in rows:
        result.append(
            {
                "id": row["id"],
                "created_at": datetime.fromisoformat(row["created_at"]),
                "user_location": row["user_location"],
                "region": row["region"],
                "latitude": row["latitude"],
                "longitude": row["longitude"],
                "cultivar": row["cultivar"],
                "weather_data": json.loads(row["weather_data"] or "{}"),
                "maturity_stage": row["maturity_stage"],
                "prediction": json.loads(row["prediction"] or "{}"),
                "actual_harvest_date": row["actual_harvest_date"],
            }
        )
    return result


def create_orchard(record: dict[str, Any]) -> dict[str, Any]:
    created_at = _utcnow_iso()
    with _DB_LOCK:
        with _connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO orchards (
                    created_at, user_id, location, cultivar, tree_density, planting_year, latitude, longitude
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    created_at,
                    str(record.get("user_id", "")),
                    str(record.get("location", "")),
                    str(record.get("cultivar", "Unknown")),
                    float(record.get("tree_density", 0.0)),
                    int(record.get("planting_year", 2000)),
                    record.get("latitude"),
                    record.get("longitude"),
                ),
            )
            orchard_id = int(cur.lastrowid)
            conn.commit()

    return {
        "id": orchard_id,
        "created_at": datetime.fromisoformat(created_at),
        "user_id": str(record.get("user_id", "")),
        "location": str(record.get("location", "")),
        "cultivar": str(record.get("cultivar", "Unknown")),
        "tree_density": float(record.get("tree_density", 0.0)),
        "planting_year": int(record.get("planting_year", 2000)),
        "latitude": record.get("latitude"),
        "longitude": record.get("longitude"),
    }


def get_orchard(orchard_id: int) -> dict[str, Any] | None:
    with _DB_LOCK:
        with _connect() as conn:
            row = conn.execute(
                """
                SELECT id, created_at, user_id, location, cultivar, tree_density, planting_year, latitude, longitude
                FROM orchards
                WHERE id = ?
                """,
                (orchard_id,),
            ).fetchone()
    if row is None:
        return None
    return {
        "id": row["id"],
        "created_at": datetime.fromisoformat(row["created_at"]),
        "user_id": row["user_id"],
        "location": row["location"],
        "cultivar": row["cultivar"],
        "tree_density": float(row["tree_density"]),
        "planting_year": int(row["planting_year"]),
        "latitude": row["latitude"],
        "longitude": row["longitude"],
    }


def create_observation(record: dict[str, Any]) -> int:
    created_at = _utcnow_iso()
    with _DB_LOCK:
        with _connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO observations (
                    created_at, orchard_id, date, image_path, weather_data, scene_type, week_no
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    created_at,
                    int(record["orchard_id"]),
                    str(record["date"]),
                    str(record["image_path"]),
                    json.dumps(record.get("weather_data", {})),
                    str(record.get("scene_type", "unknown")),
                    record.get("week_no"),
                ),
            )
            observation_id = int(cur.lastrowid)
            conn.commit()
    return observation_id


def save_observation_analysis(
    *,
    observation_id: int,
    maturity_index: float | None,
    oil_estimate: float | None,
    fruit_count: int | None,
    disease_score: float | None,
    confidence: float | None,
    details: dict[str, Any],
) -> None:
    with _DB_LOCK:
        with _connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO analysis_results (
                    observation_id, maturity_index, oil_estimate, fruit_count, disease_score, confidence, details
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(observation_id),
                    maturity_index,
                    oil_estimate,
                    fruit_count,
                    disease_score,
                    confidence,
                    json.dumps(details or {}),
                ),
            )
            conn.commit()


def list_orchard_observations(orchard_id: int, limit: int = 200) -> list[dict[str, Any]]:
    with _DB_LOCK:
        with _connect() as conn:
            rows = conn.execute(
                """
                SELECT o.id AS observation_id, o.date, o.image_path, o.weather_data, o.scene_type, o.week_no,
                       ar.maturity_index, ar.oil_estimate, ar.fruit_count, ar.disease_score, ar.confidence, ar.details
                FROM observations o
                LEFT JOIN analysis_results ar ON ar.observation_id = o.id
                WHERE o.orchard_id = ?
                ORDER BY datetime(o.date) DESC, o.id DESC
                LIMIT ?
                """,
                (orchard_id, limit),
            ).fetchall()
    result: list[dict[str, Any]] = []
    for row in rows:
        analysis_details = json.loads(row["details"] or "{}")
        result.append(
            {
                "observation_id": int(row["observation_id"]),
                "date": str(row["date"]),
                "image_path": str(row["image_path"]),
                "weather_data": json.loads(row["weather_data"] or "{}"),
                "scene_type": str(row["scene_type"]),
                "week_no": row["week_no"],
                "analysis": {
                    **analysis_details,
                    "maturity_index": row["maturity_index"],
                    "oil_estimate": row["oil_estimate"],
                    "fruit_count": row["fruit_count"],
                    "disease_score": row["disease_score"],
                    "confidence": row["confidence"],
                },
            }
        )
    return result


def list_orchard_series(orchard_id: int) -> list[dict[str, Any]]:
    with _DB_LOCK:
        with _connect() as conn:
            rows = conn.execute(
                """
                SELECT o.date, o.week_no, o.weather_data, ar.maturity_index, ar.oil_estimate, ar.fruit_count, ar.disease_score
                FROM observations o
                LEFT JOIN analysis_results ar ON ar.observation_id = o.id
                WHERE o.orchard_id = ?
                ORDER BY datetime(o.date) ASC, o.id ASC
                """,
                (orchard_id,),
            ).fetchall()
    result: list[dict[str, Any]] = []
    for row in rows:
        result.append(
            {
                "date": str(row["date"]),
                "week_no": row["week_no"],
                "weather_data": json.loads(row["weather_data"] or "{}"),
                "maturity_index": row["maturity_index"],
                "oil_estimate": row["oil_estimate"],
                "fruit_count": row["fruit_count"],
                "disease_score": row["disease_score"],
            }
        )
    return result
