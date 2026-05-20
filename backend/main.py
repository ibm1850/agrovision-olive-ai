from __future__ import annotations

import os
import tempfile
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path
from statistics import mean
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
import numpy as np

from backend.api.schemas import (
    AlertItem,
    ChatRequest,
    ChatResponse,
    ClimateHarvestRequest,
    ClimateHarvestResponse,
    CultivarMetadata,
    DiseaseScanExpertResponse,
    HarvestPredictImageResponse,
    HarvestPredictRequest,
    HarvestPredictResponse,
    HistoryItem,
    OliveDetectionResponse,
    OrchardFeedbackRequest,
    OrchardHistoryItem,
    OrchardCreateRequest,
    OrchardCreateResponse,
    OrchardObservationResponse,
    OrchardHistoryResponse,
    OrchardHarvestPredictionResponse,
    FarmAlertResponse,
    FarmDashboardResponse,
    FarmNoteCreateRequest,
    FarmNoteResponse,
    FarmNoteStatusUpdateRequest,
    FarmProfileCreateRequest,
    FarmProfileResponse,
    FarmProfileUpdateRequest,
    FarmScanCreateRequest,
    FarmScanResponse,
    FarmScanStatusUpdateRequest,
    TreeGroupCreateRequest,
    TreeGroupResponse,
    TreeGroupUpdateRequest,
    PredictTreeResponse,
    RegionItem,
    SceneClassificationResponse,
    UnifiedImageAnalysisResponse,
    VoiceResponse,
    WeatherInsightsResponse,
)
from backend.core.config import settings
from backend.db.history_repo import (
    create_observation,
    create_orchard,
    get_orchard,
    init_db,
    list_climate_predictions,
    list_history,
    list_orchard_observations,
    list_orchard_series,
    list_tree_history,
    save_analysis,
    save_climate_prediction,
    save_observation_analysis,
    save_orchard_record,
    update_tree_feedback,
)
from backend.db.farm_repo import (
    create_farm_profile,
    create_note,
    create_scan_record,
    create_tree_group,
    delete_tree_group,
    farm_dashboard_summary,
    get_farm_profile,
    init_farm_db,
    list_alerts as list_farm_alerts,
    list_farm_profiles,
    list_notes,
    list_scan_records,
    list_tree_groups,
    update_farm_profile,
    update_note_status,
    update_scan_status,
    update_tree_group,
)
from backend.services.alert_service import generate_alerts
from backend.services.chat_service import ChatService
from backend.services.climate_harvest_service import ClimateHarvestInput, ClimateHarvestService
from backend.services.climate_weather_service import OpenMeteoClimateService
from backend.services.cultivar_service import get_cultivar, list_cultivars, resolve_cultivar
from backend.services.disease_expert_service import DiseaseExpertService
from backend.services.harvest_image_service import HarvestImageService
from backend.services.harvest_fusion_service import HarvestFusionService
from backend.services.harvest_oil_service import HarvestOilService
from backend.services.harvest_time_service import HarvestTimeInput, HarvestTimeService
from backend.services.olive_detection_service import OliveDetectionService
from backend.services.quality_service import ImageQualityService
from backend.services.scene_classifier_service import SceneClassifierService
from backend.services.tunisia_geo_service import list_regions, nearest_region
from backend.services.translation_service import SUPPORTED_LANGS, translate_text
from backend.services.vision_service import UNCERTAIN_DIAGNOSIS, VisionService
from backend.services.voice_service import VoiceService
from backend.services.weather_service import WeatherRiskService

app = FastAPI(
    title="AgroVision Olive AI",
    description="Olive leaf diagnosis backend with CV, quality validation, weather risk, and history.",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

settings.cropped_olives_dir.mkdir(parents=True, exist_ok=True)
settings.observations_dir.mkdir(parents=True, exist_ok=True)
app.mount("/cropped-data", StaticFiles(directory=str(settings.cropped_olives_dir)), name="cropped_data")
app.mount("/observations-data", StaticFiles(directory=str(settings.observations_dir)), name="observations_data")

vision_service = VisionService()
chat_service = ChatService()
voice_service = VoiceService(model_name=settings.whisper_model)
quality_service = ImageQualityService()
weather_service = WeatherRiskService()
climate_weather_service = OpenMeteoClimateService()
climate_harvest_service = ClimateHarvestService()
harvest_oil_service = HarvestOilService()
harvest_image_service = HarvestImageService(harvest_oil_service=harvest_oil_service)
harvest_time_service = HarvestTimeService(
    harvest_image_service=harvest_image_service,
    weather_service=climate_weather_service,
)
olive_detection_service = OliveDetectionService()
scene_classifier_service = SceneClassifierService()
harvest_fusion_service = HarvestFusionService()
disease_expert_service = DiseaseExpertService(
    scene_classifier=scene_classifier_service,
    quality_service=quality_service,
    vision_service=vision_service,
)


@app.on_event("startup")
def startup_event() -> None:
    init_db()
    init_farm_db()


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    message = exc.detail if isinstance(exc.detail, str) else "Request could not be processed."
    return JSONResponse(
        status_code=exc.status_code,
        headers=exc.headers,
        content={
            "status": "error",
            "message": message,
            "detail": exc.detail,
            "data": {},
            "recommendation": "Verifiez les donnees envoyees puis reessayez.",
            "confidence": 0.0,
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # Keep API responses JSON-shaped so frontend parsing remains stable.
    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "message": f"Internal server error: {exc}",
            "detail": f"Internal server error: {exc}",
            "data": {},
            "recommendation": "Consultez les journaux du backend et relancez la requete.",
            "confidence": 0.0,
        },
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/regions", response_model=list[RegionItem])
def regions() -> list[RegionItem]:
    return [RegionItem(**row) for row in list_regions()]


@app.get("/cultivars", response_model=list[CultivarMetadata])
def cultivars() -> list[CultivarMetadata]:
    return [CultivarMetadata(**row) for row in list_cultivars()]


def _to_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))


def _map_tree_group(row: dict[str, Any]) -> TreeGroupResponse:
    payload = dict(row)
    payload["created_at"] = _to_datetime(payload["created_at"])
    return TreeGroupResponse(**payload)


def _map_farm_profile(row: dict[str, Any]) -> FarmProfileResponse:
    profile = dict(row)
    profile["created_at"] = _to_datetime(profile["created_at"])
    profile["updated_at"] = _to_datetime(profile["updated_at"])
    profile["tree_groups"] = [_map_tree_group(group) for group in list_tree_groups(profile["id"])]
    return FarmProfileResponse(**profile)


def _map_scan(row: dict[str, Any]) -> FarmScanResponse:
    payload = dict(row)
    payload["created_at"] = _to_datetime(payload["created_at"])
    return FarmScanResponse(**payload)


def _map_alert(row: dict[str, Any]) -> FarmAlertResponse:
    payload = dict(row)
    payload["created_at"] = _to_datetime(payload["created_at"])
    return FarmAlertResponse(**payload)


def _map_note(row: dict[str, Any]) -> FarmNoteResponse:
    payload = dict(row)
    payload["created_at"] = _to_datetime(payload["created_at"])
    return FarmNoteResponse(**payload)


@app.get("/farm/profile", response_model=list[FarmProfileResponse])
def farm_profiles() -> list[FarmProfileResponse]:
    rows = list_farm_profiles()
    return [_map_farm_profile(row) for row in rows]


