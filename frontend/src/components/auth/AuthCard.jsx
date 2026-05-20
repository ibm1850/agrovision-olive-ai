import { useTranslation } from "react-i18next";

export default function AuthCard({ title, subtitle, children, footer }) {
  const { t } = useTranslation();

  return (
    <section className="auth-shell">
      <article className="auth-card">
        <div className="auth-card-header">
          <p className="eyebrow">{t("auth.brand")}</p>
          <h1>{title}</h1>
          <p className="subtle">{subtitle}</p>
        </div>
        <div className="auth-card-body">{children}</div>
        {footer ? <div className="auth-card-footer">{footer}</div> : null}
      </article>
    </section>
  );
}
