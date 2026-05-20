import { motion } from "framer-motion";
import { AlertTriangle, Camera, CheckCircle2, CloudRain, Droplets, MapPin, SunMedium, Wind } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { CircleMarker, MapContainer, TileLayer } from "react-leaflet";
import QuickActionGrid from "../components/cards/QuickActionGrid";
import LivingOrchardView from "../components/orchard/LivingOrchardView";
import MapViewportSync from "../components/MapViewportSync";
import { buildOrchardSceneState } from "../lib/orchardSceneState";
import WeatherBadge from "../components/WeatherBadge";
import HarvestInsightCard from "../components/cards/HarvestInsightCard";
import AssistantRecommendationCard from "../components/cards/AssistantRecommendationCard";
import { formatMetaLine, formatTemperature } from "../lib/textFormat";
import { formatKgRangeWithTons, formatKgWithTons } from "../lib/productionFormat";

function healthBuckets(scans) {
  const buckets = {
    healthy: 0,
    monitoring: 0,
    disease: 0,
    uncertain: 0,
  };
  for (const scan of scans || []) {
    const status = String(scan.status || "").toLowerCase();
    const summary = String(scan.summary || "").toLowerCase();
    if (status === "pending_review" || summary.includes("uncertain")) {
      buckets.uncertain += 1;
      continue;
    }
    if (summary.includes("disease") || summary.includes("spot") || summary.includes("anthracnose")) {
      buckets.disease += 1;
      continue;
    }
    if (status === "monitoring" || summary.includes("monitor")) {
      buckets.monitoring += 1;
      continue;
    }
    buckets.healthy += 1;
  }
  return buckets;
}

function toTitle(value, t) {
  const text = String(value || "").replaceAll("_", " ").trim();
  if (!text) return "--";
  const lower = text.toLowerCase();
  if (["spring", "summer", "autumn", "winter"].includes(lower)) return t(`seasons.${lower}`);
  if (["sunny", "cloudy", "rainy", "windy", "foggy"].includes(lower)) return t(`weather.${lower}`);
  if (["morning", "afternoon", "evening", "night", "day"].includes(lower)) return t(`timeOfDay.${lower}`);
  if (["dashboard", "harvest time", "disease scan", "production model", "assistant"].includes(lower)) {
    const navMap = {
      dashboard: "nav.dashboard",
      "harvest time": "nav.harvestTime",
      "disease scan": "nav.diseaseScan",
      "production model": "nav.productionModel",
      assistant: "nav.assistant",
    };
    return t(navMap[lower]);
  }
  return text.charAt(0).toUpperCase() + text.slice(1);
}

function translateStoredText(value, t) {
  let text = String(value || "").trim();
  if (!text) return "";
  const replacements = [
    [/Dans la fen[eê]tre active de r[eé]colte/gi, t("harvestTime.inActiveHarvestWindow")],
    [/Hors fen[eê]tre active de r[eé]colte/gi, t("harvestTime.notInActiveHarvestWindow")],
    [/Approaching harvest/gi, t("harvestTime.approachingHarvest")],
    [/Harvest now/gi, t("harvestTime.harvestNow")],
    [/Too early/gi, t("harvestTime.tooEarly")],
    [/Not ready yet/gi, t("harvestTime.notReadyYet")],
    [/Outside current harvest season/gi, t("harvestTime.outsideCurrentHarvestSeason")],
    [/Maintenant|Now/gi, t("common.now", { defaultValue: t("common.today") })],
    [/Résultat|Result/gi, t("diseaseScan.result")],
    [/Moderee|Modérée|Moderate/gi, t("status.medium")],
    [/Review Needed/gi, t("status.pending_review")],
    [/Harvest Approaching/gi, t("harvestTime.approachingHarvest")],
    [/Harvest readiness is high\. Begin preparation now\./gi, `${t("dashboard.harvestReadiness")} ${t("diseaseScan.highConfidence")}. ${t("common.now", { defaultValue: t("common.today") })}`],
    [/A recent AI scan has low confidence and needs agronomist review\./gi, t("diseaseScan.reviewUploadClearer")],
    [/Harvest Time/gi, t("nav.harvestTime")],
    [/Disease Scan/gi, t("nav.diseaseScan")],
    [/Production Model/gi, t("nav.productionModel")],
    [/healthy_leaf/gi, t("diseaseScan.healthy_leaf")],
    [/olive_peacock_spot/gi, t("diseaseScan.olive_peacock_spot")],
    [/aculus_olearius/gi, t("diseaseScan.aculus_olearius")],
    [/uncertain_leaf/gi, t("diseaseScan.uncertain_leaf")],
  ];
  for (const [pattern, replacement] of replacements) {
    text = text.replace(pattern, replacement);
  }
  return text;
}

