import { useTranslation } from "react-i18next";

function InfoRow({ label, value }) {
  return (
    <div className="info-row">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

export default function DiseaseResultCard({ aggregate, action, treatment }) {
  const { t } = useTranslation();

  if (!aggregate) {
    return (
      <article className="result-card">
        <h3>{t("diseaseScan.result")}</h3>
        <p className="subtle">{t("diseaseScan.noScansYet")}</p>
      </article>
    );
  }

  const diseaseKey = String(aggregate.disease || "").toLowerCase().replace(/\s+/g, "_");
  const diseaseLabel = t(`diseaseScan.${diseaseKey}`, { defaultValue: aggregate.disease || t("common.unknown") });
  const confidenceLabel = aggregate.confidenceLabel || t("dashboard.needsReview");
  const affectedPartKey = String(aggregate.affected_part || aggregate.affected_part_key || "unknown")
    .toLowerCase()
    .replace(/\s+/g, "_");
  const affectedPartLabel = t(`plantParts.${affectedPartKey}`, {
    defaultValue: aggregate.affected_part || t("plantParts.unknown"),
  });

  return (
    <article className="result-card">
      <div className="result-header">
        <h3>{diseaseLabel}</h3>
        <span className={`status-pill ${aggregate.confidenceLabel || "needs-review"}`}>
          {confidenceLabel}
        </span>
      </div>
      <div className="result-grid">
        <InfoRow label={t("diseaseScan.severity")} value={aggregate.severity || "--"} />
        <InfoRow
          label={t("diseaseScan.confidence")}
          value={`${Math.round(Number(aggregate.confidence || 0) * 100)}%`}
        />
        <InfoRow label={t("diseaseScan.affectedPart")} value={affectedPartLabel} />
      </div>
      <p className="subtle">{t("diseaseScan.immediateAction")}: {action}</p>
      <p className="subtle">{t("diseaseScan.treatmentGuidance")}: {treatment}</p>
    </article>
  );
}
