import { useState } from "react";
import { useTranslation } from "react-i18next";
import AuthCard from "../components/auth/AuthCard";

function isValidEmail(value) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(String(value || "").trim());
}

export default function SignInPage({ onSubmit, onCreateAccount }) {
  const { t } = useTranslation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  function handleSubmit(event) {
    event.preventDefault();
    const cleanEmail = email.trim();
    if (!isValidEmail(cleanEmail)) {
      setError(t("auth.validEmail"));
      return;
    }
    if (password.length < 6) {
      setError(t("auth.passwordMin6"));
      return;
    }
    setError("");
    onSubmit({ email: cleanEmail, name: cleanEmail.split("@")[0] });
  }

  return (
    <AuthCard
      title={t("auth.signInTitle")}
      subtitle={t("auth.signInSubtitle")}
      footer={
        <p className="subtle">
          {t("auth.noAccountYet")} <button type="button" className="inline-link" onClick={onCreateAccount}>{t("nav.createAccount")}</button>
        </p>
      }
    >
      <form className="auth-form" onSubmit={handleSubmit}>
        <label>
          {t("auth.email")}
          <input
            className="field"
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder={t("auth.emailPlaceholder")}
            autoComplete="email"
          />
        </label>
        <label>
          {t("auth.password")}
          <input
            className="field"
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            placeholder={t("auth.enterPassword")}
            autoComplete="current-password"
          />
        </label>
        {error ? <p className="error-text">{error}</p> : null}
        <button className="primary-btn auth-submit" type="submit">{t("nav.signIn")}</button>
      </form>
    </AuthCard>
  );
}
