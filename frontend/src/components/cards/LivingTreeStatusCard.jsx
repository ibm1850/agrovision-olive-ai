import OliveGuideVisual from "../guide/OliveGuideVisual";
import { useTranslation } from "react-i18next";

export default function LivingTreeStatusCard({
  statusTitle,
  statusBody,
  mood = "healthy",
  season = "mid",
  meta,
}) {
  const { t } = useTranslation();

  return (
    <article className="living-tree-card">
      <div className="living-tree-copy">
        <p className="eyebrow">{t("dashboard.livingOrchard")}</p>
        <h3>{statusTitle}</h3>
        <p className="subtle">{statusBody}</p>
        {meta ? <p className="guide-meta">{meta}</p> : null}
      </div>
      <div className="living-tree-visual">
        <OliveGuideVisual mood={mood} season={season} />
      </div>
    </article>
  );
}
