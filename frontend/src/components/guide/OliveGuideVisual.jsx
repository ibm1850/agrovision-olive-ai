import { useTranslation } from "react-i18next";

export default function OliveGuideVisual({ mood = "healthy", season = "mid" }) {
  const { t } = useTranslation();

  return (
    <div className={`olive-guide-visual mood-${mood} season-${season}`}>
      <div className="guide-orbit" />
      <svg viewBox="0 0 360 360" role="img" aria-label={t("dashboard.livingOrchard")}>
        <defs>
          <linearGradient id="trunk" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="#8b6a47" />
            <stop offset="100%" stopColor="#5a4632" />
          </linearGradient>
          <radialGradient id="leafGlow" cx="50%" cy="40%" r="70%">
            <stop offset="0%" stopColor="#d7f0c3" stopOpacity="0.95" />
            <stop offset="65%" stopColor="#87b774" stopOpacity="0.55" />
            <stop offset="100%" stopColor="#4f7a4b" stopOpacity="0.25" />
          </radialGradient>
          <linearGradient id="leafDark" x1="0" x2="1" y1="0" y2="1">
            <stop offset="0%" stopColor="#3b5f3a" />
            <stop offset="100%" stopColor="#2e4b30" />
          </linearGradient>
        </defs>
        <rect width="360" height="360" rx="40" fill="url(#leafGlow)" />
        <g className="tree-body">
          <path
            d="M176 268c-8-46-8-96 4-138 9-32 27-62 48-82 18-17 38-26 59-28-12 20-17 41-16 62 2 28 18 54 38 76 20 22 42 39 60 59-60 12-107 12-149-5-39-16-72-45-92-85z"
            fill="url(#leafDark)"
            opacity="0.88"
          />
          <path
            d="M172 248c-8-38-9-80 3-116 8-26 24-52 41-68 15-14 32-22 50-24-11 17-16 34-15 51 2 24 14 45 30 63 15 17 31 30 44 46-45 9-79 9-109-4-28-11-51-32-64-58z"
            fill="#4f7e49"
          />
          <path d="M170 286c-3 18-5 34-6 50h30c-1-18-4-35-10-50-4-11-8-18-14-24z" fill="url(#trunk)" />
        </g>
        <g className="tree-olives">
          <circle cx="228" cy="162" r="12" />
          <circle cx="252" cy="190" r="9" />
          <circle cx="210" cy="130" r="7.5" />
          <circle cx="198" cy="206" r="9.5" />
          <circle cx="272" cy="166" r="6.5" />
        </g>
        <g className="tree-accents">
          <path d="M60 260c20-8 42-10 65-6" stroke="#2f7c2d" strokeOpacity="0.25" strokeWidth="4" fill="none" />
          <path d="M76 288c24-6 48-6 72 0" stroke="#2f7c2d" strokeOpacity="0.18" strokeWidth="4" fill="none" />
        </g>
      </svg>
      <div className="olive-guide-caption">
        <span className="guide-dot" />
        <p>{t("dashboard.livingOrchard")}</p>
      </div>
    </div>
  );
}
