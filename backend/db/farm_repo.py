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


def _row_to_tree_group(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": int(row["id"]),
        "farm_id": int(row["farm_id"]),
        "created_at": row["created_at"],
        "label": row["label"],
        "variety": row["variety"],
        "tree_count": int(row["tree_count"]),
        "age_mode": row["age_mode"],
        "age_exact": row["age_exact"],
        "age_min": row["age_min"],
        "age_max": row["age_max"],
        "status": row["status"],
        "notes": row["notes"],
    }


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    existing = {str(row["name"]) for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def init_farm_db() -> None:
    with _DB_LOCK:
        with _connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS farm_profiles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    owner_name TEXT NOT NULL,
                    farm_name TEXT NOT NULL,
                    country TEXT,
                    region TEXT,
                    primary_cultivar TEXT,
                    tree_age INTEGER,
                    irrigation_mode TEXT,
                    climate_notes TEXT,
                    notes TEXT,
                    latitude REAL NOT NULL,
                    longitude REAL NOT NULL,
                    total_trees INTEGER NOT NULL
                )
                """
            )
            _ensure_column(conn, "farm_profiles", "primary_cultivar", "TEXT")
            _ensure_column(conn, "farm_profiles", "tree_age", "INTEGER")
            _ensure_column(conn, "farm_profiles", "irrigation_mode", "TEXT")
            _ensure_column(conn, "farm_profiles", "notes", "TEXT")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tree_groups (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    farm_id INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    label TEXT NOT NULL,
                    variety TEXT NOT NULL,
                    tree_count INTEGER NOT NULL,
                    age_mode TEXT NOT NULL,
                    age_exact INTEGER,
                    age_min INTEGER,
                    age_max INTEGER,
                    status TEXT NOT NULL DEFAULT 'healthy',
                    notes TEXT,
                    FOREIGN KEY (farm_id) REFERENCES farm_profiles(id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS farm_scan_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    farm_id INTEGER NOT NULL,
                    tree_group_id INTEGER,
                    created_at TEXT NOT NULL,
                    module_type TEXT NOT NULL,
                    image_count INTEGER NOT NULL DEFAULT 1,
                    preliminary INTEGER NOT NULL DEFAULT 0,
                    confidence REAL,
                    status TEXT NOT NULL DEFAULT 'new',
                    summary TEXT NOT NULL,
                    next_action TEXT,
                    payload_json TEXT NOT NULL DEFAULT '{}',
                    FOREIGN KEY (farm_id) REFERENCES farm_profiles(id),
                    FOREIGN KEY (tree_group_id) REFERENCES tree_groups(id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS farm_alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    farm_id INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    level TEXT NOT NULL,
                    title TEXT NOT NULL,
                    message TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active',
                    source_scan_id INTEGER,
                    FOREIGN KEY (farm_id) REFERENCES farm_profiles(id),
                    FOREIGN KEY (source_scan_id) REFERENCES farm_scan_records(id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS farm_notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    farm_id INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    due_date TEXT,
                    text TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'open',
                    FOREIGN KEY (farm_id) REFERENCES farm_profiles(id)
                )
                """
            )
            conn.commit()


def list_farm_profiles() -> list[dict[str, Any]]:
    with _DB_LOCK:
        with _connect() as conn:
            rows = conn.execute(
                """
                SELECT id, created_at, updated_at, owner_name, farm_name, country, region,
                       primary_cultivar, tree_age, irrigation_mode, climate_notes, notes,
                       latitude, longitude, total_trees
                FROM farm_profiles
                ORDER BY datetime(updated_at) DESC
                """
            ).fetchall()
    return [dict(row) for row in rows]


def create_farm_profile(record: dict[str, Any]) -> dict[str, Any]:
    now = _utcnow_iso()
    with _DB_LOCK:
        with _connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO farm_profiles (
                    created_at, updated_at, owner_name, farm_name, country, region,
                    primary_cultivar, tree_age, irrigation_mode, climate_notes, notes,
                    latitude, longitude, total_trees
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    now,
                    now,
                    str(record.get("owner_name", "")).strip(),
                    str(record.get("farm_name", "")).strip(),
                    str(record.get("country", "")).strip(),
                    str(record.get("region", "")).strip(),
                    str(record.get("primary_cultivar", "")).strip(),
                    record.get("tree_age"),
                    str(record.get("irrigation_mode", "")).strip(),
                    str(record.get("climate_notes", "")).strip(),
                    str(record.get("notes", "")).strip(),
                    float(record.get("latitude", 0.0)),
                    float(record.get("longitude", 0.0)),
                    int(record.get("total_trees", 0)),
                ),
            )
            farm_id = int(cur.lastrowid)
            conn.commit()

    created = get_farm_profile(farm_id)
    if created is None:
        raise RuntimeError("Failed to create farm profile.")
    return created


