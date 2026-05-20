import { useEffect, useMemo, useState } from "react";
import "leaflet/dist/leaflet.css";
import { Camera, CalendarCheck2 } from "lucide-react";
import { useTranslation } from "react-i18next";
import AppHeader from "./components/AppHeader";
import FarmSelectorCard from "./components/FarmSelectorCard";
import PublicHeader from "./components/PublicHeader";
import { api } from "./lib/api";
import AssistantPage from "./pages/AssistantPage";
import DashboardPage from "./pages/DashboardPage";
import DiseaseScanPage from "./pages/DiseaseScanPage";
import FarmSetupPage from "./pages/FarmSetupPage";
import HarvestTimePage from "./pages/HarvestTimePage";
import LandingPage from "./pages/LandingPage";
import OliveDetectPage from "./pages/OliveDetectPage";
import ProductionModelPage from "./pages/ProductionModelPage";
import SignInPage from "./pages/SignInPage";
import SignUpPage from "./pages/SignUpPage";
import VerifyEmailPage from "./pages/VerifyEmailPage";

const STORAGE_KEY = "harvest-time-selected-farm";
const ORCHARD_OVERRIDE_STORAGE_KEY = "harvest-time-orchard-overrides";
const AUTH_SESSION_KEY = "agrovision-auth-session";

function loadAuthSession() {
  try {
    const raw = window.localStorage.getItem(AUTH_SESSION_KEY);
    if (!raw) return { authenticated: false, email: "", name: "" };
    const parsed = JSON.parse(raw);
    if (!parsed || !parsed.authenticated) return { authenticated: false, email: "", name: "" };
    return {
      authenticated: true,
      email: String(parsed.email || ""),
      name: String(parsed.name || ""),
    };
  } catch {
    return { authenticated: false, email: "", name: "" };
  }
}

function saveAuthSession(session) {
  try {
    window.localStorage.setItem(AUTH_SESSION_KEY, JSON.stringify(session));
  } catch {
    // ignore storage errors
  }
}

function clearAuthSession() {
  try {
    window.localStorage.removeItem(AUTH_SESSION_KEY);
  } catch {
    // ignore storage errors
  }
}

function generateVerificationCode() {
  return String(Math.floor(100000 + Math.random() * 900000));
}