@app.post("/farm/profile", response_model=FarmProfileResponse)
def farm_profile_create(payload: FarmProfileCreateRequest) -> FarmProfileResponse:
    created = create_farm_profile(payload.model_dump(exclude={"tree_groups"}))
    for group in payload.tree_groups:
        create_tree_group(created["id"], group.model_dump())
    updated = get_farm_profile(created["id"])
    if updated is None:
        raise HTTPException(status_code=500, detail="Farm profile was created but could not be reloaded.")
    return _map_farm_profile(updated)


@app.get("/farm/profile/{farm_id}", response_model=FarmProfileResponse)
def farm_profile_get(farm_id: int) -> FarmProfileResponse:
    row = get_farm_profile(farm_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Farm profile not found: {farm_id}")
    return _map_farm_profile(row)


@app.put("/farm/profile/{farm_id}", response_model=FarmProfileResponse)
def farm_profile_update(farm_id: int, payload: FarmProfileUpdateRequest) -> FarmProfileResponse:
    updated = update_farm_profile(farm_id, payload.model_dump(exclude_none=True))
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Farm profile not found: {farm_id}")
    return _map_farm_profile(updated)


@app.get("/farm/{farm_id}/tree-groups", response_model=list[TreeGroupResponse])
def farm_tree_groups(farm_id: int) -> list[TreeGroupResponse]:
    farm = get_farm_profile(farm_id)
    if farm is None:
        raise HTTPException(status_code=404, detail=f"Farm profile not found: {farm_id}")
    return [_map_tree_group(row) for row in list_tree_groups(farm_id)]


@app.post("/farm/{farm_id}/tree-groups", response_model=TreeGroupResponse)
def farm_tree_group_create(farm_id: int, payload: TreeGroupCreateRequest) -> TreeGroupResponse:
    farm = get_farm_profile(farm_id)
    if farm is None:
        raise HTTPException(status_code=404, detail=f"Farm profile not found: {farm_id}")
    row = create_tree_group(farm_id, payload.model_dump())
    return _map_tree_group(row)


@app.put("/farm/{farm_id}/tree-groups/{group_id}", response_model=TreeGroupResponse)
def farm_tree_group_update(
    farm_id: int,
    group_id: int,
    payload: TreeGroupUpdateRequest,
) -> TreeGroupResponse:
    row = update_tree_group(farm_id, group_id, payload.model_dump(exclude_none=True))
    if row is None:
        raise HTTPException(status_code=404, detail=f"Tree group not found: {group_id}")
    return _map_tree_group(row)


@app.delete("/farm/{farm_id}/tree-groups/{group_id}")
def farm_tree_group_delete(farm_id: int, group_id: int) -> dict[str, bool]:
    deleted = delete_tree_group(farm_id, group_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Tree group not found: {group_id}")
    return {"deleted": True}


@app.get("/farm/{farm_id}/scans", response_model=list[FarmScanResponse])
def farm_scans(farm_id: int, limit: int = 200) -> list[FarmScanResponse]:
    farm = get_farm_profile(farm_id)
    if farm is None:
        raise HTTPException(status_code=404, detail=f"Farm profile not found: {farm_id}")
    return [_map_scan(row) for row in list_scan_records(farm_id, limit=limit)]


@app.post("/farm/{farm_id}/scans", response_model=FarmScanResponse)
def farm_scan_create(farm_id: int, payload: FarmScanCreateRequest) -> FarmScanResponse:
    farm = get_farm_profile(farm_id)
    if farm is None:
        raise HTTPException(status_code=404, detail=f"Farm profile not found: {farm_id}")
    row = create_scan_record(farm_id, payload.model_dump())
    return _map_scan(row)


@app.put("/farm/{farm_id}/scans/{scan_id}/status", response_model=FarmScanResponse)
def farm_scan_update_status(
    farm_id: int,
    scan_id: int,
    payload: FarmScanStatusUpdateRequest,
) -> FarmScanResponse:
    row = update_scan_status(farm_id, scan_id, payload.status)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Scan not found: {scan_id}")
    return _map_scan(row)


@app.get("/farm/{farm_id}/alerts", response_model=list[FarmAlertResponse])
def farm_alerts(farm_id: int, include_resolved: bool = False) -> list[FarmAlertResponse]:
    farm = get_farm_profile(farm_id)
    if farm is None:
        raise HTTPException(status_code=404, detail=f"Farm profile not found: {farm_id}")
    status = "all" if include_resolved else "active"
    return [_map_alert(row) for row in list_farm_alerts(farm_id, status=status)]


@app.get("/farm/{farm_id}/notes", response_model=list[FarmNoteResponse])
def farm_notes(farm_id: int) -> list[FarmNoteResponse]:
    farm = get_farm_profile(farm_id)
    if farm is None:
        raise HTTPException(status_code=404, detail=f"Farm profile not found: {farm_id}")
    return [_map_note(row) for row in list_notes(farm_id)]


@app.post("/farm/{farm_id}/notes", response_model=FarmNoteResponse)
def farm_note_create(farm_id: int, payload: FarmNoteCreateRequest) -> FarmNoteResponse:
    farm = get_farm_profile(farm_id)
    if farm is None:
        raise HTTPException(status_code=404, detail=f"Farm profile not found: {farm_id}")
    row = create_note(farm_id=farm_id, text=payload.text, due_date=payload.due_date)
    return _map_note(row)


@app.put("/farm/{farm_id}/notes/{note_id}/status", response_model=FarmNoteResponse)
def farm_note_update(
    farm_id: int,
    note_id: int,
    payload: FarmNoteStatusUpdateRequest,
) -> FarmNoteResponse:
    row = update_note_status(farm_id=farm_id, note_id=note_id, status=payload.status)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Note not found: {note_id}")
    return _map_note(row)


@app.get("/farm/{farm_id}/dashboard", response_model=FarmDashboardResponse)
def farm_dashboard(farm_id: int) -> FarmDashboardResponse:
    summary = farm_dashboard_summary(farm_id)
    if summary is None:
        raise HTTPException(status_code=404, detail=f"Farm profile not found: {farm_id}")
    farm_payload = _map_farm_profile(summary["farm"])
    scans = [_map_scan(row) for row in summary.get("recent_scans", [])]
    alerts = [_map_alert(row) for row in summary.get("alerts", [])]
    notes = [_map_note(row) for row in summary.get("notes", [])]
    return FarmDashboardResponse(
        farm=farm_payload,
        widgets=summary.get("widgets", {}),
        recent_scans=scans,
        alerts=alerts,
        notes=notes,
    )


@app.get("/weather-insights", response_model=WeatherInsightsResponse)
def weather_insights(latitude: float, longitude: float) -> WeatherInsightsResponse:
    try:
        region = nearest_region(latitude, longitude)["region"]
        raw = climate_weather_service.fetch_daily_history(latitude=latitude, longitude=longitude, days=90)
        summary = climate_weather_service.summarize(raw)
        current = climate_weather_service.fetch_current_weather(latitude=latitude, longitude=longitude)
        payload = {
            "latitude": latitude,
            "longitude": longitude,
            "region": region,
            **summary,
            **current,
        }
        return WeatherInsightsResponse(**payload)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Weather service unavailable: {exc}",
        ) from exc


@app.post("/detect-olives", response_model=OliveDetectionResponse)
async def detect_olives(
    file: UploadFile = File(...),
    conf: float = Form(default=0.35),
    iou: float = Form(default=0.35),
    imgsz: int = Form(default=640),
    min_box_area: float = Form(default=150.0),
    max_box_area_ratio: float = Form(default=0.35),
    min_aspect_ratio: float = Form(default=0.4),
    max_aspect_ratio: float = Form(default=2.5),
) -> OliveDetectionResponse:
    if file.content_type and not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image uploads are supported.")

    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    try:
        result = olive_detection_service.detect_from_bytes(
            image_bytes=image_bytes,
            conf=conf,
            iou=iou,
            imgsz=imgsz,
            min_box_area=min_box_area,
            max_box_area_ratio=max_box_area_ratio,
            min_aspect_ratio=min_aspect_ratio,
            max_aspect_ratio=max_aspect_ratio,
        )
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return OliveDetectionResponse(**result)


@app.post("/scene-classify", response_model=SceneClassificationResponse)
async def scene_classify(file: UploadFile = File(...)) -> SceneClassificationResponse:
    if file.content_type and not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image uploads are supported.")
    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    try:
        result = scene_classifier_service.classify(image_bytes)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Scene classification failed: {exc}") from exc
    return SceneClassificationResponse(**result)


@app.post("/analyze-image", response_model=UnifiedImageAnalysisResponse)
async def analyze_image(
    file: UploadFile = File(...),
    language: str | None = Form(default="fr"),
    cultivar: str | None = Form(default="Unknown"),
    target_style: str | None = Form(default="premium_oil"),
    location: str | None = Form(default=None),
    sample_date: str | None = Form(default=None),
    week_no: int | None = Form(default=None),
) -> UnifiedImageAnalysisResponse:
    if file.content_type and not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image uploads are supported.")
    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    result = await _run_scene_routed_analysis(
        image_bytes=image_bytes,
        image_name=file.filename or "upload.jpg",
        language=language,
        cultivar=cultivar,
        target_style=target_style,
        location=location,
        sample_date=sample_date,
        week_no=week_no,
    )
    return UnifiedImageAnalysisResponse(**result)


def _severity_from_infection(infection_pct: float) -> tuple[str, str]:
    if infection_pct <= 5:
        return "Mild", "Healthy"
    if infection_pct <= 10:
        return "Mild", "Mild"
    if infection_pct <= 25:
        return "Moderate", "Moderate"
    if infection_pct <= 50:
        return "Severe", "Severe"
    return "Severe", "Severe"


def _translate_fields(payload: dict[str, Any], keys: list[str], language: str | None) -> None:
    lang = language if language in SUPPORTED_LANGS else "fr"
    if lang == "en":
        return
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            payload[key] = translate_text(value, from_lang="en", to_lang=lang)


def _confidence_cap(leaf_count: int, has_tree_image: bool) -> float:
    if has_tree_image:
        return 0.97
    if leaf_count >= 3:
        return 0.93
    if leaf_count == 2:
        return 0.90
    return 0.85


def _save_observation_image(image_bytes: bytes, file_name: str) -> str:
    safe_name = Path(file_name or "observation.jpg").name
    ext = Path(safe_name).suffix or ".jpg"
    stamped = f"{datetime.utcnow().strftime('%Y%m%d_%H%M%S_%f')}{ext}"
    out_path = settings.observations_dir / stamped
    out_path.write_bytes(image_bytes)
    return f"/observations-data/{stamped}"


def _resolve_cultivar_for_request(
    *,
    cultivar: str | None,
    location: str | None,
    ai_detected: str | None = None,
) -> dict[str, Any]:
    return resolve_cultivar(
        user_selected=cultivar,
        ai_detected=ai_detected,
        location=location,
    )


def _location_to_coords(location: str | None) -> tuple[float, float, str]:
    region_rows = list_regions()
    if not region_rows:
        return 34.7406, 10.7603, "Sfax"

    if location:
        text = str(location).strip().lower()
        for row in region_rows:
            name = str(row["name"])
            if text == name.lower() or text in name.lower() or name.lower() in text:
                return float(row["latitude"]), float(row["longitude"]), name

    row = region_rows[0]
    return float(row["latitude"]), float(row["longitude"]), str(row["name"])


def _historical_mi_from_climate_history(*, cultivar: str, location: str | None, fallback_mi: float) -> float:
    rows = list_climate_predictions(limit=250)
    if not rows:
        return float(fallback_mi)

    loc_key = str(location or "").strip().lower()
    cultivar_key = str(cultivar or "").strip().lower()
    collected: list[float] = []

    for row in rows:
        row_cultivar = str(row.get("cultivar", "")).strip().lower()
        if cultivar_key and row_cultivar != cultivar_key:
            continue

        row_loc = str(row.get("user_location") or row.get("region") or "").strip().lower()
        if loc_key and row_loc and loc_key not in row_loc and row_loc not in loc_key:
            continue

        prediction = row.get("prediction", {}) or {}
        for key in ["fused_maturity_index", "climate_maturity_index", "maturity_index_estimate"]:
            value = prediction.get(key)
            if value is None:
                continue
            try:
                collected.append(float(np.clip(float(value), 0.0, 7.0)))
                break
            except Exception:
                continue
        else:
            oil_val = prediction.get("estimated_oil_content") or prediction.get("predicted_oil_content")
            if oil_val is not None:
                try:
                    collected.append(float(np.clip((float(oil_val) - 10.0) / 2.0, 0.0, 7.0)))
                except Exception:
                    pass

    if not collected:
        return float(fallback_mi)
    return float(np.clip(float(np.mean(collected[-20:])), 0.0, 7.0))


def _mi_to_stage(mi: float) -> str:
    value = float(np.clip(mi, 0.0, 7.0))
    if value < 2.0:
        return "Early Ripening"
    if value <= 4.0:
        return "Optimal Harvest Stage"
    return "Late Harvest"


async def _run_scene_routed_analysis(
    *,
    image_bytes: bytes,
    image_name: str,
    language: str | None,
    cultivar: str | None,
    target_style: str | None,
    location: str | None,
    sample_date: str | None = None,
    week_no: int | None = None,
) -> dict[str, Any]:
    scene = scene_classifier_service.classify(image_bytes)
    scene_type = str(scene.get("scene_type", "unknown"))
    scene_conf = float(scene.get("confidence", 0.0))
    cultivar_info = _resolve_cultivar_for_request(
        cultivar=cultivar,
        location=location,
    )

    if scene_type == "leaf":
        quality = quality_service.validate_and_crop(image_bytes)
        if not quality.valid:
            raise HTTPException(status_code=400, detail=quality.message)
        cropped = quality.cropped_image_bytes if quality.cropped_image_bytes else image_bytes
        analysis = vision_service.analyze_image(image_bytes=cropped, image_name=image_name)
        _translate_fields(
            analysis,
            keys=[
                "leaf_health_status",
                "health_status",
                "disease",
                "leaf_severity",
                "severity",
                "notes",
            ],
            language=language,
        )
        route = "leaf_disease"
    elif scene_type == "orchard_branch":
        detect_result = olive_detection_service.detect_from_bytes(
            image_bytes=image_bytes,
            conf=0.35,
            iou=0.35,
            imgsz=960,
            min_box_area=150,
            max_box_area_ratio=0.35,
            min_aspect_ratio=0.4,
            max_aspect_ratio=2.5,
        )
        harvest_result = harvest_image_service.predict_from_image(
            image_bytes=image_bytes,
            image_name=image_name,
            sample_date=sample_date,
            week_no=week_no,
            cultivar=str(cultivar_info["cultivar"]),
            target_style=target_style or "premium_oil",
            scene_type="orchard_branch",
        )
        analysis = {
            "detection": detect_result,
            "harvest": harvest_result,
        }
        route = "branch_harvest"
    elif scene_type == "fruit_closeup":
        harvest_result = harvest_image_service.predict_from_image(
            image_bytes=image_bytes,
            image_name=image_name,
            sample_date=sample_date,
            week_no=week_no,
            cultivar=str(cultivar_info["cultivar"]),
            target_style=target_style or "premium_oil",
            scene_type="fruit_closeup",
        )
        analysis = {"harvest": harvest_result}
        route = "fruit_maturity"
    elif scene_type == "harvest_pile":
        harvest_result = harvest_image_service.predict_from_image(
            image_bytes=image_bytes,
            image_name=image_name,
            sample_date=sample_date,
            week_no=week_no,
            cultivar=str(cultivar_info["cultivar"]),
            target_style=target_style or "yield_oil",
            scene_type="harvest_pile",
        )
        harvest_result["notes"] = (
            "Harvest pile scene detected. Maturity estimation is provided, "
            "but single-fruit counting is intentionally skipped in this route. "
            + str(harvest_result.get("notes", ""))
        )
        analysis = {"harvest": harvest_result}
        route = "harvest_pile_maturity"
    else:
        analysis = {
            "message": "Unknown scene type. Upload a clearer leaf, branch, or fruit close-up image.",
        }
        route = "unknown"

    return {
        "scene_type": scene_type,
        "scene_confidence": round(float(np.clip(scene_conf, 0.0, 1.0)), 4),
        "route": route,
        "cultivar": str(cultivar_info["cultivar"]),
        "cultivar_source": str(cultivar_info["source"]),
        "analysis": analysis,
    }


def _predict_next_week_maturity(
    *,
    maturity_series: list[float],
    week_series: list[int],
    temperature_avg: float,
    rainfall_total: float,
    solar_radiation: float,
) -> float:
    clean = [(w, m) for w, m in zip(week_series, maturity_series) if w is not None and m is not None]
    if not clean:
        base = 2.0
    elif len(clean) == 1:
        base = float(clean[0][1]) + 0.25
    else:
        x = np.array([float(xi) for xi, _ in clean], dtype=np.float64)
        y = np.array([float(yi) for _, yi in clean], dtype=np.float64)
        if float(np.std(x)) < 1e-6:
            base = float(y[-1]) + 0.2
        else:
            slope, intercept = np.polyfit(x, y, 1)
            base = float((slope * (x[-1] + 1.0)) + intercept)

    climate_effect = 0.0
    if temperature_avg > 28:
        climate_effect += 0.22
    if solar_radiation > 18:
        climate_effect += 0.12
    if rainfall_total > 35:
        climate_effect -= 0.12
    return float(np.clip(base + climate_effect, 0.0, 7.0))


def _aggregate_prediction(
    leaf_results: list[dict[str, Any]],
    has_tree_image: bool,
    location: str | None,
    season: str | None,
    tree_age: int | None,
) -> dict[str, Any]:
    leaf_count = len(leaf_results)
    infection_avg = float(mean(item["infection_percentage"] for item in leaf_results))
    raw_conf = float(mean(item["disease_confidence"] for item in leaf_results))
    capped_conf = min(raw_conf, _confidence_cap(leaf_count=leaf_count, has_tree_image=has_tree_image))

    # Borderline quality lowers trust even when not rejected.
    quality_states = [item.get("_quality_state", "validated") for item in leaf_results]
    if "borderline" in quality_states:
        capped_conf = min(capped_conf, 0.69)

    predicted_diseases = [
        item["disease"]
        for item in leaf_results
        if item["disease"] not in {"None", UNCERTAIN_DIAGNOSIS}
    ]
    if predicted_diseases:
        dominant_disease = Counter(predicted_diseases).most_common(1)[0][0]
    else:
        dominant_disease = "None"

    leaf_severity, leaf_health_status = _severity_from_infection(infection_avg)
    leaf_health_score = int(max(0, min(100, round(100 - (infection_avg * 1.5)))))

    if capped_conf < 0.70:
        disease_output = UNCERTAIN_DIAGNOSIS
    else:
        disease_output = dominant_disease

    weather = weather_service.peacock_spot_risk(location)
    weather_risk = weather.get("risk", "unknown")

    notes = ["Diagnosis based on leaf-level analysis only."]
    if weather.get("status") == "ok":
        notes.append(
            f"Weather risk for peacock spot: {weather_risk} "
            f"(humidity={weather.get('humidity')}%, temp={weather.get('temperature_c')}C)."
        )
    elif location:
        notes.append(weather.get("note", "Weather risk unavailable."))
    if capped_conf < 0.70:
        notes.append(UNCERTAIN_DIAGNOSIS)
    if infection_avg > 50:
        notes.append("Critical leaf damage visible (>50% estimated infection).")
    if season:
        notes.append(f"Season context: {season}.")
    if tree_age is not None:
        notes.append(f"Tree age provided: {tree_age} years.")

    gradcam_image = leaf_results[0].get("gradcam_image", "")
    image_quality = "validated"
    if "borderline" in quality_states:
        image_quality = "borderline"

    confidence_text = f"{int(round(capped_conf * 100))}%"
    result = {
        "variety": "Unknown",
        "variety_confidence": 0.0,
        "health": "Leaf-level analysis only",
        "health_status": leaf_health_status,
        "leaf_health_status": leaf_health_status,
        "disease": disease_output,
        "disease_confidence": round(capped_conf, 4),
        "severity": leaf_severity,
        "leaf_severity": leaf_severity,
        "health_score": leaf_health_score,
        "leaf_health_score": leaf_health_score,
        "risk_level": "Leaf-level analysis only",
        "harvest_window": "Cannot be estimated from leaf disease image.",
        "confidence": confidence_text,
        "infection_percentage": round(infection_avg, 2),
        "leaf_count": leaf_count,
        "weather_risk": weather_risk,
        "image_quality": image_quality,
        "notes": " ".join(notes),
        "gradcam_image": gradcam_image,
    }
    return result


def _analyze_leaf_upload(
    *,
    image_bytes: bytes,
    image_name: str,
) -> tuple[dict[str, Any], Any]:
    quality = quality_service.validate_and_crop(image_bytes)
    if quality.valid:
        cropped = quality.cropped_image_bytes if quality.cropped_image_bytes else image_bytes
        result = vision_service.analyze_image(
            image_bytes=cropped,
            image_name=image_name,
        )
        result["_quality_state"] = (
            "borderline" if quality.blur_score < quality_service.blur_threshold * 1.35 else "validated"
        )
        return result, quality

    quality_message = str(quality.message or "").lower()
    soft_fail = ("resolution too low" in quality_message) or ("too blurry" in quality_message)
    if not soft_fail:
        raise HTTPException(status_code=400, detail=quality.message)

    # Graceful fallback for borderline images: run analysis, but cap confidence and flag for review.
    result = vision_service.analyze_image(
        image_bytes=image_bytes,
        image_name=image_name,
    )
    fallback_conf = min(float(result.get("disease_confidence", 0.0) or 0.0), 0.68)
    result["disease_confidence"] = round(float(np.clip(fallback_conf, 0.0, 1.0)), 4)
    result["confidence"] = f"{int(round(result['disease_confidence'] * 100))}%"
    result["notes"] = f"{quality.message} {str(result.get('notes', '')).strip()}".strip()
    result["image_quality"] = "borderline"
    result["_quality_state"] = "borderline"
    return result, quality


@app.post("/disease-scan-expert", response_model=DiseaseScanExpertResponse)
async def disease_scan_expert(
    file: UploadFile = File(...),
    language: str | None = Form(default="fr"),
) -> DiseaseScanExpertResponse:
    if file.content_type and not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image uploads are supported.")

    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    try:
        result = disease_expert_service.predict(
            image_bytes=image_bytes,
            image_name=file.filename or "upload.jpg",
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Disease scan failed: {exc}") from exc

    _translate_fields(
        result,
        keys=[
            "likely_disease",
            "affected_part",
            "confidence_label",
            "short_reason",
            "next_action",
            "status",
            "severity",
        ],
        language=language,
    )
    return DiseaseScanExpertResponse(**result)


@app.post("/predict-leaf-disease", response_model=PredictTreeResponse)
async def predict_leaf_disease(
    file: UploadFile = File(...),
    language: str | None = Form(default="fr"),
) -> PredictTreeResponse:
    if file.content_type and not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image uploads are supported.")

    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    result, _quality = _analyze_leaf_upload(
        image_bytes=image_bytes,
        image_name=file.filename or "upload.jpg",
    )
    _translate_fields(
        result,
        keys=[
            "leaf_health_status",
            "health_status",
            "disease",
            "leaf_severity",
            "severity",
            "notes",
            "harvest_window",
        ],
        language=language,
    )
    return PredictTreeResponse(**result)


@app.post("/predict-tree", response_model=PredictTreeResponse)
async def predict_tree(
    file: UploadFile | None = File(default=None),
    files: list[UploadFile] | None = File(default=None),
    tree_image: UploadFile | None = File(default=None),
    language: str | None = Form(default="fr"),
    tree_id: str | None = Form(default=None),
    location: str | None = Form(default=None),
    season: str | None = Form(default=None),
    tree_age: int | None = Form(default=None),
) -> PredictTreeResponse:
    leaf_uploads: list[UploadFile] = []
    if file is not None:
        leaf_uploads.append(file)
    if files:
        leaf_uploads.extend(files)
    if not leaf_uploads:
        raise HTTPException(status_code=400, detail="No leaf image provided.")

    leaf_results: list[dict[str, Any]] = []
    for upload in leaf_uploads:
        if upload.content_type and not upload.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="Only image uploads are supported.")

        image_bytes = await upload.read()
        if not image_bytes:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")

        result, quality = _analyze_leaf_upload(
            image_bytes=image_bytes,
            image_name=upload.filename or "upload.jpg",
        )
        leaf_results.append(result)

    has_tree_image = tree_image is not None
    if tree_image is not None:
        if tree_image.content_type and not tree_image.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="Tree image must be an image file.")
        tree_bytes = await tree_image.read()
        if not tree_bytes:
            raise HTTPException(status_code=400, detail="Tree image is empty.")
        # Validate quality, but tree image may not include a close leaf, so only check blur/resolution.
        tree_quality = quality_service.validate_and_crop(tree_bytes)
        if tree_quality.width < quality_service.min_resolution or tree_quality.height < quality_service.min_resolution:
            raise HTTPException(status_code=400, detail="Tree image resolution too low.")
        if tree_quality.blur_score < quality_service.blur_threshold:
            raise HTTPException(status_code=400, detail="Image too blurry. Upload a clearer leaf photo.")

    aggregated = _aggregate_prediction(
        leaf_results=leaf_results,
        has_tree_image=has_tree_image,
        location=location,
        season=season,
        tree_age=tree_age,
    )
    _translate_fields(
        aggregated,
        keys=[
            "leaf_health_status",
            "health_status",
            "disease",
            "leaf_severity",
            "severity",
            "notes",
            "harvest_window",
        ],
        language=language,
    )
    aggregated["image_name"] = leaf_results[0].get("image_name", "upload.jpg")

    save_analysis(aggregated)
    save_orchard_record(
        {
            **aggregated,
            "tree_id": tree_id,
            "location": location,
        }
    )
    return PredictTreeResponse(**aggregated)


