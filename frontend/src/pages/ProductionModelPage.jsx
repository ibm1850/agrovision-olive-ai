import { useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import { Download, Filter, Info, TrendingUp } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Line, LineChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis, Area, AreaChart } from "recharts";
import OliveGuideCard from "../components/guide/OliveGuideCard";
import { api } from "../lib/api";
import {
  SCORE_TABLES,
  calculateProductionForecast,
  deriveAutoScores,
} from "../lib/productionForecast";
import {
  formatDeltaKg,
  formatKg,
  formatKgRangeWithTons,
  formatKgWithTons,
  formatPercent,
} from "../lib/productionFormat";

function toNumber(value) {
  const n = Number(value);
  return Number.isFinite(n) ? n : 0;
}

function getLatestProductionPayload(dashboard) {
  const scans = dashboard?.recent_scans || [];
  const latest = scans.find(
    (scan) => String(scan?.module_type || "").toLowerCase() === "production_model",
  );
  const payload = latest?.payload_json;
  return payload && typeof payload === "object" ? payload : null;
}

function getDefaultHistoryFromPayload(payload) {
  const inputs = payload?.formula_inputs || {};
  return {
    y1: inputs.Yt_1 != null ? String(inputs.Yt_1) : "",
    y2: inputs.Yt_2 != null ? String(inputs.Yt_2) : "",
    y3: inputs.Yt_3 != null ? String(inputs.Yt_3) : "",
  };
}

function scoreOptions(items, t) {
  return (items || []).map((entry) => ({
    key: entry.key,
    label: `${t(`productionModel.scoreLabels.${entry.key}`, { defaultValue: entry.label })} (${entry.score})`,
  }));
}

function trendChipLabel(trend) {
  if (trend === "up") return "positive";
  if (trend === "down") return "constrained";
  return "stable";
}

function buildForecastTrend(result, y1, y2, y3, t) {
  if (!result) return [];
  const hasY3 = toNumber(y3) > 0;
  const points = [
    { label: hasY3 ? "Y-3" : "Y-2", actual: hasY3 ? toNumber(y3) : toNumber(y2), projected: null },
    { label: "Y-2", actual: toNumber(y2), projected: null },
    { label: "Y-1", actual: toNumber(y1), projected: null },
    { label: t("productionModel.chartLabelNext"), actual: null, projected: result.nextYearForecast, low: result.lowRange, high: result.highRange },
  ];
  return points;
}

function driversTable(result) {
  if (!result?.keyDrivers?.length) return [];
  return result.keyDrivers.map((driver) => ({
    id: driver.id,
    driver: driver.labelKey || driver.label,
    multiplier: driver.value.toFixed(3),
    impact: formatPercent(driver.impactPercent),
    direction: driver.impactPercent >= 0 ? "Supportive" : "Constraining",
  }));
}

