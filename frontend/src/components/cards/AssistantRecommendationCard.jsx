import { useTranslation } from "react-i18next";

function translateStoredText(value, t) {
  let text = String(value || "").trim();
  if (!text) return "";
  const replacements = [
    [/Dans la fen[eê]tre active de r[eé]colte/gi, t("harvestTime.inActiveHarvestWindow")],
    [/Hors fen[eê]tre active de r[eé]colte/gi, t("harvestTime.notInActiveHarvestWindow")],
    [/Approaching harvest/gi, t("harvestTime.approachingHarvest")],
    [/Harvest now/gi, t("harvestTime.harvestNow")],
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

function deriveMessage(alerts = [], scans = [], t) {
  const activeAlert = alerts.find((alert) => String(alert.level || "").toLowerCase() === "high");
  if (activeAlert) {
    return `${t("assistant.highPriorityAlert")}: ${translateStoredText(activeAlert.title, t) || t("assistant.checkFarmAlertsNow")}`;
  }
  const recent = scans[0];
  if (recent) {
    return `${t("dashboard.lastScan")}: ${translateStoredText(recent.summary, t) || recent.module_type || t("assistant.reviewLatestScan")}`;
  }
  return t("assistant.noScansMessage");
}

export default function AssistantRecommendationCard({ alerts, scans, onNavigate }) {
  const { t } = useTranslation();
  const message = deriveMessage(alerts, scans, t);
  return (
    <article className="assistant-recommendation">
      <p className="eyebrow">{t("assistant.title")}</p>
      <h3>{t("assistant.nextAction")}</h3>
      <p className="subtle">{message}</p>
      <div className="assistant-actions">
        <button className="secondary-btn" onClick={() => onNavigate("harvest-time")}>
          {t("assistant.checkHarvest")}
        </button>
        <button className="ghost-btn" onClick={() => onNavigate("disease-scan")}>
          {t("nav.diseaseScan")}
        </button>
      </div>
    </article>
  );
}
