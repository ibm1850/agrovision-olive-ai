import { useTranslation } from "react-i18next";

function InfoRow({ label, value }) {
  return (
    <div className="info-row">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function normalizeText(value) {
  return String(value || "")
    .trim()
    .toLowerCase()
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ");
}

function translateHarvestStatus(value, t) {
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
  return value;
}

function translateConfidence(value, t) {
  const raw = normalizeText(value);
  if (raw.includes("high") || raw.includes("élev") || raw.includes("عالية")) return t("diseaseScan.highConfidence");
  if (raw.includes("low") || raw.includes("faible") || raw.includes("منخفض")) return t("diseaseScan.lowConfidence");
  if (raw.includes("medium") || raw.includes("moy") || raw.includes("متوسط")) return t("diseaseScan.mediumConfidence");
  return value || t("diseaseScan.mediumConfidence");
}

function translateMaturityStage(value, t) {
  const raw = normalizeText(value);
  if (!raw) return "--";
  if (raw.includes("yellow")) return t("harvestTime.yellowGreen");
  if (raw.includes("color")) return t("harvestTime.startOfColorChange");
  if (raw.includes("mature")) return t("harvestTime.mature");
  if (raw.includes("green")) return t("harvestTime.green");
  return value;
}

function translateReason(value, t) {
  const raw = normalizeText(value);
  if (!raw) return "";
  if (raw.includes("recheck") && raw.includes("3") && raw.includes("5")) {
    return t("harvestTime.monitorColorChange");
  }
  if (raw.includes("not in active harvest window")) return t("harvestTime.notInActiveHarvestWindow");
  if (raw.includes("in active harvest window")) return t("harvestTime.inActiveHarvestWindow");
  if (raw.includes("verify sample date")) return t("harvestTime.dataInconsistency");
  if (raw.includes("image quality")) return t("harvestTime.qualityWarning");
  return value;
}

export default function HarvestResultCard({ result }) {
  const { t } = useTranslation();

  if (!result) {
    return (
      <article className="result-card">
        <h3>{t("common.result")}</h3>
        <p className="subtle">{t("harvestTime.noEstimateYet")}</p>
      </article>
    );
  }

  return (
    <article className="result-card">
      <div className="result-header">
        <h3>{translateHarvestStatus(result.final_harvest_decision || result.harvest_status, t)}</h3>
        <span className={`status-pill ${String(result.confidence || "").toLowerCase()}`}>
          {translateConfidence(result.confidence, t)}
        </span>
      </div>
      <p className="subtle">{translateReason(result.short_reason || result.short_explanation || result.next_action, t)}</p>
      <div className="result-grid">
        <InfoRow label={t("harvestTime.estimatedHarvestDate")} value={result.estimated_harvest_date || "--"} />
        <InfoRow label={t("harvestTime.recommendedWindow")} value={result.recommended_harvest_window || "--"} />
        <InfoRow label={t("harvestTime.timeRemaining")} value={result.estimated_time_remaining || result.time_remaining || "--"} />
        <InfoRow label={t("harvestTime.currentMaturityStage")} value={translateMaturityStage(result.current_maturity_stage, t)} />
      </div>
    </article>
  );
}
