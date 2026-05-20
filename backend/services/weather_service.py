from __future__ import annotations

from typing import Any

import requests

from backend.core.config import settings


class WeatherRiskService:
    def __init__(self) -> None:
        self.api_key = settings.openweather_api_key
        self.url = settings.openweather_url
        self.units = settings.default_weather_units

    def peacock_spot_risk(self, location: str | None) -> dict[str, Any]:
        if not location:
            return {
                "status": "not_requested",
                "risk": "unknown",
                "note": "Location not provided.",
            }
        if not self.api_key:
            return {
                "status": "unavailable",
                "risk": "unknown",
                "note": "OpenWeather API key missing.",
            }

        params = {
            "q": location,
            "appid": self.api_key,
            "units": self.units,
        }
        try:
            response = requests.get(self.url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            return {
                "status": "error",
                "risk": "unknown",
                "note": f"Weather fetch failed: {exc}",
            }

        main = data.get("main", {})
        rain = data.get("rain", {})
        humidity = float(main.get("humidity", 0.0))
        temperature = float(main.get("temp", 0.0))
        rainfall = float(rain.get("1h", rain.get("3h", 0.0)))

        risk_high = humidity > 70 and 10 <= temperature <= 20 and rainfall > 0
        risk_medium = humidity > 65 and 8 <= temperature <= 24

        if risk_high:
            risk = "high"
        elif risk_medium:
            risk = "medium"
        else:
            risk = "low"

        return {
            "status": "ok",
            "risk": risk,
            "humidity": humidity,
            "temperature_c": temperature,
            "rainfall_mm": rainfall,
        }

