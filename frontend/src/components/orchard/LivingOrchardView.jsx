import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { projectFruitStage } from "../../lib/orchardSceneState";
import { formatMetaLine, sanitizeText } from "../../lib/textFormat";

const SEASONAL_TREES = {
  spring: "/orchard-seasonal/spring.png",
  summer: "/orchard-seasonal/summer.png",
  autumn: "/orchard-seasonal/autumn.png",
  winter: "/orchard-seasonal/winter.png",
};

function stageLabel(stage, t) {
  if (stage === "no_fruit") return t("orchard.noFruit");
  if (stage === "start_of_color_change") return t("harvestTime.startOfColorChange");
  if (stage === "yellow-green") return t("harvestTime.yellowGreen");
  if (stage === "mature") return t("harvestTime.mature");
  return t("harvestTime.green");
}

function toTitle(value, t) {
  const clean = String(value || "").replaceAll("_", " ").trim();
  if (!clean) return "--";
  const lower = clean.toLowerCase();
  if (["spring", "summer", "autumn", "winter"].includes(lower)) return t(`seasons.${lower}`);
  if (["sunny", "cloudy", "rainy", "windy", "foggy"].includes(lower)) return t(`weather.${lower}`);
  if (["morning", "afternoon", "evening", "night", "day"].includes(lower)) return t(`timeOfDay.${lower}`);
  if (["low", "medium", "high"].includes(lower)) return t(`status.${lower}`);
  return clean.charAt(0).toUpperCase() + clean.slice(1);
}

function formatTemp(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return "--";
  return `${n.toFixed(1)}\u00B0C`;
}

function formatHumidity(value, t) {
  const n = Number(value);
  if (!Number.isFinite(n)) return "--";
  return `${n.toFixed(1)}% ${t("dashboard.humidity").toLowerCase()}`;
}

function WeatherBadgeIcon({ weatherType }) {
  const rainy = weatherType === "rainy" || weatherType === "storm";
  const cloudy = weatherType === "cloudy";
  const sunny = weatherType === "sunny" || weatherType === "dry_hot";

  if (sunny) {
    return (
      <svg viewBox="0 0 24 24" className="weather-badge-svg" aria-hidden="true">
        <circle cx="12" cy="12" r="4.5" fill="#d4a017" />
        <g stroke="#e7b93a" strokeWidth="1.5" strokeLinecap="round">
          <path d="M12 1.8v3.1" />
          <path d="M12 19.1v3.1" />
          <path d="M1.8 12h3.1" />
          <path d="M19.1 12h3.1" />
          <path d="m4.2 4.2 2.2 2.2" />
          <path d="m17.6 17.6 2.2 2.2" />
          <path d="m19.8 4.2-2.2 2.2" />
          <path d="m6.4 17.6-2.2 2.2" />
        </g>
      </svg>
    );
  }

  return (
    <svg viewBox="0 0 24 24" className="weather-badge-svg" aria-hidden="true">
      <path
        d="M6.2 15.2h11.1a3.4 3.4 0 0 0 .2-6.9 5.5 5.5 0 0 0-10.7 1.2 3 3 0 0 0-.6 5.7Z"
        fill={cloudy ? "#8aa8bf" : "#6b9fd4"}
      />
      {rainy ? (
        <g stroke="#a8d4f5" strokeWidth="1.2" strokeLinecap="round">
          <line x1="8.4" y1="16.5" x2="8.4" y2="20.3" className="badge-rain-line line-1" />
          <line x1="12" y1="16.9" x2="12" y2="21" className="badge-rain-line line-2" />
          <line x1="15.6" y1="16.5" x2="15.6" y2="20.3" className="badge-rain-line line-3" />
        </g>
      ) : null}
    </svg>
  );
}

