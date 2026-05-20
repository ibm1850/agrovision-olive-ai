import { useEffect, useMemo, useState } from "react";
import { MapContainer, TileLayer } from "react-leaflet";
import { ChevronLeft, ChevronRight, LocateFixed, MapPinned, Trees } from "lucide-react";
import { motion } from "framer-motion";
import { useTranslation } from "react-i18next";
import LocationPicker from "../components/LocationPicker";
import MapViewportSync from "../components/MapViewportSync";
import { api } from "../lib/api";

function blankGroup() {
  return {
    tempId: `new-${Date.now()}-${Math.random()}`,
    label: "",
    variety: "Chemlali",
    tree_count: 1,
    age_mode: "exact",
    age_exact: 5,
    age_min: null,
    age_max: null,
    status: "healthy",
    notes: "",
  };
}

const STEPS = ["identity", "location", "orchard"];

const CITY_PRESETS = [
  { name: "Sfax", lat: 34.7406, lng: 10.7603 },
  { name: "Sousse", lat: 35.8256, lng: 10.6084 },
  { name: "Mahdia", lat: 35.5047, lng: 11.0622 },
  { name: "Kairouan", lat: 35.6781, lng: 10.0963 },
  { name: "Bizerte", lat: 37.2746, lng: 9.8739 },
  { name: "Zaghouan", lat: 36.4029, lng: 10.1429 },
  { name: "Sidi Bouzid", lat: 35.0382, lng: 9.4858 },
  { name: "Nabeul", lat: 36.451, lng: 10.7355 },
  { name: "Gabes", lat: 33.8815, lng: 10.0982 },
  { name: "Tunis", lat: 36.8065, lng: 10.1815 },
];

const DEFAULT_REGION = "Sfax";
const DEFAULT_LOCATION = [34.7406, 10.7603];

function isValidCoordinatePair(value) {
  return (
    Array.isArray(value) &&
    value.length === 2 &&
    Number.isFinite(Number(value[0])) &&
    Number.isFinite(Number(value[1]))
  );
}

function normalizeLocation(value, fallback = DEFAULT_LOCATION) {
  const source = isValidCoordinatePair(value) ? value : fallback;
  return [Number(source[0]), Number(source[1])];
}

function getCityPresetByName(name) {
  return CITY_PRESETS.find((city) => city.name.toLowerCase() === String(name || "").trim().toLowerCase());
}

function nearestCityName(value) {
  const [lat, lng] = normalizeLocation(value);
  let best = CITY_PRESETS[0];
  let bestDistance = Number.POSITIVE_INFINITY;

  for (const city of CITY_PRESETS) {
    const distance = Math.hypot(lat - city.lat, lng - city.lng);
    if (distance < bestDistance) {
      best = city;
      bestDistance = distance;
    }
  }

  return best.name;
}