@app.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest) -> ChatResponse:
    history_rows = list_history(limit=1)
    latest_analysis = history_rows[0] if history_rows else None
    response, detected_lang = chat_service.ask(
        payload.message,
        payload.language,
        latest_analysis=latest_analysis,
    )
    return ChatResponse(
        response=response,
        detected_language=detected_lang,
        model=settings.ollama_model,
    )


@app.post("/predict-harvest", response_model=HarvestPredictResponse)
def predict_harvest(payload: HarvestPredictRequest) -> HarvestPredictResponse:
    try:
        result = harvest_oil_service.predict(payload.measurements)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return HarvestPredictResponse(**result)


@app.post("/predict-harvest-image", response_model=HarvestPredictImageResponse)
async def predict_harvest_image(
    file: UploadFile = File(...),
    language: str | None = Form(default="fr"),
    sample_date: str | None = Form(default=None),
    cultivar: str | None = Form(default="Chemlali"),
    ai_cultivar: str | None = Form(default=None),
    location: str | None = Form(default=None),
    latitude: float | None = Form(default=None),
    longitude: float | None = Form(default=None),
    intended_use: str | None = Form(default=None),
    target_style: str | None = Form(default=None),
    tree_age: int | None = Form(default=None),
    irrigation_notes: str | None = Form(default=None),
    disease: str | None = Form(default=None),
    health_score: int | None = Form(default=None),
    debug: bool = Form(default=False),
) -> HarvestPredictImageResponse:
    if file.content_type and not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image uploads are supported.")

    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    try:
        scene = scene_classifier_service.classify(image_bytes)
        scene_type = str(scene.get("scene_type", "unknown"))
        user_cultivar = str(cultivar or "").strip()
        ai_cultivar_raw = str(ai_cultivar or "").strip()
        if user_cultivar.lower() == "unknown" and ai_cultivar_raw.lower() in {"", "unknown"}:
            cultivar_info = {"cultivar": "Unknown", "source": "user selected", "metadata": get_cultivar("Unknown")}
        else:
            cultivar_info = _resolve_cultivar_for_request(
                cultivar=cultivar,
                ai_detected=ai_cultivar,
                location=location,
            )

        if intended_use is None and target_style:
            style = str(target_style).strip().lower()
            intended_use = "table_olives" if style.startswith("table") else "oil"

        if latitude is not None and longitude is not None:
            lat, lon = float(latitude), float(longitude)
            resolved_location = str(nearest_region(lat, lon).get("region", location or "Unknown"))
        else:
            lat, lon, resolved_location = _location_to_coords(location)
        historical_mi = _historical_mi_from_climate_history(
            cultivar=str(cultivar_info["cultivar"]),
            location=location or resolved_location,
            fallback_mi=2.8,
        )

        result = harvest_time_service.predict(
            HarvestTimeInput(
                image_bytes=image_bytes,
                image_name=file.filename or "harvest_upload.jpg",
                sample_date=sample_date,
                location=location or resolved_location,
                latitude=lat,
                longitude=lon,
                cultivar=str(cultivar_info["cultivar"]),
                cultivar_source=str(cultivar_info["source"]),
                intended_use=str(intended_use or "oil"),
                tree_age=tree_age,
                irrigation_notes=irrigation_notes,
                scene_type=scene_type,
                historical_mi=historical_mi,
                debug=debug,
            )
        )

        result["scene_type"] = scene_type
        result["cultivar"] = str(cultivar_info["cultivar"])
        result["cultivar_source"] = str(cultivar_info["source"])

        weather_summary = result.get("weather_summary", {})
        save_climate_prediction(
            {
                "user_location": location or resolved_location,
                "region": resolved_location,
                "latitude": lat,
                "longitude": lon,
                "cultivar": str(cultivar_info["cultivar"]),
                "weather_data": weather_summary,
                "maturity_stage": result.get("maturity_stage", result.get("harvest_status", "Unknown")),
                "prediction": {
                    "current_maturity_stage": result.get("current_maturity_stage"),
                    "typical_harvest_season": result.get("typical_harvest_season"),
                    "season_status": result.get("season_status"),
                    "season_interpretation": result.get("season_interpretation"),
                    "consistency": result.get("consistency"),
                    "consistency_status": result.get("consistency_status"),
                    "possible_reasons": result.get("possible_reasons"),
                    "estimated_time_until_next_harvest_season": result.get("estimated_time_until_next_harvest_season"),
                    "estimated_time_remaining": result.get("estimated_time_remaining"),
                    "harvest_status": result.get("harvest_status"),
                    "estimated_harvest_date": result.get("estimated_harvest_date"),
                    "recommended_harvest_window": result.get("recommended_harvest_window"),
                    "days_remaining": result.get("days_remaining"),
                    "confidence": result.get("confidence"),
                    "fused_maturity_index": result.get("fused_maturity_index"),
                    "harvest_readiness_percent": result.get("harvest_readiness_percent"),
                    "short_reason": result.get("short_reason"),
                    "short_explanation": result.get("short_explanation"),
                },
                "actual_harvest_date": None,
            }
        )

        _translate_fields(
            result,
            keys=[
                "harvest_status",
                "confidence",
                "season_status",
                "season_interpretation",
                "consistency",
                "estimated_time_until_next_harvest_season",
                "estimated_time_remaining",
                "current_maturity_stage",
                "typical_harvest_season",
                "short_reason",
                "short_explanation",
                "next_action",
                "maturity_stage",
                "harvest_recommendation",
                "ioc_maturity_class",
                "tunisian_window",
                "reliability",
                "notes",
                "season_warning",
            ],
            language=language,
        )
        result.setdefault("model_name", "HarvestTimeService(OpenMeteo+MaturityFusion)-v1")
        result.setdefault("image_name", file.filename or "harvest_upload.jpg")
        result.setdefault("notes", "Single-photo harvest estimate generated.")
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Harvest image processing failed: {exc}") from exc

    return HarvestPredictImageResponse(**result)