export default function LivingOrchardView({ sceneState, title, compact = false }) {
  const { t } = useTranslation();
  const safeTitle = title || t("dashboard.livingOrchardPreview");
  const timelineSteps = [
    { id: "today", label: t("dashboard.today"), offset: 0 },
    { id: "d10", label: t("dashboard.in10Days"), offset: 10 },
    { id: "d20", label: t("dashboard.in20Days"), offset: 20 },
    { id: "window", label: t("dashboard.harvestWindow"), offset: 28 },
  ];
  const seasonalGuidance = {
    spring: t("orchard.springGuidance"),
    summer: t("orchard.summerGuidance"),
    autumn: t("orchard.autumnGuidance"),
    winter: t("orchard.winterGuidance"),
  };
  const [stepId, setStepId] = useState("today");
  const activeStepIndex = Math.max(
    0,
    timelineSteps.findIndex((step) => step.id === stepId),
  );

  const season = sceneState?.season || "spring";
  const weatherType = sceneState?.weather_type || "sunny";
  const timeOfDay = sceneState?.time_of_day || "morning";
  const temperature = sceneState?.current_temperature ?? sceneState?.temperature_avg;
  const humidity = sceneState?.current_humidity ?? sceneState?.humidity_avg;
  const readiness = Number(sceneState?.harvest_readiness ?? 50);
  const sourceFruitStage = sceneState?.fruit_state || sceneState?.fruit_stage || "green";

  const projectedStage = useMemo(
    () => projectFruitStage(sourceFruitStage, activeStepIndex, readiness),
    [sourceFruitStage, activeStepIndex, readiness],
  );

  const treeImage = SEASONAL_TREES[season] || SEASONAL_TREES.spring;

  const metaLine = formatMetaLine([
    sceneState?.cultivar || t("common.unknownCultivar"),
    toTitle(season, t),
    toTitle(timeOfDay, t),
    toTitle(weatherType, t),
  ]);

  const guidance = seasonalGuidance[season] || seasonalGuidance.spring;
  const isRainy = weatherType === "rainy" || weatherType === "storm";
  const showClouds = weatherType === "cloudy" || isRainy || weatherType === "storm";
  const showSunRays = weatherType === "sunny" || weatherType === "dry_hot";

  const raindrops = useMemo(() => {
    if (!isRainy) return [];
    const count = 36;
    return Array.from({ length: count }).map((_, index) => ({
      id: `${weatherType}-${index}`,
      left: `${Math.random() * 100}%`,
      delay: `${(Math.random() * 2).toFixed(2)}s`,
      duration: `${(0.6 + Math.random() * 0.6).toFixed(2)}s`,
      height: `${Math.round(12 + Math.random() * 8)}px`,
      opacity: (0.45 + Math.random() * 0.35).toFixed(2),
    }));
  }, [isRainy, weatherType]);

  return (
    <article
      className={`living-orchard-view season-${season} weather-${weatherType} tod-${timeOfDay} stage-${projectedStage} ${compact ? "compact" : ""}`}
    >
      <div className="orchard-top">
        <div>
          <p className="eyebrow">{safeTitle}</p>
          <h3>{sanitizeText(sceneState?.location || "--")}</h3>
          <p className="subtle orchard-meta">{metaLine}</p>
        </div>
        <div className="orchard-badges">
          <span className="badge badge-readiness">{t("dashboard.readiness")} {Math.round(readiness)}%</span>
          <span className={`badge badge-alert-${sceneState?.disease_alert_level || "low"}`}>
            {t("dashboard.diseaseAlert")} {toTitle(sceneState?.disease_alert_level || "low", t)}
          </span>
          <span className="badge">{t("dashboard.fruitStage")} {stageLabel(projectedStage, t)}</span>
        </div>
      </div>

      <div className="orchard-canvas">
        {showClouds ? (
          <svg className="orchard-cloud-canopy" viewBox="0 0 1200 230" preserveAspectRatio="none" aria-hidden="true">
            <path d="M0,150 C90,95 200,115 300,140 C390,80 490,70 575,118 C660,75 760,80 845,130 C950,90 1060,100 1200,150 L1200,0 L0,0 Z" />
          </svg>
        ) : null}

        {showSunRays ? <div className="orchard-sun-rays" /> : null}

        <div className="orchard-scene-meta">
          <span>{toTitle(season, t)}</span>
          <span aria-hidden="true">&middot;</span>
          <span>{toTitle(weatherType, t)}</span>
          <span aria-hidden="true">&middot;</span>
          <span>{toTitle(timeOfDay, t)}</span>
        </div>

        <div className="orchard-season-tip">
          <strong>{t("dashboard.seasonalGuidance")}</strong>
          <p>{guidance}</p>
        </div>

        <div className="orchard-weather-badge">
          <WeatherBadgeIcon weatherType={weatherType} />
          <strong>{formatTemp(temperature)}</strong>
          <span>
            <svg viewBox="0 0 16 16" className="weather-humidity-icon" aria-hidden="true">
              <path d="M8 1.8C6.1 4.4 4.4 6.3 4.4 8.7A3.6 3.6 0 0 0 8 12.3a3.6 3.6 0 0 0 3.6-3.6c0-2.4-1.7-4.3-3.6-6.9Z" fill="#7cb4d7" />
            </svg>
            {formatHumidity(humidity, t)}
          </span>
        </div>

        {timeOfDay === "night" ? <div className="orchard-moon" /> : null}

        <div className="orchard-tree-layer">
          <img src={treeImage} alt={t("dashboard.livingOrchard")} className="orchard-tree-image" />
          <div className="orchard-tree-shadow" />
          <div className="orchard-foreground-grass" />
        </div>

        {isRainy ? (
          <div className="orchard-rain-layer" aria-hidden="true">
            {raindrops.map((drop) => (
              <span
                key={drop.id}
                className="raindrop"
                style={{
                  left: drop.left,
                  animationDelay: drop.delay,
                  animationDuration: drop.duration,
                  height: drop.height,
                  opacity: drop.opacity,
                }}
              />
            ))}
          </div>
        ) : null}

        <div className="orchard-overlay orchard-weather" />
        <div className="orchard-overlay orchard-time" />
      </div>

      {!compact ? (
        <div className="orchard-timeline">
          {timelineSteps.map((step) => (
            <button
              key={step.id}
              className={`timeline-step ${step.id === stepId ? "active" : ""}`}
              onClick={() => setStepId(step.id)}
            >
              <span>{step.label}</span>
              <small>+{step.offset}d</small>
            </button>
          ))}
        </div>
      ) : null}
    </article>
  );
}