function readinessTone(value) {
  const n = Number(value || 0);
  if (n >= 75) return "good";
  if (n >= 50) return "warn";
  return "danger";
}

function diseaseTone(alertCount) {
  const count = Number(alertCount || 0);
  if (count >= 3) return "high";
  if (count >= 1) return "medium";
  return "clear";
}

function weatherForecastFromAvg(weather, t) {
  if (!weather) {
    return [
      { day: "D+1", temp: "--", type: t("weather.cloudy") },
      { day: "D+2", temp: "--", type: t("weather.sunny") },
      { day: "D+3", temp: "--", type: t("weather.rainy") },
    ];
  }
  const avg = Number(weather.temperature_avg || 0);
  const rain = Number(weather.rainfall_total || 0);
  const humidity = Number(weather.humidity_avg || 0);
  return [
    { day: "D+1", temp: formatTemperature(avg + 0.8), type: rain > 15 ? t("weather.rainy") : t("weather.sunny") },
    { day: "D+2", temp: formatTemperature(avg - 0.2), type: humidity > 70 ? t("weather.cloudy") : t("weather.sunny") },
    { day: "D+3", temp: formatTemperature(avg + 0.4), type: rain > 10 ? t("weather.rainy") : t("weather.cloudy") },
  ];
}

function productionSeries(widgets, t) {
  if (widgets?.production_forecast_kg == null) return [];
  const forecast = Number(widgets.production_forecast_kg);
  const low = Number(widgets?.production_range_low_kg || forecast * 0.9 || 0);
  const high = Number(widgets?.production_range_high_kg || forecast * 1.1 || 0);
  const last = Number(widgets?.last_year_production_kg || 0);
  const prev = Number(widgets?.two_years_ago_production_kg || 0);
  const hasHistory = last > 0 || prev > 0;
  return [
    { label: "Y-2", actual: hasHistory ? prev : null, projected: null },
    { label: "Y-1", actual: hasHistory ? last : null, projected: null },
    { label: t("common.today"), actual: hasHistory ? (last + prev) / 2 : null, projected: null },
    { label: t("productionModel.chartLabelNext"), actual: null, projected: forecast, low, high },
  ];
}

function kpiTrendText(value, unit = "%") {
  const n = Number(value);
  if (!Number.isFinite(n)) return "--";
  return `${Math.round(n)}${unit}`;
}

function CircularReadiness({ value, t }) {
  const pct = Math.max(0, Math.min(100, Number(value || 0)));
  const radius = 36;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (pct / 100) * circumference;

  return (
    <div className="readiness-ring" aria-label={`${t("dashboard.harvestReadiness")} ${pct}%`}>
      <svg viewBox="0 0 92 92" role="img">
        <circle cx="46" cy="46" r={radius} className="ring-track" />
        <circle
          cx="46"
          cy="46"
          r={radius}
          className="ring-progress"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
        />
      </svg>
      <span>{pct}%</span>
    </div>
  );
}

function DiseaseBadge({ alertCount }) {
  const { t } = useTranslation();
  const tone = diseaseTone(alertCount);
  const label = tone === "high" ? t("status.high") : tone === "medium" ? t("status.medium") : t("status.clear");
  return (
    <span className={`disease-badge ${tone}`}>
      {tone === "clear" ? <CheckCircle2 size={14} /> : <AlertTriangle size={14} />} {label}
    </span>
  );
}

