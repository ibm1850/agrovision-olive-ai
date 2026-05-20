from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class PredictTreeResponse(BaseModel):
    variety: str
    variety_confidence: float = Field(ge=0, le=1)
    health: str
    health_status: str
    leaf_health_status: str
    disease: str
    disease_confidence: float = Field(ge=0, le=1)
    severity: str
    leaf_severity: str
    health_score: int = Field(ge=0, le=100)
    leaf_health_score: int = Field(ge=0, le=100)
    risk_level: str
    harvest_window: str
    confidence: str
    infection_percentage: float = Field(ge=0, le=100)
    leaf_count: int = Field(ge=1)
    weather_risk: Optional[str] = None
    image_quality: Optional[str] = None
    notes: str
    gradcam_image: str


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    language: Optional[str] = Field(default=None, description="en, fr, ar")


class ChatResponse(BaseModel):
    response: str
    detected_language: str
    model: str


class VoiceResponse(BaseModel):
    transcript: str
    response: str
    detected_language: str
    model: str


class OliveDetectionResponse(BaseModel):
    detected_olives: int
    avg_confidence: float
    fruit_density: float = 0.0
    fruit_coverage: float = 0.0
    confidence_scores: list[float]
    bounding_boxes: list[list[float]]
    cropped_files: list[str] = []
    crop_urls: list[str] = []


class SceneClassificationResponse(BaseModel):
    scene_type: str
    confidence: float = Field(ge=0, le=1)
    model_name: str


class UnifiedImageAnalysisResponse(BaseModel):
    scene_type: str
    scene_confidence: float = Field(ge=0, le=1)
    route: str
    cultivar: str
    cultivar_source: str
    analysis: dict[str, Any]


class DiseaseScanExpertResponse(BaseModel):
    likely_disease: str
    likely_disease_key: Optional[str] = None
    affected_part: str
    affected_part_key: Optional[str] = None
    confidence: float = Field(ge=0, le=1)
    confidence_label: str
    confidence_label_key: Optional[str] = None
    short_reason: str
    short_reason_key: Optional[str] = None
    next_action: str
    next_action_key: Optional[str] = None
    status: str
    status_key: Optional[str] = None
    plant_part_route: str
    route_confidence: float = Field(ge=0, le=1)
    severity: str = "Unknown"
    severity_key: Optional[str] = None
    quality_gate: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    model_used: str = "DiseaseExpertService-v1"


class HarvestPredictRequest(BaseModel):
    measurements: dict[str, float | int | str]


class HarvestPredictResponse(BaseModel):
    estimated_oil_content: Optional[float] = None
    estimated_fcdm: Optional[float] = None
    estimated_fcfw: Optional[float] = None
    maturity_stage: str
    harvest_recommendation: str
    maturity_index_estimate: float
    ioc_maturity_class: str
    tunisian_window: str
    reliability: str
    model_name: str


class HarvestPredictImageResponse(HarvestPredictResponse):
    cultivar: Optional[str] = None
    cultivar_source: Optional[str] = None
    intended_use: Optional[str] = None
    sample_date: Optional[str] = None
    current_maturity_stage: Optional[str] = None
    typical_harvest_season: Optional[str] = None
    season_status: Optional[str] = None
    season_interpretation: Optional[str] = None
    estimated_time_until_next_harvest_season: Optional[str] = None
    estimated_time_remaining: Optional[str] = None
    harvest_status: Optional[str] = None
    final_harvest_decision: Optional[str] = None
    estimated_harvest_date: Optional[str] = None
    recommended_harvest_window: Optional[str] = None
    days_remaining: Optional[int] = None
    time_remaining: Optional[str] = None
    confidence: Optional[str] = None
    confidence_score: Optional[float] = Field(default=None, ge=0, le=1)
    consistency: Optional[str] = None
    consistency_status: Optional[str] = None
    consistency_check: Optional[str] = None
    possible_reasons: Optional[list[str]] = None
    short_reason: Optional[str] = None
    short_explanation: Optional[str] = None
    next_action: Optional[str] = None
    weather_summary: Optional[dict[str, Any]] = None
    scene_analysis: Optional[dict[str, Any]] = None
    defaults_applied: Optional[list[str]] = None
    ripeness_index: Optional[float] = None
    average_capacitance: Optional[float] = None
    detected_olives: int = Field(ge=0, default=0)
    olive_detection_confidence: float = Field(ge=0, le=1, default=0.0)
    fruit_coverage_percent: float = Field(ge=0, le=100, default=0.0)
    scene_type: Optional[str] = None
    image_analysis: Optional[dict[str, Any]] = None
    climate_analysis: Optional[dict[str, Any]] = None
    final_ai_decision: Optional[dict[str, Any]] = None
    fused_maturity_index: Optional[float] = None
    historical_maturity_index: Optional[float] = None
    harvest_readiness_percent: Optional[float] = Field(default=None, ge=0, le=100)
    season_warning: Optional[str] = None
    debug_trace: Optional[dict[str, Any]] = None
    image_name: str
    notes: str


