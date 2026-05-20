import OliveGuideVisual from "./OliveGuideVisual";
import { useTranslation } from "react-i18next";

export default function OliveGuideHero({
  eyebrow,
  title,
  body,
  actions,
  message,
  mood = "healthy",
  season = "mid",
}) {
  const { t } = useTranslation();

  return (
    <section className="guide-hero">
      <div className="guide-hero-copy">
        <p className="eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
        <p className="hero-body">{body}</p>
        <div className="hero-actions">{actions}</div>
        <div className="guide-message">
          <span className="guide-badge">{t("assistant.guide")}</span>
          <p>{message}</p>
        </div>
      </div>
      <div className="guide-hero-visual">
        <OliveGuideVisual mood={mood} season={season} />
      </div>
    </section>
  );
}