export default function App() {
  const { t, i18n } = useTranslation();
  const language = i18n.resolvedLanguage || i18n.language || "fr";

  const [authSession, setAuthSession] = useState(() => loadAuthSession());
  const [publicView, setPublicView] = useState("landing");
  const [pendingVerification, setPendingVerification] = useState(null);

  const [activePage, setActivePage] = useState("dashboard");
  const [farmProfiles, setFarmProfiles] = useState([]);
  const [selectedFarmId, setSelectedFarmId] = useState(null);
  const [dashboard, setDashboard] = useState(null);
  const [weather, setWeather] = useState(null);
  const [loadingDashboard, setLoadingDashboard] = useState(false);
  const [error, setError] = useState("");
  const [orchardOverrides, setOrchardOverrides] = useState({});

  const selectedFarm = useMemo(
    () => farmProfiles.find((farm) => Number(farm.id) === Number(selectedFarmId)) || null,
    [farmProfiles, selectedFarmId],
  );

  useEffect(() => {
    document.documentElement.lang = language;
    document.documentElement.dir = language === "ar" ? "rtl" : "ltr";
  }, [language]);

  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(ORCHARD_OVERRIDE_STORAGE_KEY);
      if (!raw) return;
      const parsed = JSON.parse(raw);
      if (parsed && typeof parsed === "object") {
        setOrchardOverrides(parsed);
      }
    } catch {
      // keep defaults if storage is invalid
    }
  }, []);

  useEffect(() => {
    if (!authSession.authenticated) {
      setFarmProfiles([]);
      setSelectedFarmId(null);
      setDashboard(null);
      setWeather(null);
      setError("");
      return;
    }
    loadFarms();
  }, [authSession.authenticated]);

  useEffect(() => {
    if (!authSession.authenticated || !selectedFarmId) return;
    window.localStorage.setItem(STORAGE_KEY, String(selectedFarmId));
    reloadFarmDashboard(selectedFarmId);
  }, [authSession.authenticated, selectedFarmId]);

  useEffect(() => {
    try {
      window.localStorage.setItem(ORCHARD_OVERRIDE_STORAGE_KEY, JSON.stringify(orchardOverrides));
    } catch {
      // ignore storage write errors
    }
  }, [orchardOverrides]);

  async function loadFarms() {
    try {
      const farms = await api.getFarmProfiles();
      setFarmProfiles(farms || []);
      if (!farms.length) {
        setSelectedFarmId(null);
        setDashboard(null);
        setActivePage("setup");
        return;
      }
      const persisted = window.localStorage.getItem(STORAGE_KEY);
      const fallback = farms[0]?.id;
      const targetId = farms.some((farm) => String(farm.id) === persisted) ? Number(persisted) : fallback;
      setSelectedFarmId(targetId);
      setActivePage("dashboard");
    } catch (err) {
      setError(err.message || t("common.unableToLoadFarms"));
      setActivePage("dashboard");
    }
  }

  async function reloadFarmDashboard(farmId = selectedFarmId) {
    if (!farmId) return;
    setLoadingDashboard(true);
    setError("");
    try {
      const payload = await api.getFarmDashboard(farmId);
      setDashboard(payload);
      if (payload?.farm?.latitude != null && payload?.farm?.longitude != null) {
        const weatherData = await api.getWeatherInsights(payload.farm.latitude, payload.farm.longitude);
        setWeather(weatherData);
      } else {
        setWeather(null);
      }
    } catch (err) {
      setError(err.message || t("common.unableToLoadDashboard"));
    } finally {
      setLoadingDashboard(false);
    }
  }

  async function handleFarmSaved(profile) {
    await loadFarms();
    setSelectedFarmId(profile.id);
    setActivePage("dashboard");
  }

  function navigate(pageId) {
    if (!selectedFarm && pageId !== "setup") {
      setActivePage("setup");
      return;
    }
    setActivePage(pageId);
  }

  function applyOrchardSimulationUpdate(payload) {
    if (!selectedFarmId || !payload) return;
    setOrchardOverrides((prev) => ({
      ...prev,
      [String(selectedFarmId)]: {
        ...(prev[String(selectedFarmId)] || {}),
        ...payload,
      },
    }));
  }

  function handleSignedIn({ email, name }) {
    const next = {
      authenticated: true,
      email: String(email || ""),
      name: String(name || ""),
    };
    saveAuthSession(next);
    setAuthSession(next);
    setPublicView("landing");
    setActivePage("dashboard");
  }

  function handleSignUp({ email, name }) {
    const code = generateVerificationCode();
    setPendingVerification({
      email: String(email || "").trim(),
      name: String(name || "").trim(),
      code,
      sentAt: new Date().toISOString(),
    });
    setPublicView("verify");
  }

  function handleResendVerification() {
    setPendingVerification((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        code: generateVerificationCode(),
        sentAt: new Date().toISOString(),
      };
    });
  }

  function handleVerificationSuccess() {
    if (!pendingVerification) return;
    handleSignedIn({
      email: pendingVerification.email,
      name: pendingVerification.name,
    });
    setPendingVerification(null);
  }

  function handleSignOut() {
    clearAuthSession();
    setAuthSession({ authenticated: false, email: "", name: "" });
    setPendingVerification(null);
    setPublicView("landing");
  }

  const activeOrchardOverride = selectedFarmId ? orchardOverrides[String(selectedFarmId)] || null : null;

  if (!authSession.authenticated) {
    return (
      <div className="app-root app-root-public">
        <div className="app-background" />
        <div className="public-shell">
          <PublicHeader
            activeView={publicView}
            onNavigate={setPublicView}
          />

          {publicView === "landing" ? (
            <LandingPage
              onSignIn={() => setPublicView("signin")}
              onCreateAccount={() => setPublicView("signup")}
            />
          ) : null}

          {publicView === "signin" ? (
            <SignInPage
              onSubmit={handleSignedIn}
              onCreateAccount={() => setPublicView("signup")}
            />
          ) : null}

          {publicView === "signup" ? (
            <SignUpPage
              onSubmit={handleSignUp}
              onSignIn={() => setPublicView("signin")}
            />
          ) : null}

          {publicView === "verify" ? (
            <VerifyEmailPage
              email={pendingVerification?.email || ""}
              expectedCode={pendingVerification?.code || ""}
              sentAt={pendingVerification?.sentAt}
              onResend={handleResendVerification}
              onVerified={handleVerificationSuccess}
              onBack={() => setPublicView("signup")}
            />
          ) : null}
        </div>
      </div>
    );
  }

  return (
    <div className="app-root app-root-authenticated">
      <div className="app-background" />
      <div className="app-shell">
        <AppHeader
          activePage={activePage}
          onNavigate={navigate}
          user={authSession}
          onSignOut={handleSignOut}
        />

        <FarmSelectorCard
          farms={farmProfiles}
          selectedFarmId={selectedFarmId}
          onChangeFarm={setSelectedFarmId}
          onAddNew={() => setActivePage("setup")}
        />

        {error ? (
          <section className="surface-card">
            <p className="error-text">{error}</p>
          </section>
        ) : null}

        {activePage === "setup" ? (
          <FarmSetupPage farmProfile={selectedFarm} onSaved={handleFarmSaved} />
        ) : null}

        {activePage === "dashboard" ? (
          <DashboardPage
            dashboard={dashboard}
            weather={weather}
            loading={loadingDashboard}
            onRefresh={() => reloadFarmDashboard()}
            onNavigate={navigate}
            orchardOverride={activeOrchardOverride}
          />
        ) : null}

        {activePage === "olive-detect" ? (
          <OliveDetectPage
            farmId={selectedFarmId}
            onScanSaved={() => reloadFarmDashboard()}
          />
        ) : null}

        {activePage === "production-model" ? (
          <ProductionModelPage
            farmId={selectedFarmId}
            farmProfile={selectedFarm}
            dashboard={dashboard}
            weather={weather}
            onForecastSaved={() => reloadFarmDashboard()}
          />
        ) : null}

        {activePage === "harvest-time" ? (
          <HarvestTimePage
            farmId={selectedFarmId}
            farmProfile={selectedFarm}
            onScanSaved={() => reloadFarmDashboard()}
            onApplyOrchardUpdate={applyOrchardSimulationUpdate}
          />
        ) : null}

        {activePage === "disease-scan" ? (
          <DiseaseScanPage
            farmId={selectedFarmId}
            farmProfile={selectedFarm}
            onScanSaved={() => reloadFarmDashboard()}
          />
        ) : null}

        {activePage === "assistant" ? (
          <AssistantPage onNavigate={navigate} />
        ) : null}

        <div className="critical-action-bar" role="navigation" aria-label={t("assistant.quickActions")}>
          <button className="primary-btn" onClick={() => navigate("harvest-time")}>
            <CalendarCheck2 size={16} /> {t("assistant.checkHarvest")}
          </button>
          <button className="secondary-btn" onClick={() => navigate("disease-scan")}>
            <Camera size={16} /> {t("diseaseScan.scanLeaf")}
          </button>
        </div>
      </div>
    </div>
  );
}
