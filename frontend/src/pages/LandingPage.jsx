import LivingOrchardView from "../components/orchard/LivingOrchardView";
import { useTranslation } from "react-i18next";

export default function LandingPage({ onSignIn, onCreateAccount }) {
  const { t } = useTranslation();
  const previewScene = {
    tree_age_group: "mature",
    season: "spring",
    time_of_day: "evening",
    weather_type: "sunny",
    fruit_stage: "green",
    fruit_state: "green",
    harvest_readiness: 56,
    disease_alert_level: "low",
    cultivar: "Chemlali",
    location: "Sfax",
  };
  const benefits = [
    {
      title: t("landing.benefitHarvestTitle"),
      body: t("landing.benefitHarvest"),
    },
    {
      title: t("landing.benefitDiseaseTitle"),
      body: t("landing.benefitDisease"),
    },
    {
      title: t("landing.benefitProductionTitle"),
      body: t("landing.benefitProduction"),
    },
    {
      title: t("landing.benefitAssistantTitle"),
      body: t("landing.benefitAssistant"),
    },
  ];
  const howItWorks = [
    {
      step: "1",
      title: t("landing.step1Title"),
      body: t("landing.step1Body"),
    },
    {
      step: "2",
      title: t("landing.step2Title"),
      body: t("landing.step2Body"),
    },
    {
      step: "3",
      title: t("landing.step3Title"),
      body: t("landing.step3Body"),
    },
  ];

  return (
    <main className="marketing-page">
      <section className="marketing-hero surface-card">
        <div className="marketing-copy">
          <p className="eyebrow">{t("landing.eyebrow")}</p>
          <h1>{t("landing.title")}</h1>
          <p>{t("landing.body")}</p>
          <div className="marketing-actions">
            <button className="primary-btn" onClick={onSignIn}>{t("nav.signIn")}</button>
            <button className="secondary-btn" onClick={onCreateAccount}>{t("nav.createAccount")}</button>
          </div>
          <div className="hero-stats">
            <div>
              <strong>{t("nav.harvestTime")}</strong>
              <span>{t("landing.heroHarvestStat")}</span>
            </div>
            <div>
              <strong>{t("nav.diseaseScan")}</strong>
              <span>{t("landing.heroDiseaseStat")}</span>
            </div>
            <div>
              <strong>{t("nav.productionModel")}</strong>
              <span>{t("landing.heroProductionStat")}</span>
            </div>
          </div>
        </div>
        <div className="marketing-preview">
          <LivingOrchardView sceneState={previewScene} title={t("dashboard.livingOrchardPreview")} compact />
        </div>
      </section>

      <section className="marketing-section">
        <div className="section-head">
          <p className="eyebrow">{t("landing.benefitsEyebrow")}</p>
          <h2>{t("landing.benefitsTitle")}</h2>
        </div>
        <div className="benefit-grid">
          {benefits.map((item) => (
            <article key={item.title} className="benefit-card">
              <h3>{item.title}</h3>
              <p>{item.body}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="marketing-section feature-showcase">
        <div className="section-head">
          <p className="eyebrow">{t("landing.showcaseEyebrow")}</p>
          <h2>{t("landing.showcaseTitle")}</h2>
        </div>
        <div className="showcase-grid">
          <article className="showcase-card">
            <h3>{t("landing.showcaseDashboardTitle")}</h3>
            <p>{t("landing.showcaseDashboardBody")}</p>
          </article>
          <article className="showcase-card">
            <h3>{t("landing.showcaseOrchardTitle")}</h3>
            <p>{t("landing.showcaseOrchardBody")}</p>
          </article>
          <article className="showcase-card">
            <h3>{t("landing.showcaseWeatherTitle")}</h3>
            <p>{t("landing.showcaseWeatherBody")}</p>
          </article>
        </div>
      </section>

      <section className="marketing-section how-it-works">
        <div className="section-head">
          <p className="eyebrow">{t("landing.howItWorksEyebrow")}</p>
          <h2>{t("landing.howItWorksTitle")}</h2>
        </div>
        <div className="steps-grid">
          {howItWorks.map((item) => (
            <article key={item.step} className="step-card">
              <span className="step-index">{item.step}</span>
              <h3>{item.title}</h3>
              <p>{item.body}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="marketing-section trust-section">
        <div>
          <p className="eyebrow">{t("landing.trustEyebrow")}</p>
          <h2>{t("landing.trustTitle")}</h2>
          <p>{t("landing.trustBody")}</p>
        </div>
        <div className="trust-actions">
          <button className="primary-btn" onClick={onCreateAccount}>{t("landing.startNow")}</button>
          <button className="ghost-btn" onClick={onSignIn}>{t("landing.alreadyHaveAccount")}</button>
        </div>
      </section>

      <footer className="marketing-footer">
        <p>{t("auth.brand")} <span aria-hidden="true">&middot;</span> {t("landing.footerTagline")}</p>
        <p>{t("nav.harvestTime")} <span aria-hidden="true">&middot;</span> {t("nav.diseaseScan")} <span aria-hidden="true">&middot;</span> {t("nav.productionModel")} <span aria-hidden="true">&middot;</span> {t("nav.assistant")}</p>
      </footer>
    </main>
  );
}
