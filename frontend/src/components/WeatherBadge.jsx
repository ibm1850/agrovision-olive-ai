import { formatTemperature, sanitizeText } from "../lib/textFormat";
import { useTranslation } from "react-i18next";

const WEATHER_ICONS = {
  sunny: "/orchard-weather/sun.gif",
  cloudy: "/orchard-weather/cloudy.gif",
  rainy: "/orchard-weather/rain.gif",
  storm: "/orchard-weather/storm.gif",
  night: "/orchard-weather/night.gif",
  windy: "/orchard-weather/cloudy.gif",
  dry_hot: "/orchard-weather/sun.gif",
};

function labelForWeather(type, t) {
  const raw = String(type || "sunny").toLowerCase();
  if (!raw) return t("weather.sunny");
  if (raw === "dry_hot") return t("weather.dryHeat");
  return t(`weather.${raw}`, { defaultValue: raw.charAt(0).toUpperCase() + raw.slice(1) });
}

export default function WeatherBadge({ weatherType, temperature, timeOfDay = "day" }) {
  const { t } = useTranslation();
  const icon = timeOfDay === "night" ? WEATHER_ICONS.night : WEATHER_ICONS[weatherType] || WEATHER_ICONS.sunny;
  const label = labelForWeather(weatherType, t);

  return (
    <div className="weather-badge">
      <div className="weather-badge-icon">
        <img src={icon} alt={t("dashboard.weather")} />
      </div>
      <div className="weather-badge-text">
        <strong>{temperature != null ? formatTemperature(temperature) : "--"}</strong>
        <span>{sanitizeText(label)}</span>
      </div>
    </div>
  );
}
