import { Home, Languages, LogIn, UserPlus } from "lucide-react";
import { useTranslation } from "react-i18next";

const NAV_ITEMS = [
  { id: "landing", labelKey: "nav.home", icon: Home },
  { id: "signin", labelKey: "nav.signIn", icon: LogIn },
  { id: "signup", labelKey: "nav.createAccount", icon: UserPlus },
];

export default function PublicHeader({ activeView, onNavigate }) {
  const { t, i18n } = useTranslation();
  const languages = [
  { code: "fr", label: "Francais", flag: "\uD83C\uDDEB\uD83C\uDDF7" },
  { code: "en", label: "English", flag: "\uD83C\uDDEC\uD83C\uDDE7" },
  { code: "ar", label: "Arabic", flag: "\uD83C\uDDF9\uD83C\uDDF3" },
];

  function changeLanguage(code) {
    i18n.changeLanguage(code);
    document.documentElement.dir = code === "ar" ? "rtl" : "ltr";
    document.documentElement.lang = code;
  }

  return (
    <header className="public-header" role="banner">
      <button className="public-brand" onClick={() => onNavigate("landing")}>
        <img src="/branding/name-tight.png?v=6" alt={t("auth.brand")} className="brand-wordmark-img" />
      </button>

      <nav className="public-nav" aria-label={t("nav.home")}>
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          return (
            <button
              key={item.id}
              className={`public-nav-button ${activeView === item.id ? "active" : ""}`}
              onClick={() => onNavigate(item.id)}
            >
              <Icon size={14} aria-hidden="true" />
              <span>{t(item.labelKey)}</span>
            </button>
          );
        })}
      </nav>

      <label className="language-pill" title={t("common.languageSelector")}>
        <Languages size={15} aria-hidden="true" />
        <select
          className="language-select"
          value={i18n.resolvedLanguage || i18n.language || "fr"}
          onChange={(event) => changeLanguage(event.target.value)}
          aria-label={t("common.language")}
        >
          {languages.map((entry) => (
            <option key={entry.code} value={entry.code}>
              {`${entry.flag} ${entry.label}`}
            </option>
          ))}
        </select>
      </label>
    </header>
  );
}