export default function FarmSetupPage({ farmProfile, onSaved }) {
  const { t } = useTranslation();
  const [ownerName, setOwnerName] = useState("");
  const [farmName, setFarmName] = useState("");
  const [country, setCountry] = useState("Tunisia");
  const [region, setRegion] = useState(DEFAULT_REGION);
  const [primaryCultivar, setPrimaryCultivar] = useState("Chemlali");
  const [treeAge, setTreeAge] = useState(5);
  const [irrigationMode, setIrrigationMode] = useState("rainfed");
  const [climateNotes, setClimateNotes] = useState("");
  const [notes, setNotes] = useState("");
  const [totalTrees, setTotalTrees] = useState(1);
  const [location, setLocation] = useState(DEFAULT_LOCATION);
  const [groups, setGroups] = useState([blankGroup()]);
  const [removedGroupIds, setRemovedGroupIds] = useState([]);
  const [locating, setLocating] = useState(false);
  const [geoMessage, setGeoMessage] = useState("");
  const [geoMessageTone, setGeoMessageTone] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [stepIndex, setStepIndex] = useState(0);

  useEffect(() => {
    if (!farmProfile) {
      setOwnerName("");
      setFarmName("");
      setCountry("Tunisia");
      setRegion(DEFAULT_REGION);
      setPrimaryCultivar("Chemlali");
      setTreeAge(5);
      setIrrigationMode("rainfed");
      setClimateNotes("");
      setNotes("");
      setTotalTrees(1);
      setLocation(DEFAULT_LOCATION);
      setGroups([blankGroup()]);
      setRemovedGroupIds([]);
      setGeoMessage("");
      setGeoMessageTone("");
      return;
    }

    const presetFromRegion = getCityPresetByName(farmProfile.region);
    const hasSavedCoordinates =
      Number.isFinite(Number(farmProfile.latitude)) &&
      Number.isFinite(Number(farmProfile.longitude));
    const savedLocation = hasSavedCoordinates
      ? [Number(farmProfile.latitude), Number(farmProfile.longitude)]
      : presetFromRegion
        ? [presetFromRegion.lat, presetFromRegion.lng]
        : DEFAULT_LOCATION;

    setOwnerName(farmProfile.owner_name || "");
    setFarmName(farmProfile.farm_name || "");
    setCountry(farmProfile.country || "Tunisia");
    setRegion(farmProfile.region || nearestCityName(savedLocation));
    setPrimaryCultivar(farmProfile.primary_cultivar || farmProfile.tree_groups?.[0]?.variety || "Chemlali");
    setTreeAge(farmProfile.tree_age ?? farmProfile.tree_groups?.[0]?.age_exact ?? 5);
    setIrrigationMode(farmProfile.irrigation_mode || "rainfed");
    setClimateNotes(farmProfile.climate_notes || "");
    setNotes(farmProfile.notes || "");
    setTotalTrees(Number(farmProfile.total_trees || 1));
    setLocation(normalizeLocation(savedLocation));
    const mappedGroups = (farmProfile.tree_groups || []).map((group) => ({
      ...group,
      tempId: String(group.id),
    }));
    setGroups(mappedGroups.length ? mappedGroups : [blankGroup()]);
    setRemovedGroupIds([]);
    setGeoMessage("");
  }, [farmProfile]);

  const progress = useMemo(() => Math.round(((stepIndex + 1) / STEPS.length) * 100), [stepIndex]);
  const stepLabels = useMemo(
    () => [
      t("farmSetup.farmIdentity"),
      t("farmSetup.farmLocation"),
      t("farmSetup.treeGroups"),
    ],
    [t],
  );
  const selectedCity = useMemo(
    () => getCityPresetByName(region)?.name || "__custom__",
    [region],
  );

  function handleLocationChange(nextLocation) {
    const normalized = normalizeLocation(nextLocation, location);
    setLocation(normalized);
    setRegion(nearestCityName(normalized));
    setGeoMessage("");
    setGeoMessageTone("");
  }

  function updateGroup(target, patch) {
    setGroups((prev) =>
      prev.map((group, idx) => {
        const hit = String(group.id ?? group.tempId) === String(target) || idx === target;
        return hit ? { ...group, ...patch } : group;
      }),
    );
  }

  function removeGroup(group) {
    setGroups((prev) => prev.filter((row) => String(row.tempId) !== String(group.tempId)));
    if (group.id) {
      setRemovedGroupIds((prev) => [...prev, group.id]);
    }
  }

  function useCurrentLocation() {
    setGeoMessage("");
    setGeoMessageTone("");
    if (!navigator.geolocation) {
      setGeoMessage(t("farmSetup.geolocationUnsupported", { defaultValue: "La géolocalisation n'est pas disponible dans ce navigateur." }));
      setGeoMessageTone("error");
      return;
    }

    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      (position) => {
        const next = [
          Number(position.coords.latitude.toFixed(6)),
          Number(position.coords.longitude.toFixed(6)),
        ];
        setLocation(next);
        setRegion(nearestCityName(next));
        setGeoMessage(t("farmSetup.geolocationApplied", { defaultValue: "Position actuelle appliquée. Vous pouvez déplacer le point si nécessaire." }));
        setGeoMessageTone("success");
        setLocating(false);
      },
      (geoError) => {
        const denied = geoError.code === geoError.PERMISSION_DENIED;
        setGeoMessage(
          denied
            ? t("farmSetup.geolocationDenied", { defaultValue: "Autorisation refusée. Sélectionnez la position sur la carte." })
            : t("farmSetup.geolocationFailed", { defaultValue: "Impossible de récupérer la position actuelle. Sélectionnez la position sur la carte." }),
        );
        setGeoMessageTone("error");
        setLocating(false);
      },
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 60000 },
    );
  }

  async function saveFarm() {
    setSaving(true);
    setError("");
    setSuccess("");
    try {
      const cleanGroups = groups
        .filter((group) => group.label.trim() && group.tree_count > 0)
        .map((group) => ({
          id: group.id,
          label: group.label.trim(),
          variety: group.variety.trim() || "Unknown",
          tree_count: Number(group.tree_count || 0),
          age_mode: group.age_mode,
          age_exact: group.age_mode === "exact" ? Number(group.age_exact || 0) : null,
          age_min: group.age_mode === "range" ? Number(group.age_min || 0) : null,
          age_max: group.age_mode === "range" ? Number(group.age_max || 0) : null,
          status: group.status || "healthy",
          notes: group.notes || "",
        }));

      if (!cleanGroups.length) {
        throw new Error(t("farmSetup.addValidGroup"));
      }

      const profilePayload = {
        owner_name: ownerName.trim(),
        farm_name: farmName.trim(),
        country: country.trim(),
        region: region.trim(),
        primary_cultivar: primaryCultivar.trim(),
        tree_age: treeAge === "" ? null : Number(treeAge),
        irrigation_mode: irrigationMode,
        climate_notes: climateNotes.trim(),
        notes: notes.trim(),
        latitude: Number(location[0]),
        longitude: Number(location[1]),
        total_trees: Number(totalTrees || 0),
      };

      if (!profilePayload.owner_name || !profilePayload.farm_name || profilePayload.total_trees <= 0) {
        throw new Error(t("farmSetup.fillRequired"));
      }

      let targetFarmId = farmProfile?.id;
      if (!targetFarmId) {
        const created = await api.createFarmProfile({
          ...profilePayload,
          tree_groups: cleanGroups.map(({ id, ...rest }) => rest),
        });
        targetFarmId = created.id;
      } else {
        await api.updateFarmProfile(targetFarmId, profilePayload);
        for (const removedId of removedGroupIds) {
          await api.deleteTreeGroup(targetFarmId, removedId);
        }
        for (const group of cleanGroups) {
          const { id, ...body } = group;
          if (id) {
            await api.updateTreeGroup(targetFarmId, id, body);
          } else {
            await api.createTreeGroup(targetFarmId, body);
          }
        }
      }

      const refreshed = await api.getFarmProfile(targetFarmId);
      onSaved(refreshed);
      setSuccess(t("farmSetup.saveSuccess"));
      setRemovedGroupIds([]);
      setStepIndex(0);
    } catch (err) {
      setError(err.message || t("farmSetup.saveError"));
    } finally {
      setSaving(false);
    }
  }

  function nextStep() {
    setStepIndex((prev) => Math.min(prev + 1, STEPS.length - 1));
  }

  function prevStep() {
    setStepIndex((prev) => Math.max(prev - 1, 0));
  }

  return (
    <section className="page-stack">
      <article className="surface-card setup-wizard-head">
        <div className="section-row">
          <div>
            <h2>{t("farmSetup.wizardTitle")}</h2>
            <p className="subtle">{t("farmSetup.wizardDesc")}</p>
          </div>
          <span className="status-pill">{progress}%</span>
        </div>
        <div className="wizard-progress-track">
          <span className="wizard-progress-fill" style={{ width: `${progress}%` }} />
        </div>
        <div className="wizard-step-row">
          {stepLabels.map((label, idx) => (
            <button
              key={STEPS[idx]}
              type="button"
              onClick={() => setStepIndex(idx)}
              className={`wizard-step ${idx === stepIndex ? "active" : idx < stepIndex ? "done" : ""}`}
            >
              <span>{idx + 1}</span>
              <p>{label}</p>
            </button>
          ))}
        </div>
      </article>

      {stepIndex === 0 ? (
        <motion.article className="surface-card" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
          <h3>{t("farmSetup.farmIdentity")}</h3>
          <div className="form-grid">
            <label>
              {t("farmSetup.farmerName")}
              <input value={ownerName} onChange={(event) => setOwnerName(event.target.value)} className="field" />
            </label>
            <label>
              {t("farmSetup.farmName")}
              <input value={farmName} onChange={(event) => setFarmName(event.target.value)} className="field" />
            </label>
            <label>
              {t("farmSetup.country")}
              <input value={country} onChange={(event) => setCountry(event.target.value)} className="field" />
            </label>
            <label>
              {t("farmSetup.region")}
              <input value={region} onChange={(event) => setRegion(event.target.value)} className="field" />
            </label>
            <label>
              {t("farmSetup.primaryCultivar", { defaultValue: "Cultivar principal" })}
              <input value={primaryCultivar} onChange={(event) => setPrimaryCultivar(event.target.value)} className="field" placeholder="Chemlali" />
            </label>
            <label>
              {t("farmSetup.totalTrees")}
              <input type="number" min={1} value={totalTrees} onChange={(event) => setTotalTrees(event.target.value)} className="field" />
            </label>
            <label>
              {t("farmSetup.treeAge", { defaultValue: "Âge moyen des arbres" })}
              <input type="number" min={0} value={treeAge} onChange={(event) => setTreeAge(event.target.value)} className="field" />
            </label>
            <label>
              {t("farmSetup.irrigationMode", { defaultValue: "Mode d'irrigation" })}
              <select className="field" value={irrigationMode} onChange={(event) => setIrrigationMode(event.target.value)}>
                <option value="rainfed">{t("farmSetup.irrigationRainfed", { defaultValue: "Pluvial" })}</option>
                <option value="drip">{t("farmSetup.irrigationDrip", { defaultValue: "Goutte-à-goutte" })}</option>
                <option value="surface">{t("farmSetup.irrigationSurface", { defaultValue: "Irrigation de surface" })}</option>
                <option value="unknown">{t("common.unknown", { defaultValue: "Non précisé" })}</option>
              </select>
            </label>
            <label className="full-width">
              {t("farmSetup.climateNotes")} ({t("productionModel.optional")})
              <textarea value={climateNotes} onChange={(event) => setClimateNotes(event.target.value)} className="field textarea" rows={3} />
            </label>
            <label className="full-width">
              {t("farmSetup.notes", { defaultValue: "Notes" })} ({t("productionModel.optional")})
              <textarea value={notes} onChange={(event) => setNotes(event.target.value)} className="field textarea" rows={3} />
            </label>
          </div>
        </motion.article>
      ) : null}

      {stepIndex === 1 ? (
        <motion.article className="surface-card" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
          <h3><MapPinned size={16} /> {t("farmSetup.farmLocation")}</h3>
          <p className="subtle">{t("farmSetup.pickCityOrMap")}</p>
          <div className="inline-grid">
            <label>
              {t("farmSetup.quickCityPreset")}
              <select
                className="field"
                value={selectedCity}
                onChange={(event) => {
                  const picked = CITY_PRESETS.find((city) => city.name === event.target.value);
                  if (!picked) return;
                  setRegion(picked.name);
                  setLocation([picked.lat, picked.lng]);
                  setGeoMessage("");
                  setGeoMessageTone("");
                }}
              >
                <option value="__custom__">{t("farmSetup.customCoordinates")}</option>
                {CITY_PRESETS.map((city) => (
                  <option key={city.name} value={city.name}>{city.name}</option>
                ))}
              </select>
            </label>
            <div className="field-action-block">
              <span>{t("farmSetup.gpsLocation", { defaultValue: "Position actuelle" })}</span>
              <button type="button" className="secondary-btn" onClick={useCurrentLocation} disabled={locating}>
                <LocateFixed size={16} />
                {locating ? t("farmSetup.locating", { defaultValue: "Localisation..." }) : t("farmSetup.useCurrentLocation", { defaultValue: "Utiliser ma position" })}
              </button>
            </div>
          </div>
          {geoMessage ? <p className={geoMessageTone === "success" ? "ok-text" : "error-text"}>{geoMessage}</p> : null}
          <div className="map-wrap">
            <MapContainer
              center={location}
              zoom={8}
              scrollWheelZoom
              className="setup-map"
            >
              <TileLayer
                attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              />
              <MapViewportSync center={location} zoom={8} />
              <LocationPicker value={location} onChange={handleLocationChange} />
            </MapContainer>
          </div>
          <div className="inline-grid">
            <label>
              {t("farmSetup.latitude")}
              <input
                type="number"
                step="0.0001"
                className="field"
                value={String(location[0] ?? "")}
                onChange={(event) => {
                  const nextLat = Number(event.target.value);
                  if (Number.isFinite(nextLat)) {
                    handleLocationChange([nextLat, location[1]]);
                  }
                }}
              />
            </label>
            <label>
              {t("farmSetup.longitude")}
              <input
                type="number"
                step="0.0001"
                className="field"
                value={String(location[1] ?? "")}
                onChange={(event) => {
                  const nextLng = Number(event.target.value);
                  if (Number.isFinite(nextLng)) {
                    handleLocationChange([location[0], nextLng]);
                  }
                }}
              />
            </label>
          </div>
          <p className="subtle">{t("farmSetup.latitude")}: {Number(location[0]).toFixed(4)} <span aria-hidden="true">&middot;</span> {t("farmSetup.longitude")}: {Number(location[1]).toFixed(4)}</p>
        </motion.article>
      ) : null}

      {stepIndex === 2 ? (
        <motion.article className="surface-card" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
          <div className="section-row">
            <h3><Trees size={16} /> {t("farmSetup.treeGroups")}</h3>
            <button className="secondary-btn" onClick={() => setGroups((prev) => [...prev, blankGroup()])}>{t("farmSetup.addGroup")}</button>
          </div>
          <div className="group-list">
            {groups.map((group) => (
              <div key={group.tempId} className="group-card">
                <div className="inline-grid">
                  <label>
                    {t("farmSetup.groupLabel")}
                    <input className="field" value={group.label} onChange={(event) => updateGroup(group.tempId, { label: event.target.value })} placeholder={t("farmSetup.groupLabelPlaceholder")} />
                  </label>
                  <label>
                    {t("farmSetup.variety")}
                    <input className="field" value={group.variety} onChange={(event) => updateGroup(group.tempId, { variety: event.target.value })} />
                  </label>
                  <label>
                    {t("farmSetup.treeCount")}
                    <input type="number" min={1} className="field" value={group.tree_count} onChange={(event) => updateGroup(group.tempId, { tree_count: Number(event.target.value) })} />
                  </label>
                  <label>
                    {t("farmSetup.ageMode")}
                    <select className="field" value={group.age_mode} onChange={(event) => updateGroup(group.tempId, { age_mode: event.target.value })}>
                      <option value="exact">{t("farmSetup.exactAge")}</option>
                      <option value="range">{t("farmSetup.ageRange")}</option>
                    </select>
                  </label>
                </div>
                {group.age_mode === "exact" ? (
                  <label>
                    {t("farmSetup.exactAge")} ({t("common.years")})
                    <input type="number" min={0} className="field" value={group.age_exact ?? ""} onChange={(event) => updateGroup(group.tempId, { age_exact: Number(event.target.value) })} />
                  </label>
                ) : (
                  <div className="inline-grid">
                    <label>
                      {t("farmSetup.minAge")}
                      <input type="number" min={0} className="field" value={group.age_min ?? ""} onChange={(event) => updateGroup(group.tempId, { age_min: Number(event.target.value) })} />
                    </label>
                    <label>
                      {t("farmSetup.maxAge")}
                      <input type="number" min={0} className="field" value={group.age_max ?? ""} onChange={(event) => updateGroup(group.tempId, { age_max: Number(event.target.value) })} />
                    </label>
                  </div>
                )}
                <div className="inline-grid">
                  <label>
                    {t("farmSetup.status")}
                    <select className="field" value={group.status || "healthy"} onChange={(event) => updateGroup(group.tempId, { status: event.target.value })}>
                      <option value="healthy">{t("farmSetup.healthy")}</option>
                      <option value="monitoring">{t("dashboard.monitoring")}</option>
                      <option value="under_treatment">{t("farmSetup.underTreatment")}</option>
                      <option value="harvested">{t("farmSetup.harvested")}</option>
                    </select>
                  </label>
                  <label>
                    {t("farmSetup.notes")}
                    <input className="field" value={group.notes || ""} onChange={(event) => updateGroup(group.tempId, { notes: event.target.value })} placeholder={t("farmSetup.notesPlaceholder")} />
                  </label>
                </div>
                <div className="right-actions">
                  <button className="ghost-btn danger" onClick={() => removeGroup(group)}>{t("farmSetup.removeGroup")}</button>
                </div>
              </div>
            ))}
          </div>
        </motion.article>
      ) : null}

      <article className="surface-card">
        <div className="section-row">
          <div className="inline-actions">
            <button className="ghost-btn" onClick={prevStep} disabled={stepIndex === 0}><ChevronLeft size={16} /> {t("common.back")}</button>
            <button className="secondary-btn" onClick={nextStep} disabled={stepIndex === STEPS.length - 1}>{t("common.next")} <ChevronRight size={16} /></button>
          </div>
          <button className="primary-btn" onClick={saveFarm} disabled={saving}>{saving ? t("productionModel.saving") : t("farmSetup.save")}</button>
        </div>
        {error ? <p className="error-text">{error}</p> : null}
        {success ? <p className="ok-text">{success}</p> : null}
      </article>
    </section>
  );
}