@app.post("/predict-harvest-image-legacy", response_model=HarvestPredictImageResponse)
async def predict_harvest_image_legacy(
    file: UploadFile = File(...),
    language: str | None = Form(default="fr"),
    sample_date: str | None = Form(default=None),
    week_no: int | None = Form(default=None),
    cultivar: str | None = Form(default="Chemlali"),
    ai_cultivar: str | None = Form(default=None),
    location: str | None = Form(default=None),
    target_style: str | None = Form(default="premium_oil"),
    disease: str | None = Form(default=None),
    health_score: int | None = Form(default=None),
) -> HarvestPredictImageResponse:
    """Compatibility route that preserves previous image+climate fusion output."""
    if file.content_type and not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image uploads are supported.")

    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    try:
        scene = scene_classifier_service.classify(image_bytes)
        scene_type = str(scene.get("scene_type", "unknown"))
        cultivar_info = _resolve_cultivar_for_request(
            cultivar=cultivar,
            ai_detected=ai_cultivar,
            location=location,
        )
        image_result = harvest_image_service.predict_from_image(
            image_bytes=image_bytes,
            image_name=file.filename or "harvest_upload.jpg",
            sample_date=sample_date,
            week_no=week_no,
            cultivar=str(cultivar_info["cultivar"]),
            target_style=target_style,
            disease=disease,
            health_score=health_score,
            scene_type=scene_type,
        )

        image_mi = float(
            image_result.get("image_maturity_index")
            or image_result.get("maturity_index_estimate")
            or 0.0
        )
        image_oil = float(image_result.get("estimated_oil_content", 0.0))
        climate_stage = _mi_to_stage(image_mi)

        lat, lon, resolved_location = _location_to_coords(location)
        weather_summary = {
            "temperature_avg": 23.0,
            "rainfall_total": 10.0,
            "humidity_avg": 62.0,
            "solar_radiation": 18.0,
        }
        try:
            weather_raw = climate_weather_service.fetch_daily_history(latitude=lat, longitude=lon, days=90)
            weather_summary = climate_weather_service.summarize(weather_raw)
        except Exception:
            pass

        climate_result = climate_harvest_service.predict(
            ClimateHarvestInput(
                cultivar=str(cultivar_info["cultivar"]),
                location=location or resolved_location,
                maturity_stage=climate_stage,
                temperature_avg=float(weather_summary["temperature_avg"]),
                rainfall_total=float(weather_summary["rainfall_total"]),
                humidity_avg=float(weather_summary["humidity_avg"]),
                solar_radiation=float(weather_summary["solar_radiation"]),
                disease=disease or "None",
                health_score=health_score if health_score is not None else 85,
            )
        )

        climate_mi = float(climate_result.get("climate_maturity_index", image_mi))
        climate_oil = float(climate_result.get("estimated_oil_content", image_oil))

        historical_mi = _historical_mi_from_climate_history(
            cultivar=str(cultivar_info["cultivar"]),
            location=location or resolved_location,
            fallback_mi=image_mi,
        )

        cultivar_meta = get_cultivar(str(cultivar_info["cultivar"]))
        fusion = harvest_fusion_service.fuse(
            image_mi=image_mi,
            image_oil_estimate=image_oil,
            climate_mi=climate_mi,
            climate_oil_estimate=climate_oil,
            historical_mi=historical_mi,
            cultivar=str(cultivar_info["cultivar"]),
            target_style=str(target_style or "premium_oil"),
            cultivar_harvest_start=str(cultivar_meta.get("typical_harvest_start") or ""),
            cultivar_harvest_end=str(cultivar_meta.get("typical_harvest_end") or ""),
            predicted_harvest_window=str(climate_result.get("harvest_window") or ""),
            disease=disease,
            health_score=health_score,
            scene_type=scene_type,
        )

        final_decision = fusion["final_ai_decision"]
        final_oil = float(fusion["fused_oil_estimate"])
        final_fcfw = float((float(image_result.get("estimated_fcfw", image_oil)) + float(climate_result.get("estimated_fcfw", climate_oil))) / 2.0)
        final_fcdm = float((float(image_result.get("estimated_fcdm", image_oil * 2.4)) + float(climate_result.get("estimated_fcdm", climate_oil * 2.4))) / 2.0)

        result = dict(image_result)
        result["estimated_oil_content"] = round(final_oil, 3)
        result["estimated_fcdm"] = round(final_fcdm, 3)
        result["estimated_fcfw"] = round(final_fcfw, 3)
        result["maturity_stage"] = str(final_decision.get("maturity_stage", result.get("maturity_stage", "Unknown")))
        result["harvest_recommendation"] = str(final_decision.get("harvest_recommendation", result.get("harvest_recommendation", "")))
        result["maturity_index_estimate"] = float(fusion["fused_maturity_index"])
        result["ioc_maturity_class"] = str(final_decision.get("ioc_maturity_class", result.get("ioc_maturity_class", "")))
        result["tunisian_window"] = str(final_decision.get("tunisian_window", result.get("tunisian_window", "")))
        result["reliability"] = str(final_decision.get("reliability", result.get("reliability", "medium")))
        result["scene_type"] = scene_type
        result["image_analysis"] = fusion["image_analysis"]
        result["climate_analysis"] = fusion["climate_analysis"]
        result["final_ai_decision"] = final_decision
        result["fused_maturity_index"] = float(fusion["fused_maturity_index"])
        result["historical_maturity_index"] = float(fusion["historical_maturity_index"])
        result["harvest_readiness_percent"] = float(fusion["harvest_readiness_percent"])
        result["season_warning"] = fusion.get("season_warning")
        result["cultivar"] = str(cultivar_info["cultivar"])
        result["cultivar_source"] = str(cultivar_info["source"])
        fusion_notes = str(fusion.get("notes", "")).strip()
        base_notes = str(result.get("notes", "")).strip()
        season_warning = str(fusion.get("season_warning", "") or "").strip()
        result["notes"] = " ".join([part for part in [base_notes, fusion_notes, season_warning] if part]).strip()

        save_climate_prediction(
            {
                "user_location": location or resolved_location,
                "region": resolved_location,
                "latitude": lat,
                "longitude": lon,
                "cultivar": str(cultivar_info["cultivar"]),
                "weather_data": weather_summary,
                "maturity_stage": climate_stage,
                "prediction": {
                    **climate_result,
                    "fused_maturity_index": result["fused_maturity_index"],
                    "harvest_readiness_percent": result["harvest_readiness_percent"],
                },
                "actual_harvest_date": None,
            }
        )

        _translate_fields(
            result,
            keys=[
                "maturity_stage",
                "harvest_recommendation",
                "ioc_maturity_class",
                "tunisian_window",
                "reliability",
                "notes",
                "season_warning",
            ],
            language=language,
        )
        result.setdefault("model_name", "HarvestImageService+ClimateFusion-v1")
        result.setdefault("image_name", file.filename or "harvest_upload.jpg")
        result.setdefault("notes", "Legacy harvest estimate generated.")
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Harvest image processing failed: {exc}") from exc

    return HarvestPredictImageResponse(**result)