class HistoryItem(BaseModel):
    id: int
    created_at: datetime
    variety: str
    health_status: str
    disease: str
    severity: str
    health_score: int
    risk_level: str
    harvest_window: str
    image_name: str


class OrchardHistoryItem(BaseModel):
    id: int
    created_at: datetime
    tree_id: str
    location: Optional[str] = None
    disease_prediction: str
    severity: str
    leaf_health_score: int
    infection_percentage: float
    confidence: str
    weather_risk: Optional[str] = None
    image_record: str
    treatment_history: Optional[str] = None
    farmer_feedback: Optional[str] = None


class OrchardFeedbackRequest(BaseModel):
    tree_id: str = Field(min_length=1)
    treatment_history: Optional[str] = None
    farmer_feedback: Optional[str] = None


class RegionItem(BaseModel):
    name: str
    latitude: float
    longitude: float


class CultivarMetadata(BaseModel):
    cultivar: str
    typical_harvest_start: str
    typical_harvest_end: str
    oil_yield: str
    climate_adaptation: str
    region: str


class WeatherPeriodSummary(BaseModel):
    temperature_avg: float
    rainfall_total: float
    humidity_avg: float
    solar_radiation_avg: float


class WeatherInsightsResponse(BaseModel):
    latitude: float
    longitude: float
    region: str
    temperature_avg: float
    rainfall_total: float
    humidity_avg: float
    solar_radiation: float
    current_time: Optional[str] = None
    current_temperature: Optional[float] = None
    current_humidity: Optional[float] = None
    current_precipitation: Optional[float] = None
    current_rain: Optional[float] = None
    current_cloud_cover: Optional[float] = None
    current_wind_speed: Optional[float] = None
    current_weather_code: Optional[int] = None
    current_is_day: Optional[bool] = None
    current_weather_type: Optional[str] = None
    last_30_days: WeatherPeriodSummary
    last_60_days: WeatherPeriodSummary
    last_90_days: WeatherPeriodSummary
    series: list[dict]


class ClimateHarvestRequest(BaseModel):
    latitude: float
    longitude: float
    cultivar: str
    maturity_stage: str
    location: Optional[str] = None
    disease: Optional[str] = None
    health_score: Optional[int] = None
    actual_harvest_date: Optional[str] = None


class ClimateHarvestResponse(BaseModel):
    location: str
    cultivar: str
    cultivar_source: Optional[str] = None
    maturity_stage: str
    temperature_avg: float
    rainfall_last_30_days: float
    humidity_avg: float
    solar_radiation: float
    estimated_oil_content: float
    predicted_oil_content: float
    estimated_fcdm: float
    estimated_fcfw: float
    harvest_window_days: int
    harvest_window: str
    harvest_recommendation: str
    recommendation: str
    confidence_score: float
    climate_maturity_index: Optional[float] = None
    harvest_readiness_percent: Optional[float] = Field(default=None, ge=0, le=100)
    ioc_maturity_class: str
    tunisian_window: str
    agronomic_notes: list[str]
    model_name: str


class AlertItem(BaseModel):
    type: str
    level: str
    message: str


class OrchardCreateRequest(BaseModel):
    user_id: str = Field(min_length=1)
    location: str = Field(min_length=1)
    cultivar: str = "Unknown"
    tree_density: float = Field(default=0.0, ge=0)
    planting_year: int = Field(default=2000, ge=1900, le=2100)
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class OrchardCreateResponse(BaseModel):
    id: int
    user_id: str
    location: str
    cultivar: str
    tree_density: float
    planting_year: int
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    created_at: datetime


class OrchardObservationResponse(BaseModel):
    observation_id: int
    orchard_id: int
    date: str
    scene_type: str
    scene_confidence: float
    analysis: dict[str, Any]


class OrchardObservationHistoryItem(BaseModel):
    observation_id: int
    date: str
    image_path: str
    weather_data: dict[str, Any]
    scene_type: str
    analysis: dict[str, Any]


class OrchardHistoryResponse(BaseModel):
    orchard: OrchardCreateResponse
    observations: list[OrchardObservationHistoryItem]