def update_farm_profile(farm_id: int, updates: dict[str, Any]) -> dict[str, Any] | None:
    existing = get_farm_profile(farm_id)
    if existing is None:
        return None

    merged = {**existing, **updates}
    now = _utcnow_iso()
    with _DB_LOCK:
        with _connect() as conn:
            conn.execute(
                """
                UPDATE farm_profiles
                SET updated_at = ?, owner_name = ?, farm_name = ?, country = ?, region = ?,
                    primary_cultivar = ?, tree_age = ?, irrigation_mode = ?, climate_notes = ?,
                    notes = ?, latitude = ?, longitude = ?, total_trees = ?
                WHERE id = ?
                """,
                (
                    now,
                    str(merged.get("owner_name", "")).strip(),
                    str(merged.get("farm_name", "")).strip(),
                    str(merged.get("country", "")).strip(),
                    str(merged.get("region", "")).strip(),
                    str(merged.get("primary_cultivar", "")).strip(),
                    merged.get("tree_age"),
                    str(merged.get("irrigation_mode", "")).strip(),
                    str(merged.get("climate_notes", "")).strip(),
                    str(merged.get("notes", "")).strip(),
                    float(merged.get("latitude", 0.0)),
                    float(merged.get("longitude", 0.0)),
                    int(merged.get("total_trees", 0)),
                    int(farm_id),
                ),
            )
            conn.commit()

    return get_farm_profile(farm_id)


def get_farm_profile(farm_id: int) -> dict[str, Any] | None:
    with _DB_LOCK:
        with _connect() as conn:
            row = conn.execute(
                """
                SELECT id, created_at, updated_at, owner_name, farm_name, country, region,
                       primary_cultivar, tree_age, irrigation_mode, climate_notes, notes,
                       latitude, longitude, total_trees
                FROM farm_profiles
                WHERE id = ?
                """,
                (int(farm_id),),
            ).fetchone()
    if row is None:
        return None
    return dict(row)


def list_tree_groups(farm_id: int) -> list[dict[str, Any]]:
    with _DB_LOCK:
        with _connect() as conn:
            rows = conn.execute(
                """
                SELECT id, farm_id, created_at, label, variety, tree_count, age_mode, age_exact,
                       age_min, age_max, status, notes
                FROM tree_groups
                WHERE farm_id = ?
                ORDER BY id ASC
                """,
                (int(farm_id),),
            ).fetchall()
    return [_row_to_tree_group(row) for row in rows]


def create_tree_group(farm_id: int, record: dict[str, Any]) -> dict[str, Any]:
    now = _utcnow_iso()
    with _DB_LOCK:
        with _connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO tree_groups (
                    farm_id, created_at, label, variety, tree_count, age_mode,
                    age_exact, age_min, age_max, status, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(farm_id),
                    now,
                    str(record.get("label", "")).strip(),
                    str(record.get("variety", "Unknown")).strip(),
                    int(record.get("tree_count", 0)),
                    str(record.get("age_mode", "exact")).strip(),
                    record.get("age_exact"),
                    record.get("age_min"),
                    record.get("age_max"),
                    str(record.get("status", "healthy")).strip(),
                    str(record.get("notes", "")).strip(),
                ),
            )
            group_id = int(cur.lastrowid)
            conn.commit()

    group = get_tree_group(farm_id, group_id)
    if group is None:
        raise RuntimeError("Failed to create tree group.")
    return group


def get_tree_group(farm_id: int, group_id: int) -> dict[str, Any] | None:
    with _DB_LOCK:
        with _connect() as conn:
            row = conn.execute(
                """
                SELECT id, farm_id, created_at, label, variety, tree_count, age_mode, age_exact,
                       age_min, age_max, status, notes
                FROM tree_groups
                WHERE farm_id = ? AND id = ?
                """,
                (int(farm_id), int(group_id)),
            ).fetchone()
    if row is None:
        return None
    return _row_to_tree_group(row)