@app.post("/predict-harvest-climate", response_model=ClimateHarvestResponse)
def predict_harvest_climate(payload: ClimateHarvestRequest) -> ClimateHarvestResponse:
    try:
        weather_raw = climate_weather_service.fetch_daily_history(
            latitude=payload.latitude,
            longitude=payload.longitude,
            days=90,
        )
        weather_summary = climate_weather_service.summarize(weather_raw)
        region_meta = nearest_region(payload.latitude, payload.longitude)
        location_name = payload.location or str(region_meta["region"])
        cultivar_info = _resolve_cultivar_for_request(
            cultivar=payload.cultivar,
            location=location_name,
        )

        prediction = climate_harvest_service.predict(
            ClimateHarvestInput(
                cultivar=str(cultivar_info["cultivar"]),
                location=location_name,
                maturity_stage=payload.maturity_stage,
                temperature_avg=float(weather_summary["temperature_avg"]),
                rainfall_total=float(weather_summary["rainfall_total"]),
                humidity_avg=float(weather_summary["humidity_avg"]),
                solar_radiation=float(weather_summary["solar_radiation"]),
                disease=payload.disease or "None",
                health_score=payload.health_score if payload.health_score is not None else 85,
            )
        )

        save_climate_prediction(
            {
                "user_location": location_name,
                "region": region_meta["region"],
                "latitude": payload.latitude,
                "longitude": payload.longitude,
                "cultivar": str(cultivar_info["cultivar"]),
                "weather_data": weather_summary,
                "maturity_stage": payload.maturity_stage,
                "prediction": prediction,
                "actual_harvest_date": payload.actual_harvest_date,
            }
        )
        prediction["cultivar_source"] = str(cultivar_info["source"])
        return ClimateHarvestResponse(**prediction)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Climate harvest service unavailable: {exc}") from exc


