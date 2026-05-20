import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import AuthCard from "../components/auth/AuthCard";
import VerificationCodeInput from "../components/auth/VerificationCodeInput";

export default function VerifyEmailPage({
  email,
  expectedCode,
  sentAt,
  onResend,
  onVerified,
  onBack,
}) {
  const { t } = useTranslation();
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [resendMessage, setResendMessage] = useState("");

  useEffect(() => {
    setCode("");
    setError("");
    setResendMessage("");
  }, [email, expectedCode, sentAt]);

  function handleVerify(event) {
    event.preventDefault();
    if (!expectedCode) {
      setError(t("auth.verificationUnavailable"));
      return;
    }
    if (String(code).trim() !== String(expectedCode).trim()) {
      setError(t("auth.incorrectCode"));
      return;
    }
    setError("");
    onVerified();
  }

  function handleResend() {
    onResend();
    setResendMessage(t("auth.newCodeSent"));
    setError("");
    setCode("");
  }

  return (
    <AuthCard
      title={t("auth.verifyTitle")}
      subtitle={t("auth.verifySubtitle", { email: email || t("auth.inbox") })}
      footer={
        <div className="verify-footer-actions">
          <button type="button" className="ghost-btn" onClick={onBack}>{t("common.back")}</button>
          <button type="button" className="secondary-btn" onClick={handleResend}>{t("auth.resendCode")}</button>
        </div>
      }
    >
      <form className="auth-form" onSubmit={handleVerify}>
        <VerificationCodeInput value={code} onChange={setCode} />
        {error ? <p className="error-text">{error}</p> : null}
        {resendMessage ? <p className="ok-text">{resendMessage}</p> : null}
        <p className="subtle">{t("auth.demoCode")}: <strong>{expectedCode || "------"}</strong></p>
        <button className="primary-btn auth-submit" type="submit">{t("auth.verifyContinue")}</button>
      </form>
    </AuthCard>
  );
}
