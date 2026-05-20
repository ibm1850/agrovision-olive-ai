import { useTranslation } from "react-i18next";

export default function OliveGuideCard({ title, message, tip, mood = "healthy", chips = [] }) {
  const { t } = useTranslation();
  void mood;
  return (
    <article className="guide-card">
      <div className="guide-card-copy">
        <p className="eyebrow">{title}</p>
        <h3>{message}</h3>
        {tip ? <p className="subtle">{tip}</p> : null}
        {chips.length ? (
          <div className="guide-chips">
            {chips.map((chip) => (
              <span key={chip} className="guide-chip">
                {chip}
              </span>
            ))}
          </div>
        ) : null}
        <div className="guide-insight">
          <strong>{t("diseaseScan.orchardInsight")}</strong>
          <p>{t("diseaseScan.orchardInsightDesc")}</p>
        </div>
      </div>
    </article>
  );
}