@app.get("/climate-history")
def climate_history(limit: int = 200) -> list[dict[str, Any]]:
    return list_climate_predictions(limit=limit)


@app.post("/orchard/create", response_model=OrchardCreateResponse)
def orchard_create(payload: OrchardCreateRequest) -> OrchardCreateResponse:
    cultivar_info = _resolve_cultivar_for_request(
        cultivar=payload.cultivar,
        location=payload.location,
    )
    row = create_orchard(
        {
            "user_id": payload.user_id,
            "location": payload.location,
            "cultivar": cultivar_info["cultivar"],
            "tree_density": payload.tree_density,
            "planting_year": payload.planting_year,
            "latitude": payload.latitude,
            "longitude": payload.longitude,
        }
    )
    return OrchardCreateResponse(**row)


@app.post("/orchard/{orchard_id}/observation", response_model=OrchardObservationResponse)
async def orchard_observation_create(
    orchard_id: int,
    file: UploadFile = File(...),
    date_str: str | None = Form(default=None),
    language: str | None = Form(default="fr"),
    cultivar: str | None = Form(default=None),
    target_style: str | None = Form(default="premium_oil"),
) -> OrchardObservationResponse:
    orchard = get_orchard(orchard_id)
    if orchard is None:
        raise HTTPException(status_code=404, detail=f"Orchard not found: {orchard_id}")

    if file.content_type and not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image uploads are supported.")
    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    obs_date = date_str or date.today().isoformat()
    try:
        week_no = int(datetime.fromisoformat(obs_date).isocalendar().week)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")

    location_name = str(orchard.get("location") or "")
    cultivar_choice = str(cultivar or orchard.get("cultivar") or "Unknown")

    routed = await _run_scene_routed_analysis(
        image_bytes=image_bytes,
        image_name=file.filename or "observation.jpg",
        language=language,
        cultivar=cultivar_choice,
        target_style=target_style,
        location=location_name,
        sample_date=obs_date,
        week_no=week_no,
    )

    weather_data: dict[str, Any] = {}
    lat = orchard.get("latitude")
    lon = orchard.get("longitude")
    if lat is not None and lon is not None:
        try:
            raw = climate_weather_service.fetch_daily_history(latitude=float(lat), longitude=float(lon), days=30)
            weather_data = climate_weather_service.summarize(raw)
        except Exception:
            weather_data = {}

    image_path = _save_observation_image(image_bytes, file.filename or "observation.jpg")
    observation_id = create_observation(
        {
            "orchard_id": orchard_id,
            "date": obs_date,
            "image_path": image_path,
            "weather_data": weather_data,
            "scene_type": routed["scene_type"],
            "week_no": week_no,
        }
    )

    analysis_payload = routed.get("analysis", {})
    maturity_index = None
    oil_estimate = None
    fruit_count = None
    disease_score = None
    confidence = float(routed.get("scene_confidence", 0.0))

    if isinstance(analysis_payload, dict):
        if "harvest" in analysis_payload and isinstance(analysis_payload["harvest"], dict):
            hv = analysis_payload["harvest"]
            maturity_index = float(hv.get("maturity_index_estimate", 0.0))
            oil_estimate = float(hv.get("estimated_oil_content", 0.0))
            if hv.get("detected_olives") is not None:
                fruit_count = int(hv.get("detected_olives", 0))
        if "detection" in analysis_payload and isinstance(analysis_payload["detection"], dict):
            det = analysis_payload["detection"]
            fruit_count = int(det.get("detected_olives", fruit_count or 0))
            confidence = max(confidence, float(det.get("avg_confidence", 0.0)))
        if analysis_payload.get("infection_percentage") is not None:
            disease_score = float(analysis_payload.get("infection_percentage", 0.0))
        elif analysis_payload.get("leaf_health_score") is not None:
            disease_score = float(100.0 - float(analysis_payload.get("leaf_health_score", 100.0)))

    save_observation_analysis(
        observation_id=observation_id,
        maturity_index=maturity_index,
        oil_estimate=oil_estimate,
        fruit_count=fruit_count,
        disease_score=disease_score,
        confidence=confidence,
        details=routed,
    )

    return OrchardObservationResponse(
        observation_id=observation_id,
        orchard_id=orchard_id,
        date=obs_date,
        scene_type=str(routed["scene_type"]),
        scene_confidence=float(routed["scene_confidence"]),
        analysis=routed,
    )


