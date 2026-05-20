from __future__ import annotations

from datetime import date, timedelta
import time
from typing import Any

import requests


class OpenMeteoClimateService:
    def __init__(self) -> None:
        self.archive_url = "https://archive-api.open-meteo.com/v1/archive"
        self.forecast_url = "https://api.open-meteo.com/v1/forecast"
        self.cache_ttl_seconds = 60 * 30
        self.current_cache_ttl_seconds = 60
        self._cache: dict[str, tuple[float, dict[str, Any]]] = {}

    def fetch_daily_history(
        self,
        latitude: float,
        longitude: float,
        days: int = 90,
    ) -> dict[str, Any]:
        cache_key = f"{round(latitude, 4)}:{round(longitude, 4)}:{days}"
        cached = self._cache.get(cache_key)
        now = time.time()
        if cached is not None:
            ts, payload = cached
            if now - ts <= self.cache_ttl_seconds:
                return payload

        # Archive endpoint can lag by 1-3 days; use a conservative end date.
        end_date = date.today() - timedelta(days=2)
        start_date = end_date - timedelta(days=max(1, days - 1))
        if start_date > end_date:
            start_date = end_date
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "daily": ",".join(
                [
                    "temperature_2m_mean",
                    "precipitation_sum",
                    "relative_humidity_2m_mean",
                    "shortwave_radiation_sum",
                ]
            ),
            "timezone": "auto",
        }
        payload = self._request_with_daily_fallback(self.archive_url, params)
        self._cache[cache_key] = (now, payload)
        return payload

    def fetch_daily_forecast(
        self,
        latitude: float,
        longitude: float,
        days: int = 10,
    ) -> dict[str, Any]:
        horizon = max(1, min(16, int(days)))
        cache_key = f"forecast:{round(latitude, 4)}:{round(longitude, 4)}:{horizon}"
        cached = self._cache.get(cache_key)
        now = time.time()
        if cached is not None:
            ts, payload = cached
            if now - ts <= self.cache_ttl_seconds:
                return payload

        params = {
            "latitude": latitude,
            "longitude": longitude,
            "forecast_days": horizon,
            "daily": ",".join(
                [
                    "temperature_2m_max",
                    "temperature_2m_min",
                    "precipitation_sum",
                    "relative_humidity_2m_mean",
                    "shortwave_radiation_sum",
                ]
            ),
            "timezone": "auto",
        }
        payload = self._request_with_daily_fallback(self.forecast_url, params)
        self._cache[cache_key] = (now, payload)
        return payload

    def fetch_current_weather(
        self,
        latitude: float,
        longitude: float,
    ) -> dict[str, Any]:
        cache_key = f"current:{round(latitude, 4)}:{round(longitude, 4)}"
        cached = self._cache.get(cache_key)
        now = time.time()
        if cached is not None:
            ts, payload = cached
            if now - ts <= self.current_cache_ttl_seconds:
                return payload

        params = {
            "latitude": latitude,
            "longitude": longitude,
            "current": ",".join(
                [
                    "temperature_2m",
                    "relative_humidity_2m",
                    "precipitation",
                    "rain",
                    "cloud_cover",
                    "wind_speed_10m",
                    "weather_code",
                    "is_day",
                ]
            ),
            "timezone": "auto",
        }
        response = requests.get(self.forecast_url, params=params, timeout=25)
        response.raise_for_status()
        payload = response.json()

        current = payload.get("current", {}) or {}
        units = payload.get("current_units", {}) or {}

        weather_code_raw = current.get("weather_code")
        weather_code = int(weather_code_raw) if weather_code_raw is not None else None
        precipitation = float(current.get("precipitation", 0.0) or 0.0)
        rain = float(current.get("rain", precipitation) or 0.0)
        cloud_cover = float(current.get("cloud_cover", 0.0) or 0.0)
        wind_speed = float(current.get("wind_speed_10m", 0.0) or 0.0)
        is_day_raw = current.get("is_day")
        is_day = bool(int(is_day_raw)) if is_day_raw is not None else None

        summary = {
            "current_time": str(current.get("time", "")),
            "current_temperature": float(current.get("temperature_2m", 0.0) or 0.0),
            "current_humidity": float(current.get("relative_humidity_2m", 0.0) or 0.0),
            "current_precipitation": precipitation,
            "current_rain": rain,
            "current_cloud_cover": cloud_cover,
            "current_wind_speed": wind_speed,
            "current_weather_code": weather_code,
            "current_is_day": is_day,
            "current_weather_type": self._weather_type_from_current(
                precipitation=precipitation,
                rain=rain,
                cloud_cover=cloud_cover,
                weather_code=weather_code,
                wind_speed=wind_speed,
            ),
            "current_units": units,
        }
        self._cache[cache_key] = (now, summary)
        return summary

    @staticmethod
    def _weather_type_from_current(
        *,
        precipitation: float,
        rain: float,
        cloud_cover: float,
        weather_code: int | None,
        wind_speed: float,
    ) -> str:
        if wind_speed >= 22:
            return "windy"
        if rain >= 0.1 or precipitation >= 0.1:
            return "rainy"

        if weather_code in {95, 96, 99}:
            return "storm"
        if weather_code in {51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82}:
            return "rainy"
        if weather_code in {45, 48, 2, 3}:
            return "cloudy"
        if weather_code in {71, 73, 75, 77, 85, 86}:
            return "cloudy"

        if cloud_cover >= 70:
            return "cloudy"
        return "sunny"

    def _request_with_daily_fallback(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        """Request Open-Meteo and gracefully retry when a daily variable is unsupported."""
        response = requests.get(url, params=params, timeout=25)
        if response.ok:
            return response.json()

        # Some endpoints/periods reject relative_humidity_2m_mean in `daily`.
        daily_raw = str(params.get("daily", ""))
        if "relative_humidity_2m_mean" in daily_raw:
            fallback_daily = ",".join(
                [field for field in daily_raw.split(",") if field.strip() and field.strip() != "relative_humidity_2m_mean"]
            )
            fallback_params = dict(params)
            fallback_params["daily"] = fallback_daily
            retry = requests.get(url, params=fallback_params, timeout=25)
            if retry.ok:
                payload = retry.json()
                # Keep shape predictable for downstream logic.
                daily = payload.setdefault("daily", {})
                daily.setdefault("relative_humidity_2m_mean", [])
                return payload
            retry.raise_for_status()

        response.raise_for_status()
        return {}

    def summarize(self, weather_payload: dict[str, Any]) -> dict[str, float | list[dict[str, float | str]]]:
        daily = weather_payload.get("daily", {})
        dates = daily.get("time", []) or []
        temp = daily.get("temperature_2m_mean", []) or []
        rain = daily.get("precipitation_sum", []) or []
        hum = daily.get("relative_humidity_2m_mean", []) or []
        solar = daily.get("shortwave_radiation_sum", []) or []
        humidity_fallback = 62.0

        rows: list[dict[str, float | str]] = []
        for idx, day in enumerate(dates):
            rows.append(
                {
                    "date": str(day),
                    "temperature": float(temp[idx]) if idx < len(temp) and temp[idx] is not None else 0.0,
                    "rainfall": float(rain[idx]) if idx < len(rain) and rain[idx] is not None else 0.0,
                    "humidity": float(hum[idx]) if idx < len(hum) and hum[idx] is not None else humidity_fallback,
                    "solar_radiation": float(solar[idx]) if idx < len(solar) and solar[idx] is not None else 0.0,
                }
            )

        def _period_stats(period_days: int) -> dict[str, float]:
            slice_rows = rows[-period_days:] if len(rows) >= period_days else rows
            if not slice_rows:
                return {
                    "temperature_avg": 0.0,
                    "rainfall_total": 0.0,
                    "humidity_avg": 0.0,
                    "solar_radiation_avg": 0.0,
                }
            return {
                "temperature_avg": round(sum(float(r["temperature"]) for r in slice_rows) / len(slice_rows), 3),
                "rainfall_total": round(sum(float(r["rainfall"]) for r in slice_rows), 3),
                "humidity_avg": round(sum(float(r["humidity"]) for r in slice_rows) / len(slice_rows), 3),
                "solar_radiation_avg": round(
                    sum(float(r["solar_radiation"]) for r in slice_rows) / len(slice_rows), 3
                ),
            }

        p30 = _period_stats(30)
        p60 = _period_stats(60)
        p90 = _period_stats(90)
        return {
            "temperature_avg": p30["temperature_avg"],
            "rainfall_total": p30["rainfall_total"],
            "humidity_avg": p30["humidity_avg"],
            "solar_radiation": p30["solar_radiation_avg"],
            "last_30_days": p30,
            "last_60_days": p60,
            "last_90_days": p90,
            "series": rows,
        }

    def summarize_harvest_context(
        self,
        history_payload: dict[str, Any] | None,
        forecast_payload: dict[str, Any] | None,
    ) -> dict[str, Any]:
        history_summary = self.summarize(history_payload or {})

        forecast_daily = (forecast_payload or {}).get("daily", {}) or {}
        f_dates = forecast_daily.get("time", []) or []
        f_max = forecast_daily.get("temperature_2m_max", []) or []
        f_min = forecast_daily.get("temperature_2m_min", []) or []
        f_rain = forecast_daily.get("precipitation_sum", []) or []
        f_hum = forecast_daily.get("relative_humidity_2m_mean", []) or []
        f_solar = forecast_daily.get("shortwave_radiation_sum", []) or []
        humidity_fallback = float(history_summary.get("humidity_avg", 62.0))

        forecast_rows: list[dict[str, float | str]] = []
        for idx, day in enumerate(f_dates):
            tmax = float(f_max[idx]) if idx < len(f_max) and f_max[idx] is not None else 0.0
            tmin = float(f_min[idx]) if idx < len(f_min) and f_min[idx] is not None else 0.0
            tmean = (tmax + tmin) / 2.0
            forecast_rows.append(
                {
                    "date": str(day),
                    "temperature_max": tmax,
                    "temperature_min": tmin,
                    "temperature_mean": round(tmean, 3),
                    "rainfall": float(f_rain[idx]) if idx < len(f_rain) and f_rain[idx] is not None else 0.0,
                    "humidity": float(f_hum[idx]) if idx < len(f_hum) and f_hum[idx] is not None else humidity_fallback,
                    "solar_radiation": float(f_solar[idx]) if idx < len(f_solar) and f_solar[idx] is not None else 0.0,
                }
            )

        forecast_7 = forecast_rows[:7] if forecast_rows else []
        if forecast_7:
            forecast_summary = {
                "temperature_avg": round(
                    sum(float(r["temperature_mean"]) for r in forecast_7) / len(forecast_7),
                    3,
                ),
                "rainfall_total": round(sum(float(r["rainfall"]) for r in forecast_7), 3),
                "humidity_avg": round(
                    sum(float(r["humidity"]) for r in forecast_7) / len(forecast_7),
                    3,
                ),
                "solar_radiation_avg": round(
                    sum(float(r["solar_radiation"]) for r in forecast_7) / len(forecast_7),
                    3,
                ),
            }
        else:
            forecast_summary = {
                "temperature_avg": history_summary["temperature_avg"],
                "rainfall_total": 0.0,
                "humidity_avg": history_summary["humidity_avg"],
                "solar_radiation_avg": history_summary["solar_radiation"],
            }

        # Weighted blend for harvest timing (recent conditions + short forecast).
        effective_temperature = round(
            (0.7 * float(history_summary["temperature_avg"]))
            + (0.3 * float(forecast_summary["temperature_avg"])),
            3,
        )
        effective_rainfall = round(
            (0.7 * float(history_summary["rainfall_total"]))
            + (0.3 * float(forecast_summary["rainfall_total"])),
            3,
        )
        effective_humidity = round(
            (0.7 * float(history_summary["humidity_avg"]))
            + (0.3 * float(forecast_summary["humidity_avg"])),
            3,
        )
        effective_solar = round(
            (0.7 * float(history_summary["solar_radiation"]))
            + (0.3 * float(forecast_summary["solar_radiation_avg"])),
            3,
        )

        return {
            "temperature_avg": effective_temperature,
            "rainfall_total": effective_rainfall,
            "humidity_avg": effective_humidity,
            "solar_radiation": effective_solar,
            "recent_30_days": history_summary["last_30_days"],
            "recent_60_days": history_summary["last_60_days"],
            "recent_90_days": history_summary["last_90_days"],
            "forecast_7_days": forecast_summary,
            "history_series": history_summary["series"],
            "forecast_series": forecast_rows,
            "weather_available": bool(history_payload),
            "forecast_available": bool(forecast_rows),
        }
