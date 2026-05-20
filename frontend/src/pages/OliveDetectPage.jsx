import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import DragDropUpload from "../components/DragDropUpload";
import { api } from "../lib/api";
import { assessImageQuality } from "../lib/imageQuality";
import OliveGuideCard from "../components/guide/OliveGuideCard";

function average(values) {
  if (!values.length) return 0;
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

export default function OliveDetectPage({ farmId, onScanSaved }) {
  const { t } = useTranslation();
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [results, setResults] = useState([]);
  const [qualityHints, setQualityHints] = useState([]);

  const summary = useMemo(() => {
    const totalCount = results.reduce((sum, row) => sum + Number(row.detected_olives || 0), 0);
    const avgConf = average(results.map((row) => Number(row.avg_confidence || 0)));
    return { totalCount, avgConf };
  }, [results]);

  async function runDetection() {
    if (!files.length || loading) return;
    setLoading(true);
    setError("");
    setResults([]);
    setQualityHints([]);

    try {
      const hints = [];
      for (const file of files) {
        const quality = await assessImageQuality(file);
        if (quality.warnings.length) {
          hints.push({ file: file.name, warnings: quality.warnings });
        }
      }
      setQualityHints(hints);

      const perImage = [];
      for (const file of files) {
        const detected = await api.detectOlives(file, { conf: 0.35, iou: 0.45, imgsz: 960 });
        perImage.push({
          image_name: file.name,
          ...detected,
        });
      }
      setResults(perImage);

      if (farmId) {
        const avgConf = average(perImage.map((row) => Number(row.avg_confidence || 0)));
        const totalCount = perImage.reduce((sum, row) => sum + Number(row.detected_olives || 0), 0);
        const preliminary = files.length < 3;
        const pendingReview = avgConf < 0.65 || totalCount === 0;
        await api.createFarmScan(farmId, {
          module_type: "olive_detect",
          image_count: files.length,
          preliminary,
          confidence: avgConf,
          status: pendingReview ? "pending_review" : "new",
          summary: t("oliveDetect.summaryDetected", { count: totalCount, images: files.length }),
          next_action:
            totalCount === 0
              ? t("oliveDetect.nextActionUploadClearer")
              : preliminary
                ? t("oliveDetect.nextActionAddMore")
                : t("oliveDetect.nextActionMonitorWeekly"),
          payload_json: {
            per_image: perImage.map((row) => ({
              image_name: row.image_name,
              detected_olives: row.detected_olives,
              avg_confidence: row.avg_confidence,
            })),
            total_detected_olives: totalCount,
            average_confidence: avgConf,
            quality_hints: hints,
          },
        });
        if (typeof onScanSaved === "function") onScanSaved();
      }
    } catch (err) {
      setError(err.message || t("oliveDetect.detectFailed"));
    } finally {
      setLoading(false);
    }
  }

  const confidenceText =
    summary.avgConf >= 0.8 ? t("diseaseScan.highConfidence") : summary.avgConf >= 0.65 ? t("diseaseScan.mediumConfidence") : t("dashboard.needsReview");

  return (
    <section className="page-stack">
      <OliveGuideCard
        title={t("oliveDetect.title")}
        message={t("oliveDetect.message")}
        tip={t("oliveDetect.tip")}
        chips={[t("oliveDetect.multiAngle"), t("oliveDetect.confidenceScored"), t("oliveDetect.yieldTracking")]}
      />
      <article className="surface-card">
        <h2>{t("oliveDetect.title")}</h2>
        <p className="subtle">
          {t("oliveDetect.description")}
        </p>
        <DragDropUpload
          label={t("oliveDetect.uploadPhotos")}
          hint={t("oliveDetect.uploadHint")}
          multiple
          onFilesSelected={(selected) => setFiles(selected || [])}
        />
        <div className="inline-actions">
          <button className="primary-btn" onClick={runDetection} disabled={loading || !files.length}>
            {loading ? t("common.loading") : t("oliveDetect.run")}
          </button>
        </div>
        {error ? <p className="error-text">{error}</p> : null}
      </article>

      <article className="surface-card">
        <h3>{t("oliveDetect.resultSummary")}</h3>
        <div className="stats-grid compact">
          <div className="stat-card">
            <p>{t("oliveDetect.imagesAnalyzed")}</p>
            <h3>{results.length}</h3>
          </div>
          <div className="stat-card">
            <p>{t("oliveDetect.totalEstimatedOlives")}</p>
            <h3>{summary.totalCount}</h3>
          </div>
          <div className="stat-card">
            <p>{t("diseaseScan.confidence")}</p>
            <h3>{Math.round(summary.avgConf * 100)}%</h3>
            <small>{confidenceText}</small>
          </div>
        </div>
        {files.length === 1 ? <p className="subtle">{t("oliveDetect.preliminaryOneImage")}</p> : null}
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

      <article className="surface-card">
        <h3>{t("oliveDetect.perImageCounts")}</h3>
        <div className="list-stack">
          {results.map((row) => (
            <div key={row.image_name} className="list-row">
              <div>
                <strong>{row.image_name}</strong>
                <p>{t("oliveDetect.detectedOlives")}: {row.detected_olives}</p>
              </div>
              <span className="status-pill">{Math.round(Number(row.avg_confidence || 0) * 100)}%</span>
            </div>
          ))}
          {!results.length ? <p className="subtle">{t("oliveDetect.noRunYet")}</p> : null}
        </div>
      </article>
    </section>
  );
}