@app.get("/orchard/{orchard_id}/history", response_model=OrchardHistoryResponse)
def orchard_history_v2(orchard_id: int, limit: int = 200) -> OrchardHistoryResponse:
    orchard = get_orchard(orchard_id)
    if orchard is None:
        raise HTTPException(status_code=404, detail=f"Orchard not found: {orchard_id}")
    observations = list_orchard_observations(orchard_id, limit=limit)
    return OrchardHistoryResponse(
        orchard=OrchardCreateResponse(**orchard),
        observations=observations,
    )


@app.get("/orchard/{orchard_id}/harvest_prediction", response_model=OrchardHarvestPredictionResponse)
def orchard_harvest_prediction(orchard_id: int) -> OrchardHarvestPredictionResponse:
    orchard = get_orchard(orchard_id)
    if orchard is None:
        raise HTTPException(status_code=404, detail=f"Orchard not found: {orchard_id}")

    series = list_orchard_series(orchard_id)
    if not series:
        raise HTTPException(status_code=400, detail="No observations available for this orchard.")

    maturity_series = [float(row["maturity_index"]) for row in series if row.get("maturity_index") is not None]
    week_series = [int(row["week_no"]) for row in series if row.get("week_no") is not None and row.get("maturity_index") is not None]
    current_maturity = maturity_series[-1] if maturity_series else 2.0

    lat = orchard.get("latitude")
    lon = orchard.get("longitude")
    weather_summary = {
        "temperature_avg": 23.0,
        "rainfall_total": 10.0,
        "humidity_avg": 62.0,
        "solar_radiation": 18.0,
    }
    if lat is not None and lon is not None:
        try:
            raw = climate_weather_service.fetch_daily_history(latitude=float(lat), longitude=float(lon), days=30)
            weather_summary = climate_weather_service.summarize(raw)
        except Exception:
            pass

    predicted_next = _predict_next_week_maturity(
        maturity_series=maturity_series or [current_maturity],
        week_series=week_series or [int(date.today().isocalendar().week)],
        temperature_avg=float(weather_summary["temperature_avg"]),
        rainfall_total=float(weather_summary["rainfall_total"]),
        solar_radiation=float(weather_summary["solar_radiation"]),
    )

    if predicted_next < 2.0:
        stage_text = "Early Ripening"
    elif predicted_next < 3.2:
        stage_text = "Optimal Harvest Stage"
    elif predicted_next < 4.8:
        stage_text = "Late Harvest"
    else:
        stage_text = "Late Harvest"

    climate_pred = climate_harvest_service.predict(
        ClimateHarvestInput(
            cultivar=str(orchard.get("cultivar", "Unknown")),
            location=str(orchard.get("location", "Unknown")),
            maturity_stage=stage_text,
            temperature_avg=float(weather_summary["temperature_avg"]),
            rainfall_total=float(weather_summary["rainfall_total"]),
            humidity_avg=float(weather_summary["humidity_avg"]),
            solar_radiation=float(weather_summary["solar_radiation"]),
            disease="None",
            health_score=85,
        )
    )

    readiness = float(np.clip((predicted_next / 4.0) * 100.0, 0.0, 100.0))
    if predicted_next > 4.5:
        readiness = float(max(55.0, 100.0 - (predicted_next - 4.5) * 25.0))

    avg_disease = 0.0
    disease_vals = [float(row["disease_score"]) for row in series if row.get("disease_score") is not None]
    if disease_vals:
        avg_disease = float(np.mean(disease_vals))

    if avg_disease > 30 or float(weather_summary["humidity_avg"]) > 78:
        quality_risk = "high"
    elif avg_disease > 15 or float(weather_summary["humidity_avg"]) > 68:
        quality_risk = "medium"
    else:
        quality_risk = "low"

    notes = [
        "Harvest recommendation combines maturity trend, climate summary, and cultivar constraints.",
        f"Current maturity index: {current_maturity:.2f}; next-week estimate: {predicted_next:.2f}.",
    ]

    return OrchardHarvestPredictionResponse(
        orchard_id=orchard_id,
        cultivar=str(orchard.get("cultivar", "Unknown")),
        current_maturity_index=round(float(current_maturity), 3),
        predicted_maturity_next_week=round(float(predicted_next), 3),
        harvest_readiness_percentage=round(readiness, 2),
        optimal_harvest_week=f"Week {int((date.today() + timedelta(days=7)).isocalendar().week)}",
        estimated_harvest_window=str(climate_pred.get("harvest_window", "unknown")),
        estimated_oil_content=float(climate_pred.get("estimated_oil_content", 0.0)),
        oil_quality_risk=quality_risk,
        notes=notes,
    )


