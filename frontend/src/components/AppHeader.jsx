import { Bell, ChevronDown, Languages, Leaf } from "lucide-react";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

const NAV_ITEMS = [
  { id: "dashboard", labelKey: "nav.dashboard" },
  { id: "harvest-time", labelKey: "nav.harvestTime" },
  { id: "disease-scan", labelKey: "nav.diseaseScan" },
  { id: "production-model", labelKey: "nav.productionModel" },
  { id: "assistant", labelKey: "nav.assistant" },
  { id: "setup", labelKey: "nav.farmSetup" },
];

const LANGUAGES = [
  { code: "fr", label: "Francais", flag: "\uD83C\uDDEB\uD83C\uDDF7" },
  { code: "en", label: "English", flag: "\uD83C\uDDEC\uD83C\uDDE7" },
  { code: "ar", label: "Arabic", flag: "\uD83C\uDDF9\uD83C\uDDF3" },
];

export default function AppHeader({
  activePage,
  onNavigate,
  user,
  onSignOut,
}) {
  const { t, i18n } = useTranslation();
  const [open, setOpen] = useState(false);
  const currentLanguage = i18n.resolvedLanguage || i18n.language || "fr";
  const initials = useMemo(() => {
    const base = String(user?.name || user?.email || "U")
      .split(/\s+/)
      .map((part) => part[0])
      .join("")
      .slice(0, 2)
      .toUpperCase();
    return base || "U";
  }, [user]);

  function changeLanguage(code) {
    i18n.changeLanguage(code);
    document.documentElement.dir = code === "ar" ? "rtl" : "ltr";
    document.documentElement.lang = code;
  }

  return (
    <header className="app-header" role="banner">
      <button className="brand" onClick={() => onNavigate("dashboard")}>
        <span className="brand-icon" aria-hidden="true">
          <Leaf size={16} />
        </span>
        <img src="/branding/name-tight.png?v=6" alt={t("auth.brand")} className="brand-wordmark-img" />
      </button>

      <nav className="top-nav" aria-label={t("nav.dashboard")}>
        {NAV_ITEMS.map((item) => (
          <button
            key={item.id}
            className={`nav-button ${activePage === item.id ? "active" : ""}`}
            onClick={() => onNavigate(item.id)}
          >
            {t(item.labelKey)}
          </button>
        ))}
      </nav>

      <div className="header-actions">
        <label className="language-pill" title={t("common.languageSelector")}>
          <Languages size={15} aria-hidden="true" />
          <select
            className="language-select"
            value={currentLanguage}
            onChange={(event) => changeLanguage(event.target.value)}
            aria-label={t("common.language")}
          >
            {LANGUAGES.map((entry) => (
              <option key={entry.code} value={entry.code}>
                {`${entry.flag} ${entry.label}`}
              </option>
            ))}
          </select>
        </label>

        <button className="icon-button" type="button" aria-label={t("common.notifications")}>
          <Bell size={16} />
          <span className="icon-dot" />
        </button>

        <div className="avatar-menu">
          <button
            className="avatar-trigger"
            type="button"
            onClick={() => setOpen((prev) => !prev)}
            aria-expanded={open}
            aria-haspopup="menu"
          >
            <span className="avatar-circle">{initials}</span>
            <span className="avatar-text" title={user?.email || ""}>
              {user?.name || user?.email || t("common.user")}
            </span>
            <ChevronDown size={14} />
          </button>
          {open ? (
            <div className="avatar-dropdown" role="menu">
              <button type="button" className="dropdown-item" onClick={() => onNavigate("setup")}>
                {t("nav.profileSettings")}
              </button>
              <button type="button" className="dropdown-item" onClick={onSignOut}>
                {t("nav.signOut")}
              </button>
            </div>
          ) : null}
        </div>
      </div>
    </header>
  );
}
