import { useTranslation } from "react-i18next";

export default function EmptyStateAssistantCard({ onSelect }) {
  const { t } = useTranslation();
  const options = [
    { id: "harvest-time", label: t("assistant.checkHarvestReadiness") },
    { id: "disease-scan", label: t("assistant.scanLeaf") },
    { id: "production-model", label: t("assistant.openProductionOutlook") },
    { id: "dashboard", label: t("assistant.summarizeFarmToday") },
  ];

  return (
    <article className="assistant-empty-card">
      <div>
        <p className="eyebrow">{t("assistant.guide")}</p>
        <h3>{t("assistant.ready")}</h3>
        <p className="subtle">{t("assistant.emptyStateDesc")}</p>
      </div>
      <div className="assistant-action-grid">
        {options.map((option) => (
          <button key={option.id} className="ghost-card" onClick={() => onSelect(option.id, option.label)}>
            {option.label}
          </button>
        ))}
      </div>
    </article>
  );
}