@app.get("/alerts", response_model=list[AlertItem])
def alerts(latitude: float | None = None, longitude: float | None = None) -> list[AlertItem]:
    try:
        latest = list_history(limit=1)
        latest_analysis = latest[0] if latest else None

        weather = None
        climate_prediction = None
        if latitude is not None and longitude is not None:
            raw = climate_weather_service.fetch_daily_history(latitude=latitude, longitude=longitude, days=90)
            weather = climate_weather_service.summarize(raw)
            sample_pred = climate_harvest_service.predict(
                ClimateHarvestInput(
                    cultivar="Chemlali",
                    location=str(nearest_region(latitude, longitude)["region"]),
                    maturity_stage="Optimal Harvest Stage",
                    temperature_avg=float(weather["temperature_avg"]),
                    rainfall_total=float(weather["rainfall_total"]),
                    humidity_avg=float(weather["humidity_avg"]),
                    solar_radiation=float(weather["solar_radiation"]),
                    disease=str(latest_analysis.get("disease", "None")) if latest_analysis else "None",
                    health_score=int(latest_analysis.get("health_score", 85)) if latest_analysis else 85,
                )
            )
            climate_prediction = sample_pred

        return [AlertItem(**row) for row in generate_alerts(latest_analysis=latest_analysis, weather=weather, climate_prediction=climate_prediction)]
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Alert service unavailable: {exc}") from exc


@app.get("/ai-extensions")
def ai_extensions() -> dict[str, list[str]]:
    return {
        "supported_next_modules": [
            "Satellite NDVI monitoring",
            "Yield prediction",
            "Olive fruit fly detection",
            "Automatic cultivar recognition",
        ]
    }


@app.post("/voice", response_model=VoiceResponse)
async def voice(
    file: UploadFile = File(...),
    language: str | None = Form(default=None),
) -> VoiceResponse:
    suffix = Path(file.filename or "audio.wav").suffix or ".wav"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_audio:
        audio_bytes = await file.read()
        if not audio_bytes:
            raise HTTPException(status_code=400, detail="Audio upload is empty.")
        temp_audio.write(audio_bytes)
        temp_path = temp_audio.name

    try:
        transcript = voice_service.transcribe(temp_path)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)

    if not transcript:
        raise HTTPException(status_code=400, detail="No speech detected in the audio.")

    history_rows = list_history(limit=1)
    latest_analysis = history_rows[0] if history_rows else None
    response, detected_lang = chat_service.ask(
        transcript,
        language,
        latest_analysis=latest_analysis,
    )
    return VoiceResponse(
        transcript=transcript,
        response=response,
        detected_language=detected_lang,
        model=settings.ollama_model,
    )


@app.get("/history", response_model=list[HistoryItem])
def history(limit: int = 100) -> list[HistoryItem]:
    rows = list_history(limit=limit)
    return [HistoryItem(**row) for row in rows]


@app.get("/orchard/{tree_id}", response_model=list[OrchardHistoryItem])
def orchard_history(tree_id: str, limit: int = 200) -> list[OrchardHistoryItem]:
    rows = list_tree_history(tree_id=tree_id, limit=limit)
    return [OrchardHistoryItem(**row) for row in rows]


@app.post("/orchard/feedback")
def orchard_feedback(payload: OrchardFeedbackRequest) -> dict[str, str]:
    update_tree_feedback(
        tree_id=payload.tree_id,
        treatment_history=payload.treatment_history,
        farmer_feedback=payload.farmer_feedback,
    )
    return {"status": "updated"}