def update_tree_group(farm_id: int, group_id: int, updates: dict[str, Any]) -> dict[str, Any] | None:
    existing = get_tree_group(farm_id, group_id)
    if existing is None:
        return None

    merged = {**existing, **updates}
    with _DB_LOCK:
        with _connect() as conn:
            conn.execute(
                """
                UPDATE tree_groups
                SET label = ?, variety = ?, tree_count = ?, age_mode = ?, age_exact = ?,
                    age_min = ?, age_max = ?, status = ?, notes = ?
                WHERE farm_id = ? AND id = ?
                """,
                (
                    str(merged.get("label", "")).strip(),
                    str(merged.get("variety", "Unknown")).strip(),
                    int(merged.get("tree_count", 0)),
                    str(merged.get("age_mode", "exact")).strip(),
                    merged.get("age_exact"),
                    merged.get("age_min"),
                    merged.get("age_max"),
                    str(merged.get("status", "healthy")).strip(),
                    str(merged.get("notes", "")).strip(),
                    int(farm_id),
                    int(group_id),
                ),
            )
            conn.commit()
    return get_tree_group(farm_id, group_id)


def delete_tree_group(farm_id: int, group_id: int) -> bool:
    with _DB_LOCK:
        with _connect() as conn:
            cur = conn.execute(
                "DELETE FROM tree_groups WHERE farm_id = ? AND id = ?",
                (int(farm_id), int(group_id)),
            )
            conn.commit()
    return cur.rowcount > 0


def create_scan_record(farm_id: int, record: dict[str, Any]) -> dict[str, Any]:
    now = _utcnow_iso()
    with _DB_LOCK:
        with _connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO farm_scan_records (
                    farm_id, tree_group_id, created_at, module_type, image_count, preliminary,
                    confidence, status, summary, next_action, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(farm_id),
                    record.get("tree_group_id"),
                    now,
                    str(record.get("module_type", "unknown")).strip(),
                    int(record.get("image_count", 1)),
                    1 if bool(record.get("preliminary", False)) else 0,
                    record.get("confidence"),
                    str(record.get("status", "new")).strip(),
                    str(record.get("summary", "")).strip(),
                    str(record.get("next_action", "")).strip(),
                    json.dumps(record.get("payload_json", {})),
                ),
            )
            scan_id = int(cur.lastrowid)
            conn.commit()

    scan = get_scan_record(farm_id, scan_id)
    if scan is None:
        raise RuntimeError("Failed to create scan record.")
    _auto_alert_from_scan(scan)
    return scan


def list_scan_records(farm_id: int, limit: int = 200) -> list[dict[str, Any]]:
    with _DB_LOCK:
        with _connect() as conn:
            rows = conn.execute(
                """
                SELECT id, farm_id, tree_group_id, created_at, module_type, image_count, preliminary,
                       confidence, status, summary, next_action, payload_json
                FROM farm_scan_records
                WHERE farm_id = ?
                ORDER BY datetime(created_at) DESC
                LIMIT ?
                """,
                (int(farm_id), int(limit)),
            ).fetchall()

    result: list[dict[str, Any]] = []
    for row in rows:
        result.append(
            {
                "id": int(row["id"]),
                "farm_id": int(row["farm_id"]),
                "tree_group_id": row["tree_group_id"],
                "created_at": row["created_at"],
                "module_type": row["module_type"],
                "image_count": int(row["image_count"]),
                "preliminary": bool(row["preliminary"]),
                "confidence": row["confidence"],
                "status": row["status"],
                "summary": row["summary"],
                "next_action": row["next_action"],
                "payload_json": json.loads(row["payload_json"] or "{}"),
            }
        )
    return result


def get_scan_record(farm_id: int, scan_id: int) -> dict[str, Any] | None:
    rows = list_scan_records(farm_id=farm_id, limit=500)
    for row in rows:
        if int(row["id"]) == int(scan_id):
            return row
    return None


def update_scan_status(farm_id: int, scan_id: int, status: str) -> dict[str, Any] | None:
    with _DB_LOCK:
        with _connect() as conn:
            conn.execute(
                """
                UPDATE farm_scan_records
                SET status = ?
                WHERE farm_id = ? AND id = ?
                """,
                (str(status).strip(), int(farm_id), int(scan_id)),
            )
            conn.commit()
    return get_scan_record(farm_id=farm_id, scan_id=scan_id)