class OrchardHarvestPredictionResponse(BaseModel):
    orchard_id: int
    cultivar: str
    current_maturity_index: float
    predicted_maturity_next_week: float
    harvest_readiness_percentage: float
    optimal_harvest_week: str
    estimated_harvest_window: str
    estimated_oil_content: float
    oil_quality_risk: str
    notes: list[str]


class TreeGroupBase(BaseModel):
    label: str
    variety: str
    tree_count: int = Field(ge=1)
    age_mode: str = Field(description="exact | range")
    age_exact: Optional[int] = None
    age_min: Optional[int] = None
    age_max: Optional[int] = None
    status: str = "healthy"
    notes: Optional[str] = ""


class TreeGroupCreateRequest(TreeGroupBase):
    pass


class TreeGroupUpdateRequest(BaseModel):
    label: Optional[str] = None
    variety: Optional[str] = None
    tree_count: Optional[int] = Field(default=None, ge=1)
    age_mode: Optional[str] = None
    age_exact: Optional[int] = None
    age_min: Optional[int] = None
    age_max: Optional[int] = None
    status: Optional[str] = None
    notes: Optional[str] = None


class TreeGroupResponse(TreeGroupBase):
    id: int
    farm_id: int
    created_at: datetime


class FarmProfileCreateRequest(BaseModel):
    owner_name: str
    farm_name: str
    country: Optional[str] = ""
    region: Optional[str] = ""
    primary_cultivar: Optional[str] = ""
    tree_age: Optional[int] = Field(default=None, ge=0)
    irrigation_mode: Optional[str] = ""
    climate_notes: Optional[str] = ""
    notes: Optional[str] = ""
    latitude: float
    longitude: float
    total_trees: int = Field(ge=1)
    tree_groups: list[TreeGroupCreateRequest] = Field(default_factory=list)


class FarmProfileUpdateRequest(BaseModel):
    owner_name: Optional[str] = None
    farm_name: Optional[str] = None
    country: Optional[str] = None
    region: Optional[str] = None
    primary_cultivar: Optional[str] = None
    tree_age: Optional[int] = Field(default=None, ge=0)
    irrigation_mode: Optional[str] = None
    climate_notes: Optional[str] = None
    notes: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    total_trees: Optional[int] = Field(default=None, ge=1)


class FarmProfileResponse(BaseModel):
    id: int
    created_at: datetime
    updated_at: datetime
    owner_name: str
    farm_name: str
    country: Optional[str] = ""
    region: Optional[str] = ""
    primary_cultivar: Optional[str] = ""
    tree_age: Optional[int] = None
    irrigation_mode: Optional[str] = ""
    climate_notes: Optional[str] = ""
    notes: Optional[str] = ""
    latitude: float
    longitude: float
    total_trees: int
    tree_groups: list[TreeGroupResponse] = Field(default_factory=list)


class FarmScanCreateRequest(BaseModel):
    tree_group_id: Optional[int] = None
    module_type: str
    image_count: int = Field(default=1, ge=1)
    preliminary: bool = False
    confidence: Optional[float] = Field(default=None, ge=0, le=1)
    status: str = "new"
    summary: str
    next_action: Optional[str] = ""
    payload_json: dict[str, Any] = Field(default_factory=dict)


class FarmScanStatusUpdateRequest(BaseModel):
    status: str


class FarmScanResponse(BaseModel):
    id: int
    farm_id: int
    tree_group_id: Optional[int] = None
    created_at: datetime
    module_type: str
    image_count: int
    preliminary: bool
    confidence: Optional[float] = None
    status: str
    summary: str
    next_action: Optional[str] = ""
    payload_json: dict[str, Any] = Field(default_factory=dict)


class FarmAlertResponse(BaseModel):
    id: int
    farm_id: int
    created_at: datetime
    level: str
    title: str
    message: str
    status: str
    source_scan_id: Optional[int] = None


class FarmNoteCreateRequest(BaseModel):
    text: str
    due_date: Optional[str] = None


class FarmNoteStatusUpdateRequest(BaseModel):
    status: str


class FarmNoteResponse(BaseModel):
    id: int
    farm_id: int
    created_at: datetime
    due_date: Optional[str] = None
    text: str
    status: str


class FarmDashboardResponse(BaseModel):
    farm: FarmProfileResponse
    widgets: dict[str, Any]
    recent_scans: list[FarmScanResponse]
    alerts: list[FarmAlertResponse]
    notes: list[FarmNoteResponse]
