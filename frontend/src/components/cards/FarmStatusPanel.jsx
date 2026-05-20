import { formatMetaLine, formatTemperature, sanitizeText } from "../../lib/textFormat";
import { useTranslation } from "react-i18next";

export default function FarmStatusPanel({ farm, widgets, weather }) {
  const { t } = useTranslation();
  const varieties = Array.isArray(widgets?.varieties) ? widgets.varieties.join(", ") : "--";
  const harvest = widgets?.harvest_readiness != null ? `${widgets.harvest_readiness}%` : "--";
  const metaLine = formatMetaLine([
    farm?.region || "--",
    farm?.country || "--",
    `${t("common.cultivar")}: ${varieties}`,
  ]);

  return (
    <article className="farm-status-panel">
      <div>
        <p className="eyebrow">{t("dashboard.activeFarm")}</p>
        <h2>{farm?.farm_name || t("farmSetup.title")}</h2>
        <p className="subtle">{sanitizeText(metaLine)}</p>
      </div>
      <div className="farm-status-grid">
        <div>
          <small>{t("dashboard.harvestReadiness")}</small>
          <strong>{harvest}</strong>
        </div>
        <div>
          <small>{t("dashboard.diseaseAlert")}</small>
          <strong>{widgets?.disease_alerts ?? 0}</strong>
        </div>
        <div>
          <small>{t("dashboard.lastScan")}</small>
          <strong>{widgets?.last_scan_summary || "--"}</strong>
        </div>
        <div>
          <small>{t("dashboard.weather")}</small>
          <strong>{weather ? formatTemperature(weather.temperature_avg) : "--"}</strong>
        </div>
      </div>
    </article>
  );
}