def create_alert(farm_id: int, level: str, title: str, message: str, source_scan_id: int | None = None) -> dict[str, Any]:
    now = _utcnow_iso()
    with _DB_LOCK:
        with _connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO farm_alerts (farm_id, created_at, level, title, message, status, source_scan_id)
                VALUES (?, ?, ?, ?, ?, 'active', ?)
                """,
                (int(farm_id), now, str(level).strip(), str(title).strip(), str(message).strip(), source_scan_id),
            )
            alert_id = int(cur.lastrowid)
            conn.commit()

    rows = list_alerts(farm_id=farm_id, status="all")
    for row in rows:
        if int(row["id"]) == alert_id:
            return row
    raise RuntimeError("Failed to create alert.")


def list_alerts(farm_id: int, status: str = "active") -> list[dict[str, Any]]:
    query = """
        SELECT id, farm_id, created_at, level, title, message, status, source_scan_id
        FROM farm_alerts
        WHERE farm_id = ?
    """
    params: list[Any] = [int(farm_id)]
    if status != "all":
        query += " AND status = ?"
        params.append(status)
    query += " ORDER BY datetime(created_at) DESC"

    with _DB_LOCK:
        with _connect() as conn:
            rows = conn.execute(query, tuple(params)).fetchall()
    return [dict(row) for row in rows]


def create_note(farm_id: int, text: str, due_date: str | None = None) -> dict[str, Any]:
    now = _utcnow_iso()
    with _DB_LOCK:
        with _connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO farm_notes (farm_id, created_at, due_date, text, status)
                VALUES (?, ?, ?, ?, 'open')
                """,
                (int(farm_id), now, due_date, text.strip()),
            )
            note_id = int(cur.lastrowid)
            conn.commit()
    notes = list_notes(farm_id=farm_id)
    for row in notes:
        if int(row["id"]) == note_id:
            return row
    raise RuntimeError("Failed to create note.")


def update_note_status(farm_id: int, note_id: int, status: str) -> dict[str, Any] | None:
    with _DB_LOCK:
        with _connect() as conn:
            conn.execute(
                """
                UPDATE farm_notes
                SET status = ?
                WHERE farm_id = ? AND id = ?
                """,
                (str(status).strip(), int(farm_id), int(note_id)),
            )
            conn.commit()
    notes = list_notes(farm_id=farm_id)
    for row in notes:
        if int(row["id"]) == int(note_id):
            return row
    return None


def list_notes(farm_id: int) -> list[dict[str, Any]]:
    with _DB_LOCK:
        with _connect() as conn:
            rows = conn.execute(
                """
                SELECT id, farm_id, created_at, due_date, text, status
                FROM farm_notes
                WHERE farm_id = ?
                ORDER BY datetime(created_at) DESC
                """,
                (int(farm_id),),
            ).fetchall()
    return [dict(row) for row in rows]


