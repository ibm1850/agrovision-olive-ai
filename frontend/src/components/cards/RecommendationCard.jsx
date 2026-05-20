import { useTranslation } from "react-i18next";

export default function RecommendationCard({ title, body, status }) {
  const { t } = useTranslation();
  return (
    <article className={`recommendation-card ${status || ""}`}>
      <p className="eyebrow">{t("diseaseScan.recommendation")}</p>
      <h4>{title}</h4>
      <p className="subtle">{body}</p>
    </article>
  );
}
