import { MapPin, Plus, Sprout } from "lucide-react";
import { useTranslation } from "react-i18next";

export default function FarmSelectorCard({ farms = [], selectedFarmId, onChangeFarm, onAddNew }) {
  const { t } = useTranslation();
  if (!farms.length) return null;

  return (
    <section className="farm-selector-card surface-card" aria-label={t("dashboard.activeFarm")}>
      <div className="farm-selector-head">
        <p className="eyebrow">{t("dashboard.activeFarm")}</p>
      </div>
      <div className="farm-selector-grid">
        {farms.map((farm) => {
          const isActive = Number(selectedFarmId) === Number(farm.id);
          return (
            <button
              type="button"
              key={farm.id}
              className={`farm-option ${isActive ? "active" : ""}`}
              onClick={() => onChangeFarm?.(Number(farm.id))}
            >
              <div className="farm-option-title">
                <Sprout size={14} aria-hidden="true" />
                <strong>{farm.farm_name}</strong>
              </div>
              <div className="farm-option-meta">
                <span><MapPin size={12} aria-hidden="true" /> {farm.region || t("common.unknownRegion")}</span>
                {farm.country ? <span className="farm-chip">{farm.country}</span> : null}
              </div>
            </button>
          );
        })}
        <button type="button" className="farm-option farm-option-add" onClick={onAddNew}>
          <div className="farm-option-title">
            <Plus size={14} aria-hidden="true" />
            <strong>{t("dashboard.addNewFarm")}</strong>
          </div>
          <div className="farm-option-meta">
            <span>{t("dashboard.addNewFarmDesc")}</span>
          </div>
        </button>
      </div>
    </section>
  );
}
