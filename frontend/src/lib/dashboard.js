export const TABS = [
  { id: "home", labelKey: "overview", short: "OV" },
  { id: "detect", labelKey: "olive_detect", short: "OD" },
  { id: "scan", labelKey: "disease_scan", short: "SC" },
  { id: "results", labelKey: "results", short: "RS" },
  { id: "harvest", labelKey: "harvest_ai", short: "HV" },
  { id: "dashboard", labelKey: "dashboard", short: "DB" },
  { id: "assistant", labelKey: "assistant", short: "AI" },
];

export function clampScore(score) {
  const value = Number(score);
  if (!Number.isFinite(value)) return 0;
  return Math.max(0, Math.min(100, value));
}

export function riskKey(score) {
  if (score >= 80) return "low";
  if (score >= 60) return "mild";
  if (score >= 40) return "moderate";
  return "high";
}

export function riskTone(score) {
  if (score >= 80) return "good";
  if (score >= 60) return "warn";
  return "danger";
}

export function recommendationFor(analysis, t) {
  if (!analysis) return t("rec_default");
  const disease = String(analysis.disease || "").toLowerCase();
  if (disease.includes("peacock")) {
    return t("rec_peacock");
  }
  if (disease.includes("anthracnose")) {
    return t("rec_anthracnose");
  }
  if (disease.includes("aculus")) {
    return t("rec_aculus");
  }
  if (disease.includes("scab")) {
    return t("rec_scab");
  }
  if (disease.includes("uncertain")) {
    return t("rec_uncertain");
  }
  return t("rec_stable");
}

export function toChartPoints(values, width = 520, height = 180) {
  if (!values.length) return "";
  const max = Math.max(...values, 100);
  const min = Math.min(...values, 0);

  return values
    .map((value, index) => {
      const x = (index / Math.max(values.length - 1, 1)) * width;
      const y = height - ((value - min) / Math.max(max - min, 1)) * height;
      return `${x},${y}`;
    })
    .join(" ");
}

export function prettyDate(value, locale = "en-US") {
  if (!value) return "--";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "--";
  return parsed.toLocaleDateString(locale);
}

export function severityClass(stage) {
  const text = String(stage || "").toLowerCase();
  if (text.includes("optimal")) return "good";
  if (text.includes("early")) return "warn";
  if (text.includes("late") || text.includes("immature")) return "danger";
  return "neutral";
}
