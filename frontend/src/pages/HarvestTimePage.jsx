import { useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import { CalendarDays, CloudSun, MapPin, ShieldCheck } from "lucide-react";
import { useTranslation } from "react-i18next";
import DragDropUpload from "../components/DragDropUpload";
import { api } from "../lib/api";
import { assessImageQuality } from "../lib/imageQuality";
import OliveGuideCard from "../components/guide/OliveGuideCard";
import HarvestResultCard from "../components/cards/HarvestResultCard";

function confidenceToNumber(label, score) {
  if (typeof score === "number" && Number.isFinite(score)) return score;
  const text = String(label || "").toLowerCase();
  if (text === "high") return 0.88;
  if (text === "low") return 0.52;
  return 0.7;
}

function formatDate(value) {
  if (!value) return "--";
  try {
    return new Date(value).toLocaleDateString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  } catch {
    return String(value);
  }
}

function normalizeText(value) {
  return String(value || "")
    .trim()
    .toLowerCase()
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ");
}

function friendlyHarvestStatusValue(value, t) {
  const raw = normalizeText(value);
  if (!raw) return t("harvestTime.pendingEstimate");
  if (raw.includes("data inconsistency")) return t("harvestTime.dataInconsistency");
  if (raw.includes("outside current harvest season")) return t("harvestTime.outsideCurrentHarvestSeason");
  if (raw.includes("next season cycle")) return t("harvestTime.nextSeasonCycle");
  if (raw.includes("late") || raw.includes("urgent")) return t("harvestTime.lateUrgent");
  if (raw.includes("harvest now") || raw.includes("ready now")) return t("harvestTime.harvestNow");
  if (raw.includes("approaching") || raw.includes("near optimal") || raw.includes("récolte proche")) return t("harvestTime.approachingHarvest");
  if (raw.includes("too early")) return t("harvestTime.tooEarly");
  if (raw.includes("not ready")) return t("harvestTime.notReadyYet");
  if (raw.includes("not in active harvest window")) return t("harvestTime.notInActiveHarvestWindow");
  if (raw.includes("in active harvest window")) return t("harvestTime.inActiveHarvestWindow");
  return value || t("harvestTime.pendingEstimate");
}

function friendlyMaturityStage(value, t) {
  const raw = normalizeText(value);
  if (!raw) return "--";
  if (raw.includes("yellow")) return t("harvestTime.yellowGreen");
  if (raw.includes("color")) return t("harvestTime.startOfColorChange");
  if (raw.includes("mature")) return t("harvestTime.mature");
  if (raw.includes("green")) return t("harvestTime.green");
  return value;
}

function friendlyConfidence(value, t) {
  const raw = normalizeText(value);
  if (raw.includes("high") || raw.includes("élev") || raw.includes("عالية")) return t("diseaseScan.highConfidence");
  if (raw.includes("low") || raw.includes("faible") || raw.includes("منخفض")) return t("diseaseScan.lowConfidence");
  if (raw.includes("medium") || raw.includes("moy") || raw.includes("متوسط")) return t("diseaseScan.mediumConfidence");
  return value || t("diseaseScan.mediumConfidence");
}

function friendlyHarvestNote(value, t) {
  const raw = normalizeText(value);
  if (!raw) return "";
  if (raw.includes("image maturity") && raw.includes("season")) return t("harvestTime.dataInconsistency");
  if (raw.includes("season gate") || raw.includes("outside normal harvest season")) return t("harvestTime.outsideCurrentHarvestSeason");
  if (raw.includes("not in active harvest window")) return t("harvestTime.notInActiveHarvestWindow");
  if (raw.includes("in active harvest window")) return t("harvestTime.inActiveHarvestWindow");
  if (raw.includes("weather history unavailable")) return t("harvestTime.weatherFallback");
  if (raw.includes("unknown tunisian cultivar")) return t("harvestTime.cultivarAware");
  if (raw.includes("verify sample date")) return t("harvestTime.dataInconsistency");
  if (raw.includes("recheck") && raw.includes("3") && raw.includes("5")) return t("harvestTime.monitorColorChange");
  if (raw.includes("recheck") || raw.includes("rescan")) return t("harvestTime.likelyReadinessCheckpoint");
  return value;
}

function isUrgentDecision(result) {
  const status = String(result?.harvest_status || "").toLowerCase();
  const action = String(result?.next_action || "").toLowerCase();
  return (
    status.includes("late / urgent") ||
    status.includes("ready now") ||
    status.includes("urgent") ||
    action.includes("harvest now") ||
    action.includes("harvest immediately")
  );
}

function friendlyDecisionLabel(result, t) {
  return friendlyHarvestStatusValue(
    result?.final_harvest_decision || result?.harvest_status || result?.season_interpretation || result?.season_status,
    t,
  );
}

function friendlySeasonInterpretation(result, t) {
  const raw = String(result?.season_interpretation || "").toLowerCase();
  if (raw === "data inconsistency") return t("harvestTime.outsideCurrentHarvestSeason");
  if (raw === "next season cycle") return t("harvestTime.nextSeasonCycle");
  return friendlyHarvestStatusValue(result?.season_interpretation, t) || "--";
}

function friendlyConsistency(result, t) {
  const raw = String(result?.consistency_check || result?.consistency || result?.consistency_status || "consistent").toLowerCase();
  if (raw === "inconsistent") return t("harvestTime.inconsistent");
  if (raw === "consistent") return t("harvestTime.consistent");
  return result?.consistency_check || result?.consistency || result?.consistency_status || "consistent";
}

function displayHarvestDate(result, t) {
  if (isUrgentDecision(result)) return t("common.today");
  return formatDate(result?.estimated_harvest_date);
}

function displayHarvestWindow(result, t) {
  if (isUrgentDecision(result)) return t("harvestTime.immediateWindow");
  return result?.recommended_harvest_window || "--";
}

function buildHarvestCalendar(sampleDate, windowText, status, t) {
  const base = sampleDate ? new Date(sampleDate) : new Date();
  const in10 = new Date(base);
  in10.setDate(base.getDate() + 10);
  const in20 = new Date(base);
  in20.setDate(base.getDate() + 20);

  return [
    {
      id: "today",
      label: t("dashboard.today"),
      date: base,
      tone: "current",
      note: status || t("harvestTime.currentFieldSample"),
    },
    {
      id: "d10",
      label: t("dashboard.in10Days"),
      date: in10,
      tone: "watch",
      note: t("harvestTime.monitorColorChange"),
    },
    {
      id: "d20",
      label: t("dashboard.in20Days"),
      date: in20,
      tone: "near",
      note: t("harvestTime.likelyReadinessCheckpoint"),
    },
    {
      id: "window",
      label: t("dashboard.harvestWindow"),
      date: null,
      tone: "window",
      note: windowText || t("harvestTime.pendingEstimate"),
    },
  ];
}

export default function HarvestTimePage({
  farmId,
  farmProfile,
  onScanSaved,
  onApplyOrchardUpdate,
}) {
  const { t, i18n } = useTranslation();
  const language = i18n.resolvedLanguage || i18n.language || "fr";
  const [file, setFile] = useState(null);
  const [sampleDate, setSampleDate] = useState(new Date().toISOString().slice(0, 10));
  const [location, setLocation] = useState(farmProfile?.region || "Sfax");
  const [cultivar, setCultivar] = useState(farmProfile?.tree_groups?.[0]?.variety || "Chemlali Sfax");
  const [intendedUse, setIntendedUse] = useState("oil");
  const [treeAge, setTreeAge] = useState("");
  const [irrigationNotes, setIrrigationNotes] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [qualityHints, setQualityHints] = useState([]);
  const [result, setResult] = useState(null);
  const [showWhy, setShowWhy] = useState(false);
  const [orchardApplied, setOrchardApplied] = useState(false);
  const isInconsistency = result?.consistency === "inconsistent" || result?.consistency_status === "inconsistent";

  const defaultsLabel = useMemo(() => {
    const raw = Array.isArray(result?.defaults_applied) ? result.defaults_applied : [];
    if (!raw.length) return t("harvestTime.noDefaultsApplied");

    let cleaned = raw;
    if (isInconsistency) {
      cleaned = cleaned.filter((entry) => {
        const text = String(entry || "").toLowerCase();
        return !(
          text.includes("data inconsistency detected between image maturity and harvest season") ||
          text.includes("image maturity and season profile conflict") ||
          text.includes("season gate indicates sample date is outside normal harvest season")
        );
      });
    }

    const unique = [];
    const seen = new Set();
    for (const entry of cleaned) {
      const text = String(entry || "").trim();
      if (!text) continue;
      const key = text.toLowerCase();
      if (seen.has(key)) continue;
      seen.add(key);
      unique.push(friendlyHarvestNote(text, t));
    }
    return unique.length ? unique.join(" ") : t("harvestTime.noDefaultsApplied");
  }, [result, isInconsistency, t]);

  const calendarItems = useMemo(() => {
    const decision = result ? friendlyHarvestStatusValue(result.final_harvest_decision || result.harvest_status, t) : "";
    return buildHarvestCalendar(sampleDate, result?.recommended_harvest_window, decision, t);
  }, [sampleDate, result, t]);

  useEffect(() => {
    setLocation(farmProfile?.region || "Sfax");
    setCultivar(farmProfile?.tree_groups?.[0]?.variety || "Chemlali Sfax");
  }, [farmProfile?.id]);

  async function runHarvest() {
    if (!file || loading) return;
    setLoading(true);
    setError("");
    setResult(null);
    setQualityHints([]);
    setOrchardApplied(false);

    try {
      const localQuality = await assessImageQuality(file);
      setQualityHints(localQuality.warnings || []);

      const prediction = await api.predictHarvestImage(file, {
        language,
        cultivar,
        intended_use: intendedUse,
        location,
        latitude: farmProfile?.latitude,
        longitude: farmProfile?.longitude,
        sample_date: sampleDate,
        tree_age: treeAge ? Number(treeAge) : undefined,
        irrigation_notes: irrigationNotes || undefined,
      });
      setResult(prediction);

      if (farmId) {
        const confidenceValue = confidenceToNumber(prediction.confidence, prediction.confidence_score);
        const lowConfidence = String(prediction.confidence || "").toLowerCase() === "low";
        const needsReview = lowConfidence || (prediction.image_analysis?.quality_warnings || []).length > 0;

        await api.createFarmScan(farmId, {
          module_type: "harvest_time",
          image_count: 1,
          preliminary: true,
          confidence: confidenceValue,
          status: needsReview ? "pending_review" : "new",
          summary: `${prediction.season_interpretation || prediction.harvest_status || "Harvest estimate"} - ${prediction.estimated_time_until_next_harvest_season || prediction.estimated_time_remaining || prediction.recommended_harvest_window || "--"}`,
          next_action: prediction.next_action || "Recheck in 7 days.",
          payload_json: {
            final_harvest_decision: prediction.final_harvest_decision || prediction.harvest_status,
            current_maturity_stage: prediction.current_maturity_stage,
            typical_harvest_season: prediction.typical_harvest_season,
            season_status: prediction.season_status,
            season_interpretation: prediction.season_interpretation,
            estimated_time_until_next_harvest_season: prediction.estimated_time_until_next_harvest_season,
            estimated_time_remaining: prediction.estimated_time_remaining,
            time_remaining: prediction.time_remaining,
            harvest_status: prediction.harvest_status,
            estimated_harvest_date: prediction.estimated_harvest_date,
            recommended_harvest_window: prediction.recommended_harvest_window,
            days_remaining: prediction.days_remaining,
            harvest_readiness_percent: prediction.harvest_readiness_percent,
            confidence: prediction.confidence,
            confidence_score: prediction.confidence_score,
            consistency: prediction.consistency,
            consistency_status: prediction.consistency_status,
            possible_reasons: prediction.possible_reasons || [],
            short_reason: prediction.short_reason,
            short_explanation: prediction.short_explanation,
            next_action: prediction.next_action,
            scene_analysis: prediction.scene_analysis || {},
            location,
            cultivar: prediction.cultivar || cultivar,
            intended_use: prediction.intended_use || intendedUse,
            sample_date: prediction.sample_date || sampleDate,
            weather_snapshot: prediction.weather_summary || {},
          },
        });
        if (typeof onScanSaved === "function") onScanSaved();
      }
    } catch (err) {
      setError(err.message || t("harvestTime.estimationFailed"));
    } finally {
      setLoading(false);
    }
  }

  function applyToOrchardSimulation() {
    if (!result || !onApplyOrchardUpdate) return;
    onApplyOrchardUpdate({
      fruit_stage: result.current_maturity_stage || result.image_analysis?.visual_stage || "green",
      harvest_readiness:
        result.harvest_readiness_percent != null
          ? Number(result.harvest_readiness_percent)
          : undefined,
      sample_date: result.sample_date || sampleDate,
      cultivar: result.cultivar || cultivar,
      source: "harvest_result",
      updated_at: new Date().toISOString(),
    });
    setOrchardApplied(true);
  }

  return (
    <section className="page-stack">
      <OliveGuideCard
        title={t("harvestTime.title")}
        message={t("harvestTime.guideMessage")}
        tip={t("harvestTime.guideTip")}
        chips={[t("harvestTime.onePhotoWorkflow"), t("harvestTime.weatherAware"), t("harvestTime.cultivarAware")]}
      />

      <article className="surface-card">
        <div className="section-row">
          <div>
            <h2>{t("harvestTime.estimatorTitle")}</h2>
            <p className="subtle">{t("harvestTime.estimatorDesc")}</p>
          </div>
          <span className="status-pill high"><ShieldCheck size={14} /> {t("harvestTime.evidenceFirst")}</span>
        </div>

        <DragDropUpload
          label={t("harvestTime.uploadOnePhoto")}
          hint={t("harvestTime.uploadHint")}
          multiple={false}
          onFilesSelected={(selected) => setFile((selected || [])[0] || null)}
        />

        <div className="inline-grid">
          <label>
            {t("harvestTime.sampleDate")}
            <input className="field" type="date" value={sampleDate} onChange={(event) => setSampleDate(event.target.value)} />
          </label>
          <label>
            {t("harvestTime.location")}
            <input className="field" value={location} onChange={(event) => setLocation(event.target.value)} placeholder={t("common.locationPlaceholder")} />
          </label>
          <label>
            {t("harvestTime.cultivar")}
            <select className="field" value={cultivar} onChange={(event) => setCultivar(event.target.value)}>
              <option value="Chemlali Sfax">Chemlali Sfax</option>
              <option value="Chetoui">Chetoui</option>
              <option value="Meski">Meski</option>
              <option value="Oueslati">Oueslati</option>
              <option value="Arbequina">Arbequina</option>
              <option value="Koroneiki">Koroneiki</option>
              <option value="Unknown">{t("common.unknownCultivar")}</option>
            </select>
          </label>
          <label>
            {t("harvestTime.intendedUse")}
            <select className="field" value={intendedUse} onChange={(event) => setIntendedUse(event.target.value)}>
              <option value="oil">{t("harvestTime.oliveOil")}</option>
              <option value="table_olives">{t("harvestTime.tableOlives")}</option>
            </select>
          </label>
          <label>
            {t("harvestTime.treeAge")} ({t("productionModel.optional")})
            <input className="field" value={treeAge} onChange={(event) => setTreeAge(event.target.value)} placeholder={t("harvestTime.treeAgePlaceholder")} />
          </label>
          <label className="full-width">
            {t("harvestTime.irrigationNotes")} ({t("productionModel.optional")})
            <input className="field" value={irrigationNotes} onChange={(event) => setIrrigationNotes(event.target.value)} placeholder={t("harvestTime.irrigationPlaceholder")} />
          </label>
        </div>

        {qualityHints.length ? (
          <div className="quality-list">
            <div className="hint-row">
              <strong>{t("harvestTime.imageQualityChecks")}</strong>
              <ul>
                {qualityHints.map((warning) => (
                  <li key={warning}>{warning}</li>
                ))}
              </ul>
            </div>
          </div>
        ) : null}

        <div className="inline-actions">
          <button className="primary-btn" onClick={runHarvest} disabled={loading || !file}>
            {loading ? t("common.loading") : t("harvestTime.estimateHarvestTime")}
          </button>
        </div>
        {error ? <p className="error-text">{error}</p> : null}
      </article>

      <HarvestResultCard
        result={
          result
            ? {
              ...result,
              final_harvest_decision: friendlyDecisionLabel(result, t),
              estimated_harvest_date: displayHarvestDate(result, t),
              recommended_harvest_window: displayHarvestWindow(result, t),
            }
            : null
        }
      />

      <article className="surface-card">
        <div className="section-row">
          <div>
            <h3><CalendarDays size={16} /> {t("harvestTime.harvestCalendarView")}</h3>
            <p className="subtle">{t("harvestTime.calendarDesc")}</p>
          </div>
          <span className="status-pill"><MapPin size={14} /> {location || t("farmSetup.region")}</span>
        </div>
        <div className="harvest-calendar-grid">
          {calendarItems.map((item) => (
            <div key={item.id} className={`harvest-calendar-card ${item.tone}`}>
              <p className="eyebrow">{item.label}</p>
              <h4>{item.date ? item.date.toLocaleDateString() : item.note}</h4>
              <p className="subtle">{item.note}</p>
            </div>
          ))}
        </div>
      </article>

      {result ? (
        <motion.article className="surface-card" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
          <div className="section-row">
            <div>
              <h3><CloudSun size={16} /> {t("harvestTime.harvestContext")}</h3>
              <p className="subtle">{t("harvestTime.harvestContextDesc")}</p>
            </div>
            <button className="primary-btn" onClick={applyToOrchardSimulation} disabled={orchardApplied}>
              {orchardApplied ? t("harvestTime.appliedToOrchard") : t("harvestTime.applyToOrchard")}
            </button>
          </div>
          <div className="stats-grid compact">
            <article className="stat-card"><p>{t("harvestTime.currentMaturityStage")}</p><h3>{friendlyMaturityStage(result.current_maturity_stage, t)}</h3></article>
            <article className="stat-card"><p>{t("harvestTime.typicalHarvestSeason")}</p><h3>{result.typical_harvest_season || "--"}</h3></article>
            <article className="stat-card"><p>{t("harvestTime.seasonInterpretation")}</p><h3>{friendlySeasonInterpretation(result, t)}</h3></article>
            <article className="stat-card"><p>{t("harvestTime.consistencyCheck")}</p><h3>{friendlyConsistency(result, t)}</h3></article>
            <article className="stat-card"><p>{t("harvestTime.cultivar")}</p><h3>{result.cultivar || cultivar}</h3><small>{result.cultivar_source || t("common.userSelected")}</small></article>
            <article className="stat-card"><p>{t("harvestTime.intendedUse")}</p><h3>{result.intended_use === "table_olives" ? t("harvestTime.tableOlives") : t("harvestTime.oliveOil")}</h3></article>
          </div>
          <div className="seasonal-grid">
            <div className="seasonal-card"><p className="eyebrow">{t("harvestTime.temperatureAvg")}</p><h4>{result.weather_summary?.temperature_avg ?? "--"}<span aria-hidden="true">&deg;C</span></h4><p className="subtle">{t("dashboard.recentDays")}</p></div>
            <div className="seasonal-card"><p className="eyebrow">{t("dashboard.rainfall")}</p><h4>{result.weather_summary?.rainfall_total ?? "--"} mm</h4><p className="subtle">{t("dashboard.recentDays")}</p></div>
            <div className="seasonal-card"><p className="eyebrow">{t("dashboard.humidity")}</p><h4>{result.weather_summary?.humidity_avg ?? "--"}%</h4><p className="subtle">{t("dashboard.recentDays")}</p></div>
            <div className="seasonal-card"><p className="eyebrow">{t("harvestTime.forecast")}</p><h4>{result.weather_summary?.forecast_available ? t("common.available") : t("common.notAvailable")}</h4><p className="subtle">{t("harvestTime.weatherReliability")}</p></div>
          </div>
          <p className="subtle">{defaultsLabel}</p>
          {Array.isArray(result.possible_reasons) && result.possible_reasons.length ? (
            <p className="subtle">{t("harvestTime.possibleReasons")}: {result.possible_reasons.map((reason) => friendlyHarvestNote(reason, t)).join(" ")}</p>
          ) : null}
          {!isInconsistency && result.season_warning ? <p className="error-text">{friendlyHarvestNote(result.season_warning, t)}</p> : null}
        </motion.article>
      ) : null}

      {result ? (
        <article className="surface-card">
          <div className="section-row">
            <h3>{t("harvestTime.whyEstimate")}</h3>
            <button className="ghost-btn" onClick={() => setShowWhy((open) => !open)}>
              {showWhy ? t("harvestTime.hideDetails") : t("harvestTime.showDetails")}
            </button>
          </div>
          {showWhy ? (
            <div className="list-stack">
              <div className="list-row">
                <div>
                  <strong>{t("harvestTime.sceneAnalysis")}</strong>
                  <p>{result.scene_analysis?.note || t("harvestTime.noSceneNote")}</p>
                </div>
                <span className="status-pill">{friendlyConfidence(result.scene_analysis?.reliability, t)}</span>
              </div>
              <div className="list-row">
                <div>
                  <strong>{t("harvestTime.imageAnalysis")}</strong>
                  <p>{t("harvestTime.stage")}: {friendlyMaturityStage(result.image_analysis?.visual_stage, t)} <span aria-hidden="true">&middot;</span> {t("harvestTime.uniformity")}: {friendlyConfidence(result.image_analysis?.sample_uniformity, t)}</p>
                </div>
                <span className="status-pill">{result.image_analysis?.detected_olives ?? 0} {t("harvestTime.olives")}</span>
              </div>
              <div className="list-row">
                <div>
                  <strong>{t("harvestTime.climateAnalysis")}</strong>
                  <p>{t("harvestTime.temperatureShort")} {result.climate_analysis?.temperature_avg ?? "--"}<span aria-hidden="true">&deg;C</span> <span aria-hidden="true">&middot;</span> {t("harvestTime.rainShort")} {result.climate_analysis?.rainfall_total ?? "--"} mm</p>
                </div>
                <span className="status-pill">{result.climate_analysis?.weather_available ? t("harvestTime.weatherUsed") : t("harvestTime.weatherFallback")}</span>
              </div>
              <div className="list-row">
                <div>
                  <strong>{t("harvestTime.finalDecision")}</strong>
                  <p>{friendlyHarvestNote(result.final_ai_decision?.short_reason || result.final_ai_decision?.short_explanation || result.short_reason || result.short_explanation, t)}</p>
                </div>
                <span className="status-pill">{friendlyConfidence(result.final_ai_decision?.confidence || result.confidence, t)}</span>
              </div>
            </div>
          ) : null}
        </article>
      ) : null}
    </section>
  );
}