export default function ProductionModelPage({
  farmId,
  farmProfile,
  dashboard,
  weather,
  onForecastSaved,
}) {
  const { t } = useTranslation();
  const latestPayload = useMemo(() => getLatestProductionPayload(dashboard), [dashboard]);
  const latestHistory = useMemo(() => getDefaultHistoryFromPayload(latestPayload), [latestPayload]);

  const defaultCultivar = useMemo(() => {
    const fromFarm = farmProfile?.tree_groups?.[0]?.variety;
    const fromDashboard = dashboard?.widgets?.varieties?.[0];
    return fromFarm || fromDashboard || "Unknown";
  }, [farmProfile, dashboard]);

  const [cultivar, setCultivar] = useState(defaultCultivar);
  const [region, setRegion] = useState(farmProfile?.region || "Sfax");
  const [irrigationNotes, setIrrigationNotes] = useState(farmProfile?.climate_notes || "");
  const [y1, setY1] = useState(latestHistory.y1);
  const [y2, setY2] = useState(latestHistory.y2);
  const [y3, setY3] = useState(latestHistory.y3);

  const [overrideRainfall, setOverrideRainfall] = useState("");
  const [overrideHeat, setOverrideHeat] = useState("");
  const [overrideIrrigation, setOverrideIrrigation] = useState("");
  const [overrideDisease, setOverrideDisease] = useState("");
  const [overrideAge, setOverrideAge] = useState("");

  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [savedMessage, setSavedMessage] = useState("");
  const [comparisonMode, setComparisonMode] = useState("this_year");
  const [driverFilter, setDriverFilter] = useState("all");

  useEffect(() => {
    setCultivar(defaultCultivar);
    setRegion(farmProfile?.region || "Sfax");
    setIrrigationNotes(farmProfile?.climate_notes || "");
    setY1(latestHistory.y1);
    setY2(latestHistory.y2);
    setY3(latestHistory.y3);
    setOverrideRainfall("");
    setOverrideHeat("");
    setOverrideIrrigation("");
    setOverrideDisease("");
    setOverrideAge("");
  }, [defaultCultivar, farmProfile, latestHistory]);

  const autoModel = useMemo(() => {
    const autoScores = deriveAutoScores({
      weather,
      farmProfile,
      dashboard,
      cultivar,
      region,
      irrigationNotes,
    });
    return autoScores;
  }, [weather, farmProfile, dashboard, cultivar, region, irrigationNotes]);

  function withOverrides(autoScores) {
    const merged = JSON.parse(JSON.stringify(autoScores));
    if (overrideRainfall) {
      const item = SCORE_TABLES.rainfall.find((s) => s.key === overrideRainfall);
      if (item) merged.scores.rainfall = { ...item, source: "manual" };
    }
    if (overrideHeat) {
      const item = SCORE_TABLES.heat.find((s) => s.key === overrideHeat);
      if (item) merged.scores.heat = { ...item, source: "manual" };
    }
    if (overrideIrrigation) {
      const item = SCORE_TABLES.irrigation.find((s) => s.key === overrideIrrigation);
      if (item) merged.scores.irrigation = { ...item, source: "manual" };
    }
    if (overrideDisease) {
      const item = SCORE_TABLES.disease.find((s) => s.key === overrideDisease);
      if (item) merged.scores.disease = { ...item, source: "manual" };
    }
    if (overrideAge) {
      const item = SCORE_TABLES.age.find((s) => s.key === overrideAge);
      if (item) merged.scores.age = { ...item, source: "manual" };
    }
    return merged;
  }

  function runForecast() {
    setError("");
    setSavedMessage("");

    const Yt_1 = toNumber(y1);
    const Yt_2 = toNumber(y2);
    if (Yt_1 <= 0 || Yt_2 <= 0) {
      setError(t("productionModel.enterHistoryValues"));
      setResult(null);
      return;
    }

    const mergedScores = withOverrides(autoModel);
    const forecast = calculateProductionForecast({
      yt1: Yt_1,
      yt2: Yt_2,
      yt3: toNumber(y3),
      autoScores: mergedScores,
    });

    const assumptions = [...mergedScores.assumptions];
    if (!toNumber(y3)) {
      assumptions.push(t("productionModel.onlyTwoYears"));
    }

    setResult({
      ...forecast,
      assumptions,
      scoreSummary: mergedScores.scores,
    });
  }

  async function saveToHistory() {
    if (!farmId || !result || saving) return;
    setSaving(true);
    setSavedMessage("");
    try {
      await api.createFarmScan(farmId, {
        module_type: "production_model",
        image_count: 1,
        preliminary: false,
        confidence: result.confidenceScore,
        status: result.confidenceLabelKey === "low" ? "pending_review" : "new",
        summary: `${t("productionModel.projectedNextSeasonProduction")}: ${formatKgWithTons(result.nextYearForecast)} | ${t("productionModel.forecastRange")}: ${formatKgRangeWithTons(result.lowRange, result.highRange)}`,
        next_action: displayRecommendation,
        payload_json: {
          projected_next_season_production_kg: result.nextYearForecast,
          projected_next_season_production_t: result.nextYearForecast / 1000,
          estimated_production_range_kg: {
            low: result.lowRange,
            high: result.highRange,
          },
          estimated_production_range_t: {
            low: result.lowRange / 1000,
            high: result.highRange / 1000,
          },
          confidence_score: result.confidenceScore,
          confidence_label: result.confidenceLabel,
          trend_indicator: result.trendIndicator,
          formula_inputs: {
            Yt_1: toNumber(y1),
            Yt_2: toNumber(y2),
            Yt_3: toNumber(y3),
            ...result.formulaInputs,
            cultivar,
            region,
          },
          score_summary: result.scoreSummary,
          comparisons: result.comparisons,
          key_drivers: result.keyDrivers,
          assumptions: result.assumptions,
          recommendation: displayRecommendation,
          generated_at: new Date().toISOString(),
        },
      });
      setSavedMessage(t("productionModel.savedMessage"));
      if (typeof onForecastSaved === "function") onForecastSaved();
    } catch (err) {
      setError(err.message || t("productionModel.saveError"));
    } finally {
      setSaving(false);
    }
  }

  const trendData = buildForecastTrend(result, y1, y2, y3, t);
  const tableRows = driversTable(result).filter((row) => {
    if (driverFilter === "all") return true;
    if (driverFilter === "supportive") return row.direction === "Supportive";
    if (driverFilter === "constraining") return row.direction === "Constraining";
    return true;
  });
  const displayRecommendation = result
    ? t(`productionModel.recommendations.${result.recommendationKey}`, { defaultValue: result.recommendation })
    : "";

  return (
    <section className="page-stack">
      <OliveGuideCard
        title={t("productionModel.title")}
        message={t("productionModel.guideMessage")}
        tip={t("productionModel.guideTip")}
        chips={[t("productionModel.kgPrimary"), t("productionModel.tonsSecondary"), t("productionModel.confidenceLevel")]}
      />

      <article className="surface-card">
        <div className="section-row">
          <div>
            <h2>{t("productionModel.projectedNextSeasonProduction")}</h2>
            <p className="subtle">{t("productionModel.automaticScoresDesc")}</p>
          </div>
          <div className="inline-actions">
            <button className="secondary-btn" onClick={runForecast}><TrendingUp size={16} /> {t("productionModel.runForecast")}</button>
            {result ? (
              <button className="primary-btn" onClick={saveToHistory} disabled={!farmId || saving}>
                <Download size={16} /> {saving ? t("productionModel.saving") : t("productionModel.saveToHistory")}
              </button>
            ) : null}
          </div>
        </div>

        <div className="inline-grid">
          <label>
            {t("productionModel.lastYearProduction")}
            <input className="field" value={y1} onChange={(event) => setY1(event.target.value)} placeholder={t("productionModel.kgExample")} />
          </label>
          <label>
            {t("productionModel.twoYearsAgoProduction")}
            <input className="field" value={y2} onChange={(event) => setY2(event.target.value)} placeholder={t("productionModel.kgExample2")} />
          </label>
          <label>
            {t("productionModel.threeYearsAgoProduction")} ({t("productionModel.optional")})
            <input className="field" value={y3} onChange={(event) => setY3(event.target.value)} placeholder={t("productionModel.optional")} />
          </label>
          <label>
            {t("common.cultivar")}
            <input className="field" value={cultivar} onChange={(event) => setCultivar(event.target.value)} />
          </label>
          <label>
            {t("common.location")}
            <input className="field" value={region} onChange={(event) => setRegion(event.target.value)} />
          </label>
          <label>
            {t("productionModel.irrigation")}
            <input className="field" value={irrigationNotes} onChange={(event) => setIrrigationNotes(event.target.value)} placeholder={t("productionModel.irrigationPlaceholder")} />
          </label>
        </div>

        <details className="filter-panel">
          <summary><Filter size={14} /> {t("productionModel.scoreOverrides")} ({t("productionModel.optional")})</summary>
          <div className="inline-grid">
            <label>
              {t("productionModel.rainfall")}
              <select className="field" value={overrideRainfall} onChange={(event) => setOverrideRainfall(event.target.value)}>
                <option value="">{t("productionModel.autoFromWeather")}</option>
                {scoreOptions(SCORE_TABLES.rainfall, t).map((opt) => <option key={opt.key} value={opt.key}>{opt.label}</option>)}
              </select>
            </label>
            <label>
              {t("productionModel.temperature")}
              <select className="field" value={overrideHeat} onChange={(event) => setOverrideHeat(event.target.value)}>
                <option value="">{t("productionModel.autoFromWeather")}</option>
                {scoreOptions(SCORE_TABLES.heat, t).map((opt) => <option key={opt.key} value={opt.key}>{opt.label}</option>)}
              </select>
            </label>
            <label>
              {t("productionModel.irrigation")}
              <select className="field" value={overrideIrrigation} onChange={(event) => setOverrideIrrigation(event.target.value)}>
                <option value="">{t("productionModel.autoFromNotes")}</option>
                {scoreOptions(SCORE_TABLES.irrigation, t).map((opt) => <option key={opt.key} value={opt.key}>{opt.label}</option>)}
              </select>
            </label>
            <label>
              {t("productionModel.disease")}
              <select className="field" value={overrideDisease} onChange={(event) => setOverrideDisease(event.target.value)}>
                <option value="">{t("productionModel.autoFromDashboard")}</option>
                {scoreOptions(SCORE_TABLES.disease, t).map((opt) => <option key={opt.key} value={opt.key}>{opt.label}</option>)}
              </select>
            </label>
            <label>
              {t("productionModel.treeAge")}
              <select className="field" value={overrideAge} onChange={(event) => setOverrideAge(event.target.value)}>
                <option value="">{t("productionModel.autoFromTreeGroups")}</option>
                {scoreOptions(SCORE_TABLES.age, t).map((opt) => <option key={opt.key} value={opt.key}>{opt.label}</option>)}
              </select>
            </label>
          </div>
        </details>

        {error ? <p className="error-text">{error}</p> : null}
        {savedMessage ? <p className="next-action">{savedMessage}</p> : null}
      </article>

      {result ? (
        <>
          <motion.article className="surface-card" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.25 }}>
            <div className="stats-grid compact">
              <article className="stat-card">
                <p>{t("productionModel.projectedNextSeasonProduction")}</p>
                <h3>{formatKgWithTons(result.nextYearForecast)}</h3>
              </article>
              <article className="stat-card">
                <p>{t("productionModel.forecastRange")}</p>
                <h3>{formatKgRangeWithTons(result.lowRange, result.highRange)}</h3>
              </article>
              <article className="stat-card">
                <p>{t("productionModel.confidenceLevel")}</p>
                <h3>{t(`status.${result.confidenceLabelKey || String(result.confidenceLabel || "").toLowerCase()}`, { defaultValue: result.confidenceLabel })}</h3>
                <small>{Math.round(result.confidenceScore * 100)}%</small>
              </article>
              <article className="stat-card">
                <p>{t("productionModel.vsLastYear")}</p>
                <h3>{t(`dashboard.${trendChipLabel(result.trendIndicator)}Trend`, { defaultValue: trendChipLabel(result.trendIndicator) })}</h3>
                <small>{formatPercent(result.comparisons.vsLastYearPct)} ({formatDeltaKg(result.comparisons.vsLastYearKg)})</small>
              </article>
            </div>
            <p className="subtle">{t("productionModel.vsAverage")}: {formatPercent(result.comparisons.vsAveragePct)} ({formatDeltaKg(result.comparisons.vsAverageKg)}).</p>
            <p className="next-action">{displayRecommendation}</p>
          </motion.article>

          <article className="surface-card">
            <div className="section-row">
              <div>
                <h3>{t("productionModel.yieldOutlookChart")}</h3>
                <p className="subtle">{t("productionModel.chartToggleDesc")}</p>
              </div>
              <div className="inline-actions">
                <button className={`ghost-btn ${comparisonMode === "this_year" ? "active-ghost" : ""}`} onClick={() => setComparisonMode("this_year")}>{t("productionModel.thisSeason")}</button>
                <button className={`ghost-btn ${comparisonMode === "last_year" ? "active-ghost" : ""}`} onClick={() => setComparisonMode("last_year")}>{t("productionModel.lastSeason")}</button>
              </div>
            </div>
            <div className="production-chart-wrap">
              <ResponsiveContainer width="100%" height={280}>
                {comparisonMode === "this_year" ? (
                  <AreaChart data={trendData} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
                    <defs>
                      <linearGradient id="actualLine" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#4a7c59" stopOpacity={0.3} />
                        <stop offset="95%" stopColor="#4a7c59" stopOpacity={0.05} />
                      </linearGradient>
                      <linearGradient id="projectedLine" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#d4a017" stopOpacity={0.35} />
                        <stop offset="95%" stopColor="#d4a017" stopOpacity={0.08} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#d8e0d2" />
                    <XAxis dataKey="label" />
                    <YAxis />
                    <Tooltip />
                    <Area type="monotone" dataKey="actual" stroke="#4a7c59" fill="url(#actualLine)" />
                    <Area type="monotone" dataKey="projected" stroke="#d4a017" fill="url(#projectedLine)" />
                  </AreaChart>
                ) : (
                  <LineChart data={trendData.map((row) => ({ ...row, baseline: toNumber(y2) }))} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#d8e0d2" />
                    <XAxis dataKey="label" />
                    <YAxis />
                    <Tooltip />
                    <Line type="monotone" dataKey="actual" stroke="#4a7c59" strokeWidth={3} dot />
                    <Line type="monotone" dataKey="baseline" stroke="#8b5e3c" strokeWidth={2} strokeDasharray="6 4" dot={false} />
                  </LineChart>
                )}
              </ResponsiveContainer>
            </div>
          </article>

          <article className="surface-card">
            <div className="section-row">
              <div>
                <h3>{t("productionModel.keyDrivers")}</h3>
                <p className="subtle">{t("productionModel.driverFilterDesc")}</p>
              </div>
              <div className="inline-actions">
                <button className={`ghost-btn ${driverFilter === "all" ? "active-ghost" : ""}`} onClick={() => setDriverFilter("all")}>{t("productionModel.allDrivers")}</button>
                <button className={`ghost-btn ${driverFilter === "supportive" ? "active-ghost" : ""}`} onClick={() => setDriverFilter("supportive")}>{t("productionModel.supportive")}</button>
                <button className={`ghost-btn ${driverFilter === "constraining" ? "active-ghost" : ""}`} onClick={() => setDriverFilter("constraining")}>{t("productionModel.constraining")}</button>
              </div>
            </div>
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>{t("productionModel.driverColumn")}</th>
                    <th>{t("productionModel.multiplierColumn")}</th>
                    <th>{t("productionModel.impactColumn")}</th>
                    <th>{t("productionModel.directionColumn")}</th>
                  </tr>
                </thead>
                <tbody>
                  {tableRows.map((row) => (
                    <tr key={row.id}>
                      <td>{t(`productionModel.driverLabels.${row.id}`, { defaultValue: row.driver })}</td>
                      <td>{row.multiplier}</td>
                      <td>{row.impact}</td>
                      <td><span className={`status-pill ${row.direction === "Supportive" ? "high" : "medium"}`}>{row.direction === "Supportive" ? t("productionModel.supportive") : t("productionModel.constraining")}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </article>

          <article className="surface-card assumptions-card">
            <h3><Info size={16} /> {t("productionModel.assumptions")}</h3>
            {result.assumptions.length ? (
              <ul className="quality-list">
                {result.assumptions.map((assumption) => <li key={assumption}>{t(`productionModel.assumptions.${assumption}`, { defaultValue: assumption })}</li>)}
              </ul>
            ) : (
              <p className="subtle">{t("productionModel.noAssumptions")}</p>
            )}
          </article>
        </>
      ) : null}
    </section>
  );
}