def farm_dashboard_summary(farm_id: int) -> dict[str, Any] | None:
    farm = get_farm_profile(farm_id)
    if farm is None:
        return None

    groups = list_tree_groups(farm_id)
    scans = list_scan_records(farm_id, limit=500)
    alerts = list_alerts(farm_id, status="active")
    notes = list_notes(farm_id)

    disease_alerts = sum(1 for a in alerts if str(a.get("title", "")).lower().startswith("disease"))
    pending_review = sum(1 for s in scans if str(s.get("status", "")).lower() == "pending_review")
    trees_scanned = len({s.get("tree_group_id") for s in scans if s.get("tree_group_id") is not None})

    readiness_values = []
    for scan in scans:
        payload = scan.get("payload_json", {})
        if not isinstance(payload, dict):
            continue
        readiness = payload.get("harvest_readiness_percent")
        if readiness is None:
            continue
        try:
            readiness_values.append(float(readiness))
        except Exception:
            continue
    harvest_readiness = round(sum(readiness_values) / len(readiness_values), 2) if readiness_values else None

    def _as_float(value: Any) -> float | None:
        try:
            if value is None:
                return None
            return float(value)
        except Exception:
            return None

    last_harvest_payload = _find_last_module_payload(scans, "harvest_time")
    last_harvest_estimate = None
    last_harvest_days_remaining = None
    last_harvest_window = None
    harvest_alert = None
    if isinstance(last_harvest_payload, dict):
        last_harvest_estimate = (
            last_harvest_payload.get("estimated_harvest_date")
            or last_harvest_payload.get("estimated_time_until_next_harvest_season")
            or last_harvest_payload.get("estimated_time_remaining")
        )
        last_harvest_days_remaining = (
            last_harvest_payload.get("days_remaining")
            or last_harvest_payload.get("estimated_time_until_next_harvest_season")
            or last_harvest_payload.get("estimated_time_remaining")
        )
        last_harvest_window = last_harvest_payload.get("recommended_harvest_window")
        status = str(
            last_harvest_payload.get("consistency")
            or last_harvest_payload.get("consistency_status")
            or last_harvest_payload.get("harvest_status")
            or last_harvest_payload.get("season_interpretation")
            or last_harvest_payload.get("season_status")
            or ""
        ).lower()
        if status in {
            "ready now",
            "near harvest",
            "late / urgent",
            "late / post-season",
            "not in active harvest window",
            "data inconsistency",
            "inconsistent",
            "data inconsistency detected",
            "data_inconsistency",
        }:
            harvest_alert = str(last_harvest_payload.get("next_action") or "Prepare harvest operations this week.")

    last_production_payload = _find_last_module_payload(scans, "production_model")
    production_forecast_kg = None
    production_range_low_kg = None
    production_range_high_kg = None
    production_confidence_label = None
    production_confidence_score = None
    production_trend = None
    production_vs_last_year_pct = None
    if isinstance(last_production_payload, dict):
        production_forecast_kg = _as_float(
            last_production_payload.get("projected_next_season_production_kg")
            or last_production_payload.get("projected_next_season_production")
            or last_production_payload.get("next_year_forecast")
        )
        range_kg = last_production_payload.get("estimated_production_range_kg")
        if isinstance(range_kg, dict):
            production_range_low_kg = _as_float(range_kg.get("low"))
            production_range_high_kg = _as_float(range_kg.get("high"))
        production_confidence_label = str(last_production_payload.get("confidence_label") or "") or None
        production_confidence_score = _as_float(
            last_production_payload.get("confidence_score")
            or last_production_payload.get("confidence")
        )
        comparisons = last_production_payload.get("comparisons")
        if isinstance(comparisons, dict):
            production_vs_last_year_pct = _as_float(
                comparisons.get("vsLastYearPct")
                or comparisons.get("vs_last_year_pct")
            )
        if production_vs_last_year_pct is None and production_forecast_kg is not None:
            inputs = last_production_payload.get("formula_inputs")
            if isinstance(inputs, dict):
                y1 = _as_float(inputs.get("Yt_1"))
                if y1 and y1 > 0:
                    production_vs_last_year_pct = ((production_forecast_kg - y1) / y1) * 100.0
        production_trend = str(last_production_payload.get("trend_indicator") or "").lower() or None
        if production_trend not in {"up", "down", "stable"}:
            if production_vs_last_year_pct is not None:
                if production_vs_last_year_pct > 5:
                    production_trend = "up"
                elif production_vs_last_year_pct < -5:
                    production_trend = "down"
                else:
                    production_trend = "stable"
            else:
                production_trend = None

    primary_cultivar = str(farm.get("primary_cultivar") or "").strip()
    varieties = {str(g.get("variety", "Unknown")).strip() or "Unknown" for g in groups}
    if primary_cultivar:
        varieties.add(primary_cultivar)

    return {
        "farm": farm,
        "tree_groups": groups,
        "recent_scans": scans[:20],
        "alerts": alerts[:20],
        "notes": notes[:20],
        "widgets": {
            "total_trees": int(farm.get("total_trees", 0)),
            "varieties": sorted(varieties),
            "primary_cultivar": primary_cultivar or None,
            "tree_age": farm.get("tree_age"),
            "irrigation_mode": farm.get("irrigation_mode"),
            "age_groups": len(groups),
            "trees_scanned": trees_scanned,
            "disease_alerts": disease_alerts,
            "harvest_readiness": harvest_readiness,
            "last_harvest_prediction": _find_last_module_summary(scans, "harvest_time"),
            "last_harvest_estimate": last_harvest_estimate,
            "last_harvest_days_remaining": last_harvest_days_remaining,
            "last_harvest_window": last_harvest_window,
            "harvest_alert": harvest_alert,
            "last_olive_count": _find_last_module_summary(scans, "olive_detect"),
            "last_production_prediction": _find_last_module_summary(scans, "production_model"),
            "production_forecast_kg": production_forecast_kg,
            "production_forecast_t": (production_forecast_kg / 1000.0) if production_forecast_kg is not None else None,
            "production_range_low_kg": production_range_low_kg,
            "production_range_high_kg": production_range_high_kg,
            "production_range_low_t": (production_range_low_kg / 1000.0) if production_range_low_kg is not None else None,
            "production_range_high_t": (production_range_high_kg / 1000.0) if production_range_high_kg is not None else None,
            "production_confidence_label": production_confidence_label,
            "production_confidence_score": production_confidence_score,
            "production_trend": production_trend,
            "production_vs_last_year_pct": production_vs_last_year_pct,
            "pending_review_cases": pending_review,
            "active_alerts": len(alerts),
        },
    }


