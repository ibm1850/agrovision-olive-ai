import { useState } from "react";
import { useTranslation } from "react-i18next";
import AuthCard from "../components/auth/AuthCard";

function isValidEmail(value) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(String(value || "").trim());
}

export default function SignUpPage({ onSubmit, onSignIn }) {
  const { t } = useTranslation();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");

  function handleSubmit(event) {
    event.preventDefault();
    const cleanName = name.trim();
    const cleanEmail = email.trim();

    if (cleanName.length < 2) {
      setError(t("auth.nameRequired"));
      return;
    }
    if (!isValidEmail(cleanEmail)) {
      setError(t("auth.validEmail"));
      return;
    }
    if (password.length < 8) {
      setError(t("auth.passwordMin8"));
      return;
    }
    if (password !== confirmPassword) {
      setError(t("auth.passwordsMismatch"));
      return;
    }

    setError("");
    onSubmit({ name: cleanName, email: cleanEmail, password });
  }

  return (
    <AuthCard
      title={t("auth.signUpTitle")}
      subtitle={t("auth.signUpSubtitle")}
      footer={
        <p className="subtle">
          {t("auth.alreadyRegistered")} <button type="button" className="inline-link" onClick={onSignIn}>{t("nav.signIn")}</button>
        </p>
      }
    >
      <form className="auth-form" onSubmit={handleSubmit}>
        <label>
          {t("auth.fullName")}
          <input
            className="field"
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder={t("auth.farmerName")}
            autoComplete="name"
          />
        </label>
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
            placeholder={t("auth.atLeast8")}
            autoComplete="new-password"
          />
        </label>
        <label>
          {t("auth.confirmPassword")}
          <input
            className="field"
            type="password"
            value={confirmPassword}
            onChange={(event) => setConfirmPassword(event.target.value)}
            placeholder={t("auth.repeatPassword")}
            autoComplete="new-password"
          />
        </label>
        {error ? <p className="error-text">{error}</p> : null}
        <button className="primary-btn auth-submit" type="submit">{t("nav.createAccount")}</button>
      </form>
    </AuthCard>
  );
}