function KPIStat({ title, value, subtitle, children, accent = "green" }) {
  return (
    <motion.article
      className={`kpi-card ${accent}`}
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
    >
      <div>
        <p className="kpi-title">{title}</p>
        <h3>{value}</h3>
        <p className="subtle">{subtitle}</p>
      </div>
      {children}
    </motion.article>
  );
}

function MetricBar({ label, value, suffix, ratio, icon: Icon, tone = "green" }) {
  const width = `${Math.max(8, Math.min(100, Number(ratio || 0) * 100))}%`;
  return (
    <div className="metric-item">
      <div className="metric-head">
        <span><Icon size={14} /> {label}</span>
        <strong>{value}{suffix}</strong>
      </div>
      <div className="metric-track">
        <div className={`metric-fill ${tone}`} style={{ width }} />
      </div>
    </div>
  );
}

export default function DashboardPage({
  dashboard,
  weather,
  loading,
  onRefresh,
  onNavigate,
  orchardOverride,
}) {
  const { t } = useTranslation();

  if (loading && !dashboard) {
    return (
      <section className="page-stack">
        <article className="surface-card skeleton-card" />
        <article className="surface-card skeleton-card" />
        <article className="surface-card skeleton-card" />
      </section>
    );
  }

  if (!dashboard) {
    return (
      <section className="page-stack">
        <article className="surface-card empty-state-card">
          <h2>{t("dashboard.noFarmDashboard")}</h2>
          <p className="subtle">{t("dashboard.noFarmDashboardDesc")}</p>
          <button className="primary-btn" onClick={() => onNavigate("setup")}>{t("nav.farmSetup")}</button>
        </article>
      </section>
    );
  }

  const farm = dashboard.farm;
  const widgets = dashboard.widgets || {};
  const farmLat = Number(farm.latitude || 34.7406);
  const farmLng = Number(farm.longitude || 10.7603);
  const scans = dashboard.recent_scans || [];
  const alerts = dashboard.alerts || [];
  const notes = dashboard.notes || [];
  const buckets = healthBuckets(scans);
  const varieties = Array.isArray(widgets.varieties) ? widgets.varieties.join(", ") : "--";
  const lastScan = scans[0];
  const displayTemperature = weather?.current_temperature ?? weather?.temperature_avg ?? null;
  const topMeta = formatMetaLine([
    farm.region || "--",
    farm.country || t("common.Tunisia"),
    `${t("common.cultivar")}: ${varieties}`,
  ]);
  const sceneState = buildOrchardSceneState({
    farm,
    widgets,
    weather,
    alerts,
    scans,
    harvestOverride: orchardOverride,
  });

  const readiness = Number(widgets.harvest_readiness ?? 0);
  const diseaseAlerts = Number(widgets.disease_alerts ?? 0);
  const forecastSeries = weatherForecastFromAvg(weather, t);
  const productionData = productionSeries(widgets, t);
  const windSpeed = weather?.wind_speed_avg ?? weather?.current_wind_speed;

  return (
    <section className="page-stack">
      <motion.article
        className="dashboard-hero-card"
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
      >
        <div className="dashboard-hero-overlay" />
        <div className="dashboard-hero-head">
          <div>
            <p className="eyebrow">{t("dashboard.farmCommandCenter")}</p>
            <h2>{farm.farm_name}</h2>
            <p className="subtle"><MapPin size={14} /> {topMeta}</p>
          </div>
          <WeatherBadge
            weatherType={sceneState.weather_type}
            temperature={displayTemperature}
            timeOfDay={sceneState.time_of_day}
          />
        </div>

        <div className="kpi-grid">
          <KPIStat
            title={t("dashboard.harvestReadiness")}
            value={kpiTrendText(readiness)}
            subtitle={readiness >= 70 ? t("dashboard.windowApproaching") : t("dashboard.continueWeeklyTracking")}
            accent={readinessTone(readiness)}
          >
            <CircularReadiness value={readiness} t={t} />
          </KPIStat>

          <KPIStat
            title={t("dashboard.diseaseAlert")}
            value={`${diseaseAlerts}`}
            subtitle={t("dashboard.openAlerts")}
            accent={diseaseTone(diseaseAlerts) === "high" ? "danger" : diseaseTone(diseaseAlerts) === "medium" ? "warn" : "green"}
          >
            <DiseaseBadge alertCount={diseaseAlerts} />
          </KPIStat>

          <KPIStat
            title={t("dashboard.lastScan")}
            value={toTitle(lastScan?.module_type || "none", t)}
            subtitle={lastScan?.created_at ? new Date(lastScan.created_at).toLocaleString() : t("dashboard.noScansYet")}
            accent="brown"
          >
            <span className="timestamp-chip"><Camera size={14} /> {lastScan?.id ? `#${lastScan.id}` : "--"}</span>
          </KPIStat>
        </div>

        <div className="hero-weather-mini">
          <div>
            <p className="eyebrow">{t("dashboard.weatherGlance")}</p>
            <h3>{displayTemperature != null ? formatTemperature(displayTemperature) : "--"}</h3>
          </div>
          <div className="mini-forecast-row">
            {forecastSeries.map((item) => (
              <div key={item.day} className="mini-forecast-chip">
                <span>{item.day}</span>
                <strong>{item.temp}</strong>
                <small>{item.type}</small>
              </div>
            ))}
          </div>
        </div>
      </motion.article>

      <div className="dashboard-main-grid">
        <motion.article
          className="living-orchard-card"
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3, delay: 0.05 }}
        >
          <div className="living-orchard-header">
            <div>
              <p className="eyebrow">{t("dashboard.livingOrchardPreview")}</p>
              <h3>{farm.farm_name} <span aria-hidden="true">&middot;</span> {sceneState.cultivar}</h3>
              <p className="subtle">
                {toTitle(sceneState.season, t)} <span aria-hidden="true">&middot;</span> {toTitle(sceneState.time_of_day, t)} <span aria-hidden="true">&middot;</span> {toTitle(sceneState.weather_type, t)}
              </p>
            </div>
            <div className="living-orchard-actions">
              <button className="secondary-btn" onClick={onRefresh} disabled={loading}>
                {loading ? t("dashboard.refreshing") : t("dashboard.refresh")}
              </button>
              <button className="primary-btn" onClick={() => onNavigate("assistant")}>{t("dashboard.askAssistant")}</button>
            </div>
          </div>
          <LivingOrchardView sceneState={sceneState} title={t("dashboard.orchardSimulation")} />
        </motion.article>

        <div className="dashboard-side-stack">
          <article className="weather-card weather-gradient">
            <p className="eyebrow">{t("dashboard.weatherAnalytics")}</p>
            <h3>{weather ? formatTemperature(weather.temperature_avg) : "--"}</h3>
            <p className="subtle">{t("dashboard.recentDays")} <span aria-hidden="true">&middot;</span> {t("common.location")}</p>

            <div className="metric-grid">
              <MetricBar
                label={t("dashboard.rainfall")}
                value={weather?.rainfall_total ?? "--"}
                suffix=" mm"
                ratio={Number(weather?.rainfall_total || 0) / 80}
                icon={CloudRain}
                tone="blue"
              />
              <MetricBar
                label={t("dashboard.humidity")}
                value={weather?.humidity_avg ?? "--"}
                suffix="%"
                ratio={Number(weather?.humidity_avg || 0) / 100}
                icon={Droplets}
                tone="green"
              />
              <MetricBar
                label={t("dashboard.solar")}
                value={weather?.solar_radiation ?? "--"}
                suffix=""
                ratio={Number(weather?.solar_radiation || 0) / 30}
                icon={SunMedium}
                tone="gold"
              />
              <MetricBar
                label={t("weather.windy")}
                value={windSpeed ?? "--"}
                suffix=" km/h"
                ratio={Number(windSpeed || 0) / 40}
                icon={Wind}
                tone="olive"
              />
            </div>

            <div className="sparkline-wrap" aria-hidden="true">
              <svg viewBox="0 0 220 56" preserveAspectRatio="none">
                <polyline
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="3"
                  points="0,40 30,34 60,36 90,28 120,32 150,22 180,26 210,18"
                />
              </svg>
            </div>
          </article>

          <HarvestInsightCard widgets={widgets} sceneState={sceneState} />
          <AssistantRecommendationCard alerts={alerts} scans={scans} onNavigate={onNavigate} />
        </div>
      </div>

      <article className="surface-card production-visual-card">
        <div className="section-row">
          <div>
            <p className="eyebrow">{t("dashboard.projectedProduction")}</p>
            <h3>{widgets.production_forecast_kg != null ? formatKgWithTons(widgets.production_forecast_kg) : "--"}</h3>
            <p className="subtle">{t("productionModel.forecastRange")}: {widgets.production_range_low_kg != null && widgets.production_range_high_kg != null ? formatKgRangeWithTons(widgets.production_range_low_kg, widgets.production_range_high_kg) : "--"}</p>
          </div>
          <button className="secondary-btn" onClick={() => onNavigate("production-model")}>{t("nav.productionModel")}</button>
        </div>
        {productionData.length ? (
          <div className="production-chart-wrap">
            <ResponsiveContainer width="100%" height={260}>
              <AreaChart data={productionData} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="prodActual" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#4a7c59" stopOpacity={0.4} />
                    <stop offset="95%" stopColor="#4a7c59" stopOpacity={0.05} />
                  </linearGradient>
                  <linearGradient id="prodProjected" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#d4a017" stopOpacity={0.45} />
                    <stop offset="95%" stopColor="#d4a017" stopOpacity={0.08} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#d8e0d2" />
                <XAxis dataKey="label" tick={{ fill: "#4f6353", fontSize: 12 }} />
                <YAxis tick={{ fill: "#4f6353", fontSize: 12 }} />
                <Tooltip />
                <Area type="monotone" dataKey="actual" stroke="#4a7c59" fillOpacity={1} fill="url(#prodActual)" />
                <Area type="monotone" dataKey="projected" stroke="#d4a017" fillOpacity={1} fill="url(#prodProjected)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <div className="empty-state-card compact">
            <p>{t("dashboard.noProductionForecastYet", { defaultValue: "Aucune prévision de production enregistrée pour le moment." })}</p>
            <small>{t("dashboard.runProductionModelHint", { defaultValue: "Lancez le module de production pour afficher un intervalle estimatif ici." })}</small>
          </div>
        )}
      </article>

      <div className="stats-grid">
        <article className="stat-card"><p>{t("dashboard.totalTrees")}</p><h3>{widgets.total_trees ?? "--"}</h3></article>
        <article className="stat-card"><p>{t("dashboard.varieties")}</p><h3>{Array.isArray(widgets.varieties) ? widgets.varieties.length : "--"}</h3><small>{varieties}</small></article>
        <article className="stat-card"><p>{t("dashboard.ageGroups")}</p><h3>{widgets.age_groups ?? "--"}</h3></article>
        <article className="stat-card"><p>{t("dashboard.treesScanned")}</p><h3>{widgets.trees_scanned ?? "--"}</h3></article>
        <article className="stat-card"><p>{t("dashboard.harvestReadiness")}</p><h3>{widgets.harvest_readiness != null ? `${widgets.harvest_readiness}%` : "--"}</h3></article>
        <article className="stat-card"><p>{t("dashboard.pendingReviewCases")}</p><h3>{widgets.pending_review_cases ?? 0}</h3></article>
      </div>

      <div className="two-col">
        <article className="surface-card">
          <h3>{t("farmSetup.farmLocation")}</h3>
          <div className="map-wrap">
            <MapContainer key={`dashboard-map-${farm.id}-${farmLat}-${farmLng}`} center={[farmLat, farmLng]} zoom={9} scrollWheelZoom className="dashboard-map">
              <TileLayer
                attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              />
              <MapViewportSync center={[farmLat, farmLng]} zoom={9} />
              <CircleMarker
                center={[farmLat, farmLng]}
                radius={10}
                pathOptions={{ color: "#2f7c2d", fillOpacity: 0.8 }}
              />
            </MapContainer>
          </div>
          <p className="subtle">{t("farmSetup.latitude")} {farmLat.toFixed(4)} <span aria-hidden="true">&middot;</span> {t("farmSetup.longitude")} {farmLng.toFixed(4)}</p>
        </article>

        <article className="surface-card">
          <h3>{t("dashboard.healthOverview")}</h3>
          <div className="health-overview">
            <div><p>{t("dashboard.healthy")}</p><strong>{buckets.healthy}</strong></div>
            <div><p>{t("dashboard.monitoring")}</p><strong>{buckets.monitoring}</strong></div>
            <div><p>{t("dashboard.diseaseDetected")}</p><strong>{buckets.disease}</strong></div>
            <div><p>{t("dashboard.uncertainCases")}</p><strong>{buckets.uncertain}</strong></div>
          </div>
          <div className="module-cta-grid">
            <button className="secondary-btn" onClick={() => onNavigate("production-model")}>{t("productionModel.runForecast")}</button>
            <button className="secondary-btn" onClick={() => onNavigate("harvest-time")}>{t("harvestTime.estimateHarvestTime")}</button>
            <button className="secondary-btn" onClick={() => onNavigate("disease-scan")}>{t("diseaseScan.runScan")}</button>
          </div>
          {widgets.harvest_alert ? <p className="next-action">{translateStoredText(widgets.harvest_alert, t)}</p> : null}
        </article>
      </div>

      <div className="three-col-layout">
        <article className="surface-card">
          <h3>{t("dashboard.recentActivity")}</h3>
          <div className="list-stack">
            {scans.slice(0, 6).map((scan) => (
              <div key={scan.id} className="list-row">
                <div>
                  <strong>{toTitle(scan.module_type, t)}</strong>
                  <p>{translateStoredText(scan.summary, t)}</p>
                </div>
                <span className={`status-pill ${scan.status}`}>{t(`status.${scan.status}`, { defaultValue: scan.status })}</span>
              </div>
            ))}
            {!scans.length ? <p className="subtle">{t("dashboard.noScansHint")}</p> : null}
          </div>
        </article>

        <article className="surface-card">
          <h3>{t("dashboard.activeAlerts")}</h3>
          <div className="list-stack">
            {alerts.slice(0, 6).map((alert) => (
              <div key={alert.id} className="list-row">
                <div>
                  <strong>{translateStoredText(alert.title, t)}</strong>
                  <p>{translateStoredText(alert.message, t)}</p>
                </div>
                <span className={`status-pill ${alert.level}`}>{t(`status.${alert.level}`, { defaultValue: alert.level })}</span>
              </div>
            ))}
            {!alerts.length ? <p className="subtle">{t("dashboard.noActiveAlerts")}</p> : null}
          </div>
        </article>

        <article className="surface-card">
          <h3>{t("dashboard.notesAndReminders")}</h3>
          <div className="list-stack">
            {notes.slice(0, 6).map((note) => (
              <div key={note.id} className="list-row">
                <div>
                  <strong>{note.text}</strong>
                  <p>{t("dashboard.due")}: {note.due_date || t("dashboard.notSet")}</p>
                </div>
                <span className={`status-pill ${note.status}`}>{t(`status.${note.status}`, { defaultValue: note.status })}</span>
              </div>
            ))}
            {!notes.length ? <p className="subtle">{t("dashboard.noNotesYet")}</p> : null}
          </div>
        </article>
      </div>

      <QuickActionGrid
        actions={[
          {
            id: "production-model",
            title: t("nav.productionModel"),
            body: t("dashboard.productionQuickAction"),
            onClick: () => onNavigate("production-model"),
          },
          {
            id: "harvest-time",
            title: t("nav.harvestTime"),
            body: t("dashboard.harvestQuickAction"),
            onClick: () => onNavigate("harvest-time"),
          },
          {
            id: "disease-scan",
            title: t("nav.diseaseScan"),
            body: t("dashboard.diseaseQuickAction"),
            onClick: () => onNavigate("disease-scan"),
          },
        ]}
      />
    </section>
  );
}