def _find_last_module_summary(scans: list[dict[str, Any]], module_type: str) -> str | None:
    for scan in scans:
        if str(scan.get("module_type", "")).lower() == module_type:
            return str(scan.get("summary", ""))
    return None


def _find_last_module_payload(scans: list[dict[str, Any]], module_type: str) -> dict[str, Any] | None:
    for scan in scans:
        if str(scan.get("module_type", "")).lower() == module_type:
            payload = scan.get("payload_json", {})
            if isinstance(payload, dict):
                return payload
            return None
    return None


def _auto_alert_from_scan(scan: dict[str, Any]) -> None:
    farm_id = int(scan["farm_id"])
    status = str(scan.get("status", "")).lower()
    summary = str(scan.get("summary", "")).lower()
    module_type = str(scan.get("module_type", "")).lower()
    payload = scan.get("payload_json", {})
    if not isinstance(payload, dict):
        payload = {}

    confidence = scan.get("confidence")
    confidence_value = None
    try:
        if confidence is not None:
            confidence_value = float(confidence)
    except Exception:
        confidence_value = None

    if status == "pending_review":
        create_alert(
            farm_id=farm_id,
            level="medium",
            title="Review Needed",
            message="A recent AI scan has low confidence and needs agronomist review.",
            source_scan_id=int(scan["id"]),
        )
        return

    if module_type == "disease_scan":
        severity = str(payload.get("severity", "")).lower()
        disease = str(payload.get("disease", "")).lower()
        if "severe" in severity or "severe" in summary:
            create_alert(
                farm_id=farm_id,
                level="high",
                title="Disease Alert",
                message="Severe disease signal detected. Start treatment workflow now.",
                source_scan_id=int(scan["id"]),
            )
        elif disease and disease not in {"none", "healthy", "unknown"}:
            create_alert(
                farm_id=farm_id,
                level="medium",
                title="Disease Alert",
                message="Possible disease detected. Monitor and rescan in 7 days.",
                source_scan_id=int(scan["id"]),
            )

    if module_type == "harvest_time":
        harvest_status = str(
            payload.get("consistency")
            or payload.get("consistency_status")
            or payload.get("harvest_status")
            or payload.get("season_interpretation")
            or payload.get("season_status")
            or ""
        ).lower()
        if harvest_status in {
            "ready now",
            "near harvest",
            "late / urgent",
            "late / post-season",
            "not in active harvest window",
            "data inconsistency",
            "inconsistent",
            "data inconsistency detected",
            "data_inconsistency",
        }:
            create_alert(
                farm_id=farm_id,
                level="high" if harvest_status in {"late / urgent", "late / post-season", "data inconsistency detected", "data_inconsistency", "data inconsistency", "inconsistent"} else "medium",
                title="Harvest Action",
                message=str(payload.get("next_action") or "Harvest window is active. Prepare labor and equipment."),
                source_scan_id=int(scan["id"]),
            )
            return
        readiness = payload.get("harvest_readiness_percent")
        try:
            readiness_value = float(readiness) if readiness is not None else None
        except Exception:
            readiness_value = None
        if readiness_value is not None and readiness_value >= 85:
            create_alert(
                farm_id=farm_id,
                level="medium",
                title="Harvest Approaching",
                message="Harvest readiness is high. Begin preparation now.",
                source_scan_id=int(scan["id"]),
            )

    if confidence_value is not None and confidence_value < 0.65:
        create_alert(
            farm_id=farm_id,
            level="low",
            title="Low Confidence",
            message="Scan confidence is low. Capture clearer photos from multiple trees.",
            source_scan_id=int(scan["id"]),
        )
