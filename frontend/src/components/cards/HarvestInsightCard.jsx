import { useTranslation } from "react-i18next";

function translateHarvestDecision(value, t) {
  let text = String(value || "").trim();
  if (!text) return "";
  const replacements = [
    [/Dans la fen[eê]tre active de r[eé]colte/gi, t("harvestTime.inActiveHarvestWindow")],
    [/Hors fen[eê]tre active de r[eé]colte/gi, t("harvestTime.notInActiveHarvestWindow")],
    [/Approaching harvest/gi, t("harvestTime.approachingHarvest")],
    [/Harvest now/gi, t("harvestTime.harvestNow")],
    [/Too early/gi, t("harvestTime.tooEarly")],
    [/Not ready yet/gi, t("harvestTime.notReadyYet")],
    [/Maintenant|Now/gi, t("common.now", { defaultValue: t("common.today") })],
  ];
  for (const [pattern, replacement] of replacements) text = text.replace(pattern, replacement);
  return text;
}

export default function HarvestInsightCard({ widgets, sceneState }) {
  const { t } = useTranslation();
  const readiness = widgets?.harvest_readiness ?? sceneState?.harvest_readiness ?? "--";
  const window = widgets?.last_harvest_window || "--";
  const rawStage = String(sceneState?.fruit_stage || "--");
  const stageMap = {
    green: "green",
    yellow_green: "yellowGreen",
    "yellow-green": "yellowGreen",
    start_of_color_change: "startOfColorChange",
    mature: "mature",
  };
  const stageKey = stageMap[String(sceneState?.fruit_stage || "").toLowerCase()] || "";
  const stage = stageKey
    ? t(`harvestTime.${stageKey}`)
    : rawStage.replaceAll("_", " ");
  const decision = translateHarvestDecision(widgets?.last_harvest_prediction, t) || t("harvestTime.noRecentEstimate");
  return (
    <article className="insight-card">
      <p className="eyebrow">{t("dashboard.harvestReadiness")}</p>
      <h3>{t("dashboard.readiness")} {readiness}%</h3>
      <p className="subtle">{t("harvestTime.currentMaturityStage")}: {stage}</p>
      <div className="insight-row">
        <span>{t("common.window")}</span>
        <strong>{window}</strong>
      </div>
      <p className="insight-note">{decision}</p>
    </article>
  );
}
