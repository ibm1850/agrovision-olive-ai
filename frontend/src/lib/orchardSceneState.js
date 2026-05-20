const FRUIT_STAGES = ["no_fruit", "green", "yellow-green", "start_of_color_change", "mature"];

export function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

export function toTreeAgeGroup(treeGroups = []) {
  const ages = [];
  for (const group of treeGroups || []) {
    const mode = String(group?.age_mode || "").toLowerCase();
    if (mode === "exact" && Number.isFinite(Number(group?.age_exact))) {
      ages.push(Number(group.age_exact));
    } else if (
      Number.isFinite(Number(group?.age_min)) &&
      Number.isFinite(Number(group?.age_max))
    ) {
      ages.push((Number(group.age_min) + Number(group.age_max)) / 2);
    }
  }
  const avg = ages.length ? ages.reduce((sum, age) => sum + age, 0) / ages.length : 8;
  if (avg <= 3) return "young";
  if (avg <= 8) return "growing";
  if (avg <= 20) return "mature";
  return "established";
}

export function detectSeason(dateValue) {
  const date = dateValue ? new Date(dateValue) : new Date();
  const month = date.getMonth() + 1;
  if (month >= 3 && month <= 5) return "spring";
  if (month >= 6 && month <= 8) return "summer";
  if (month >= 9 && month <= 11) return "autumn";
  return "winter";
}

export function detectTimeOfDay(dateValue) {
  const date = dateValue ? new Date(dateValue) : new Date();
  const hour = date.getHours();
  if (hour >= 5 && hour < 11) return "morning";
  if (hour >= 11 && hour < 17) return "midday";
  if (hour >= 17 && hour < 21) return "evening";
  return "night";
}

export function weatherTypeFromSummary(weather) {
  if (!weather) return "sunny";
  const liveType = String(weather.current_weather_type || "").toLowerCase().trim();
  if (liveType) return liveType;

  const currentRain = Number(weather.current_rain ?? weather.current_precipitation);
  const currentCloud = Number(weather.current_cloud_cover);
  const currentWind = Number(weather.current_wind_speed);
  if (Number.isFinite(currentWind) && currentWind >= 22) return "windy";
  if (Number.isFinite(currentRain) && currentRain >= 0.1) return "rainy";
  if (Number.isFinite(currentCloud) && currentCloud >= 70) return "cloudy";

  const rain = Number(weather.rainfall_total ?? 0);
  const humidity = Number(weather.humidity_avg ?? 0);
  const temp = Number(weather.temperature_avg ?? 0);
  const wind = Number(weather.wind_speed_avg ?? weather.current_wind_speed ?? 0);
  if (wind >= 22) return "windy";
  if (rain >= 18) return "rainy";
  if (humidity >= 72) return "cloudy";
  if (temp >= 30) return "dry_hot";
  return "sunny";
}

export function normalizeFruitStage(raw) {
  const text = String(raw || "").toLowerCase().replace(/\s+/g, "_");
  if (!text) return "green";
  if (text.includes("mature") || text.includes("black")) return "mature";
  if (text.includes("color_change") || text.includes("ripen") || text.includes("turning")) {
    return "start_of_color_change";
  }
  if (text.includes("yellow")) return "yellow-green";
  if (text.includes("green")) return "green";
  return "green";
}

export function stageFromHarvestSignals({ override, scans, widgets }) {
  if (override?.fruit_stage) return normalizeFruitStage(override.fruit_stage);

  const harvestScan = (scans || []).find((scan) => scan?.module_type === "harvest_time");
  const payload = harvestScan?.payload_json || {};
  if (payload.current_maturity_stage) {
    return normalizeFruitStage(payload.current_maturity_stage);
  }
  if (payload.image_analysis?.visual_stage) {
    return normalizeFruitStage(payload.image_analysis.visual_stage);
  }

  const widgetText = String(
    widgets?.last_harvest_prediction || widgets?.last_harvest_summary || widgets?.harvest_alert || "",
  );
  if (widgetText.toLowerCase().includes("mature")) return "mature";
  if (widgetText.toLowerCase().includes("color")) return "start_of_color_change";
  if (widgetText.toLowerCase().includes("yellow")) return "yellow-green";
  return "green";
}

export function diseaseAlertLevel({ alerts, widgets }) {
  const activeAlerts = alerts || [];
  const high = activeAlerts.some((a) => String(a.level || "").toLowerCase() === "high");
  const medium = activeAlerts.some((a) => String(a.level || "").toLowerCase() === "medium");
  const widgetAlerts = Number(widgets?.disease_alerts ?? 0);
  if (high || widgetAlerts >= 3) return "high";
  if (medium || widgetAlerts > 0) return "medium";
  return "low";
}

export function harvestReadinessValue(widgets, override) {
  if (Number.isFinite(Number(override?.harvest_readiness))) {
    return clamp(Number(override.harvest_readiness), 0, 100);
  }
  if (Number.isFinite(Number(widgets?.harvest_readiness))) {
    return clamp(Number(widgets.harvest_readiness), 0, 100);
  }
  return 45;
}

export function projectFruitStage(currentStage, stepIndex, readiness) {
  const idx = Math.max(0, FRUIT_STAGES.indexOf(currentStage));
  const progress = stepIndex >= 3 ? 2 : stepIndex >= 1 ? 1 : 0;
  const readinessPush = readiness >= 85 ? 2 : readiness >= 60 ? 1 : 0;
  const projected = clamp(idx + progress + readinessPush, 0, FRUIT_STAGES.length - 1);
  return FRUIT_STAGES[projected];
}

export function buildOrchardSceneState({
  farm,
  widgets,
  weather,
  alerts,
  scans,
  harvestOverride,
}) {
  const tree_age_group = toTreeAgeGroup(farm?.tree_groups || []);
  // Use real current season for dashboard simulation so the scene reflects "now".
  const season = detectSeason();
  const time_of_day = weather?.current_is_day === false ? "night" : detectTimeOfDay();
  const weather_type = weatherTypeFromSummary(weather);
  const fruit_stage = stageFromHarvestSignals({
    override: harvestOverride,
    scans,
    widgets,
  });
  const harvest_readiness = harvestReadinessValue(widgets, harvestOverride);
  const disease_alert_level = diseaseAlertLevel({ alerts, widgets });

  const fruit_state =
    tree_age_group === "young" && harvest_readiness < 38
      ? "no_fruit"
      : fruit_stage;

  return {
    tree_age_group,
    season,
    time_of_day,
    weather_type,
    temperature_avg: weather?.temperature_avg ?? null,
    humidity_avg: weather?.humidity_avg ?? null,
    current_temperature: weather?.current_temperature ?? null,
    current_humidity: weather?.current_humidity ?? null,
    fruit_stage,
    fruit_state,
    harvest_readiness,
    disease_alert_level,
    cultivar: harvestOverride?.cultivar || farm?.tree_groups?.[0]?.variety || "Unknown",
    location: farm?.region || "--",
  };
}
