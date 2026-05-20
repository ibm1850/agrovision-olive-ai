from __future__ import annotations

from typing import Any


def generate_alerts(
    *,
    latest_analysis: dict[str, Any] | None,
    weather: dict[str, Any] | None,
    climate_prediction: dict[str, Any] | None,
) -> list[dict[str, str]]:
    alerts: list[dict[str, str]] = []

    if climate_prediction is not None:
        days = int(climate_prediction.get("harvest_window_days", 999))
        if days <= 14:
            alerts.append(
                {
                    "type": "harvest_approaching",
                    "level": "medium",
                    "message": f"Harvest window is approaching ({days} days). Prepare logistics.",
                }
            )

    if latest_analysis is not None:
        disease = str(latest_analysis.get("disease", "None")).lower()
        score = int(latest_analysis.get("health_score", latest_analysis.get("leaf_health_score", 100)))
        if disease not in {"none", "none detected", "healthy"} or score < 60:
            alerts.append(
                {
                    "type": "high_disease_risk",
                    "level": "high",
                    "message": "High disease risk detected. Prioritize treatment and re-scan soon.",
                }
            )

    if weather is not None:
        hum = float(weather.get("humidity_avg", weather.get("humidity", 0.0)))
        temp = float(weather.get("temperature_avg", weather.get("temperature", 0.0)))
        rain = float(weather.get("rainfall_total", weather.get("rainfall_mm", 0.0)))
        if hum > 70 and 10 <= temp <= 20 and rain > 0:
            alerts.append(
                {
                    "type": "fruit_fly_risk",
                    "level": "medium",
                    "message": "Climatic conditions can increase pest/fungal pressure. Intensify monitoring.",
                }
            )
        if rain < 4 and temp > 30:
            alerts.append(
                {
                    "type": "irrigation_need",
                    "level": "medium",
                    "message": "High temperature with low rainfall suggests irrigation stress risk.",
                }
            )

    return alerts
