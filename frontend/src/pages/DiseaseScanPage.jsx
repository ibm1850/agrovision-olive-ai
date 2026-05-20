import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import { AlertTriangle, CheckCircle2, Microscope, UploadCloud } from "lucide-react";
import { useTranslation } from "react-i18next";
import DragDropUpload from "../components/DragDropUpload";
import { api } from "../lib/api";
import { assessImageQuality } from "../lib/imageQuality";
import OliveGuideCard from "../components/guide/OliveGuideCard";
import DiseaseResultCard from "../components/cards/DiseaseResultCard";

function average(values) {
  if (!values.length) return 0;
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function mode(values) {
  const counts = {};
  for (const value of values) counts[value] = (counts[value] || 0) + 1;
  return Object.entries(counts).sort((a, b) => b[1] - a[1])[0]?.[0] || "uncertain_leaf";
}

function treatmentForDisease(disease, t) {
  const text = String(disease || "").toLowerCase();
  if (text.includes("no clear disease") || text.includes("none") || text.includes("healthy")) return t("diseaseScan.noTreatmentNeeded");
  if (text.includes("uncertain")) return t("diseaseScan.uncertainTreatment");
  return t("diseaseScan.defaultTreatment");
}

function confidenceBadge(confidence, t) {
  if (confidence >= 0.8) return { label: t("diseaseScan.highConfidence"), tone: "good", icon: CheckCircle2 };
  if (confidence >= 0.65) return { label: t("diseaseScan.mediumConfidence"), tone: "warn", icon: AlertTriangle };
  return { label: t("dashboard.needsReview"), tone: "danger", icon: AlertTriangle };
}

function translatePlantPart(part, t) {
  const key = String(part || "unknown").toLowerCase().replace(/\s+/g, "_");
  return t(`plantParts.${key}`, { defaultValue: part || t("plantParts.unknown") });
}

function translatedReason(row, t) {
  if (row?.short_reason_key) {
    return t(`diseaseScan.reasons.${row.short_reason_key}`, { defaultValue: row.short_reason || "" });
  }
  if (row?.status === "needs_better_image") return t("diseaseScan.uploadClearerImage");
  if (row?.status === "unsupported_part") return t("diseaseScan.unsupportedImage", { defaultValue: t("diseaseScan.uncertainEvidence") });
  return row?.short_reason || "";
}

function translatedAction(row, t) {
  if (row?.next_action_key) {
    return t(`diseaseScan.actions.${row.next_action_key}`, { defaultValue: row.next_action || "" });
  }
  if (row?.status === "needs_better_image") return t("diseaseScan.uploadClearerImage");
  return row?.next_action || "";
}

export default function DiseaseScanPage({ farmId, onScanSaved }) {
  const { t, i18n } = useTranslation();
  const language = i18n.resolvedLanguage || i18n.language || "fr";
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [results, setResults] = useState([]);
  const [qualityHints, setQualityHints] = useState([]);

  const aggregate = useMemo(() => {
    if (!results.length) {
      return {
        disease: "uncertain_leaf",
        severity: t("diseaseScan.unknown"),
        confidence: 0,
        affected_part: "unknown",
        confidenceLabel: t("dashboard.needsReview"),
        status: "uncertain",
        short_reason: t("diseaseScan.noScansYet"),
        short_reason_key: "",
        next_action: t("diseaseScan.startWithClearImage"),
        next_action_key: "",
      };
    }

    const okResults = results.filter((row) => row.status === "ok");
    const strongOk = okResults.filter((row) => Number(row.confidence || 0) >= 0.72);

    const disease =
      strongOk.length > 0
        ? mode(strongOk.map((row) => row.likely_disease_key || row.likely_disease || "uncertain_leaf"))
        : mode(results.map((row) => row.likely_disease_key || row.likely_disease || "uncertain_leaf"));
    const severity = mode(results.map((row) => row.severity || t("diseaseScan.unknown")));
    const confidence = average(results.map((row) => Number(row.confidence || 0)));
    const affected_part = mode(results.map((row) => row.affected_part || row.plant_part_route || "unknown"));
    const status = strongOk.length > 0 ? "ok" : mode(results.map((row) => row.status || "uncertain"));
    const short_reason = mode(results.map((row) => row.short_reason || t("diseaseScan.uncertainEvidence")));
    const short_reason_key = mode(results.map((row) => row.short_reason_key || ""));
    const next_action = mode(results.map((row) => row.next_action || t("diseaseScan.uploadAnotherClearImage")));
    const next_action_key = mode(results.map((row) => row.next_action_key || ""));

    const confidenceLabel = confidence >= 0.8 ? t("diseaseScan.highConfidence") : confidence >= 0.7 ? t("diseaseScan.mediumConfidence") : t("dashboard.needsReview");
    return { disease, severity, confidence, affected_part, confidenceLabel, status, short_reason, short_reason_key, next_action, next_action_key };
  }, [results, t]);

  const aggregateAction = aggregate.next_action_key
    ? t(`diseaseScan.actions.${aggregate.next_action_key}`, { defaultValue: aggregate.next_action })
    : aggregate.next_action;
  const aggregateReason = aggregate.short_reason_key
    ? t(`diseaseScan.reasons.${aggregate.short_reason_key}`, { defaultValue: aggregate.short_reason })
    : aggregate.short_reason;

  const confidenceMeta = confidenceBadge(aggregate.confidence || 0, t);
  const ConfidenceIcon = confidenceMeta.icon;

  async function runDiseaseScan() {
    if (!files.length || loading) return;
    setLoading(true);
    setError("");
    setResults([]);

    try {
      const hints = [];
      for (const file of files) {
        const quality = await assessImageQuality(file);
        if (quality.warnings.length) hints.push({ file: file.name, warnings: quality.warnings });
      }
      setQualityHints(hints);

      const perImage = [];
      for (const file of files.slice(0, 3)) {
        try {
          const result = await api.diseaseScanExpert(file, { language });
          perImage.push({
            image_name: file.name,
            ...result,
            notes: [result.short_reason, ...(result.warnings || [])].filter(Boolean).join(" "),
          });
        } catch (scanError) {
          perImage.push({
            image_name: file.name,
            likely_disease_key: "uncertain_leaf",
            likely_disease: "uncertain_leaf",
            affected_part: "unknown",
            confidence: 0,
            confidence_label: t("status.medium"),
            short_reason: scanError.message || t("diseaseScan.analysisFailed"),
            next_action: t("diseaseScan.uploadClearerImage"),
            status: "uncertain",
            plant_part_route: "unknown",
            route_confidence: 0,
            severity: t("diseaseScan.unknown"),
            notes: scanError.message || t("diseaseScan.analysisFailed"),
          });
        }
      }
      setResults(perImage);

      if (farmId) {
        const averageConfidence = average(perImage.map((row) => Number(row.confidence || 0)));
        const disease = mode(perImage.map((row) => row.likely_disease_key || row.likely_disease || "uncertain_leaf"));
        const severity = mode(perImage.map((row) => row.severity || t("diseaseScan.unknown")));
        const preliminary = files.length < 3;
        const pendingReview =
          averageConfidence < 0.7 ||
          disease.toLowerCase().includes("uncertain") ||
          perImage.some((row) => row.status && row.status !== "ok");

        await api.createFarmScan(farmId, {
          module_type: "disease_scan",
          image_count: perImage.length,
          preliminary,
          confidence: averageConfidence,
          status: pendingReview ? "pending_review" : "new",
          summary: `${t("diseaseScan.result")}: ${disease} (${severity}) ${Math.round(averageConfidence * 100)}%`,
          next_action:
            pendingReview
              ? t("diseaseScan.reviewUploadClearer")
              : t("diseaseScan.followManagement"),
          payload_json: {
            disease,
            severity,
            confidence: averageConfidence,
            affected_part: mode(perImage.map((row) => row.affected_part || row.plant_part_route || "unknown")),
            per_image: perImage,
            quality_hints: hints,
          },
        });
        if (typeof onScanSaved === "function") onScanSaved();
      }
    } catch (err) {
      setError(err.message || t("diseaseScan.scanFailed"));
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="page-stack">
      <OliveGuideCard
        title={t("diseaseScan.title")}
        message={t("diseaseScan.subtitle")}
        tip={t("diseaseScan.leafPipelineTip")}
        chips={[t("diseaseScan.qualityGate"), t("diseaseScan.plantPartRouting"), t("diseaseScan.safeFallback")]}
      />

      <article className="surface-card">
        <div className="section-row">
          <div>
            <h2>{t("diseaseScan.uploadTitle")}</h2>
            <p className="subtle">{t("diseaseScan.uploadDesc")}</p>
          </div>
          <span className={`status-pill ${confidenceMeta.tone === "good" ? "high" : confidenceMeta.tone === "warn" ? "medium" : "pending_review"}`}>
            <ConfidenceIcon size={14} /> {confidenceMeta.label}
          </span>
        </div>

        <DragDropUpload
          label={t("diseaseScan.uploadLeaf")}
          hint={t("diseaseScan.uploadHint")}
          multiple
          onFilesSelected={(selected) => setFiles((selected || []).slice(0, 3))}
        />

        <div className="inline-actions">
          <button className="primary-btn" onClick={runDiseaseScan} disabled={loading || !files.length}>
            <UploadCloud size={16} /> {loading ? t("common.loading") : t("diseaseScan.runScan")}
          </button>
        </div>
        {error ? <p className="error-text">{error}</p> : null}
      </article>

      {!results.length ? (
        <article className="surface-card empty-state-card">
          <h3>{t("diseaseScan.noScansYet")}</h3>
          <p className="subtle">{t("diseaseScan.noScansDesc")}</p>
        </article>
      ) : null}

      <DiseaseResultCard
        aggregate={aggregate}
        action={aggregateAction || t("diseaseScan.uploadAnotherClearImage")}
        treatment={treatmentForDisease(aggregate.disease, t)}
      />

      <article className="surface-card">
        <p className="subtle"><Microscope size={14} /> {t("diseaseScan.reason")}: {aggregateReason || t("diseaseScan.noSummaryYet")}</p>
        <p className="subtle">{t("diseaseScan.nextAction")}: {aggregateAction || t("diseaseScan.rescan7Days")}</p>
        {files.length === 1 ? <p className="subtle">{t("diseaseScan.preliminaryOneImage")}</p> : null}
      </article>

      <article className="surface-card">
        <h3>{t("diseaseScan.perImageDiagnostics")}</h3>
        <div className="list-stack">
          {results.map((row) => (
            <motion.div className="list-row" key={row.image_name} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
              <div>
                <strong>{row.image_name}</strong>
                <p>
                  {t(`diseaseScan.${String(row.likely_disease_key || row.likely_disease || "uncertain_leaf").toLowerCase()}`, { defaultValue: row.likely_disease || t("diseaseScan.uncertain") })}
                  <span aria-hidden="true">&middot;</span> {row.severity || t("diseaseScan.unknown")}
                  <span aria-hidden="true">&middot;</span> {translatePlantPart(row.affected_part || row.affected_part_key || "unknown", t)}
                </p>
                <p>{translatedReason(row, t)} {translatedAction(row, t)}</p>
              </div>
              <span className="status-pill">{Math.round(Number(row.confidence || 0) * 100)}%</span>
            </motion.div>
          ))}
        </div>

        {qualityHints.length ? (
          <div className="quality-list">
            {qualityHints.map((hint) => (
              <div key={hint.file} className="hint-row">
                <strong>{hint.file}</strong>
                <ul>
                  {hint.warnings.map((warning) => (
                    <li key={warning}>{warning}</li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        ) : null}
      </article>
    </section>
  );
}
