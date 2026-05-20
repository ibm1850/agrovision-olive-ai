function toNumber(value, fallback = 0) {
  const n = Number(value);
  return Number.isFinite(n) ? n : fallback;
}

function lower(value) {
  return String(value || "").toLowerCase();
}

export const SCORE_TABLES = {
  rainfall: [
    { key: "very_dry", label: "Very dry", score: 0.82 },
    { key: "dry", label: "Dry", score: 0.9 },
    { key: "normal", label: "Normal", score: 1.0 },
    { key: "good", label: "Good", score: 1.08 },
    { key: "excellent", label: "Excellent", score: 1.15 },
  ],
  heat: [
    { key: "severe", label: "Severe heat stress", score: 0.85 },
    { key: "hot", label: "Hot", score: 0.92 },
    { key: "normal", label: "Normal", score: 1.0 },
    { key: "mild", label: "Mild favorable", score: 1.04 },
  ],
  irrigation: [
    { key: "rainfed_stressed", label: "Rainfed stressed orchard", score: 0.9 },
    { key: "limited", label: "Limited irrigation", score: 0.97 },
    { key: "adequate", label: "Adequate irrigation", score: 1.05 },
    { key: "strong", label: "Strong well-managed irrigation", score: 1.1 },
    { key: "default", label: "Neutral default assumption", score: 1.0 },
  ],
  disease: [
    { key: "high", label: "High disease pressure", score: 0.88 },
    { key: "moderate", label: "Moderate disease pressure", score: 0.95 },
    { key: "low", label: "Low disease pressure", score: 1.0 },
    { key: "very_healthy", label: "Very healthy orchard", score: 1.03 },
    { key: "default", label: "Neutral default assumption", score: 1.0 },
  ],
  age: [
    { key: "young", label: "Young non-full-production orchard", score: 0.8 },
    { key: "growing", label: "Growing orchard", score: 0.92 },
    { key: "mature", label: "Mature productive orchard", score: 1.05 },
    { key: "old", label: "Old declining orchard", score: 0.95 },
    { key: "default", label: "Neutral default assumption", score: 1.0 },
  ],
};

function findScore(list, key, fallbackKey = "default") {
  return (
    list.find((item) => item.key === key) ||
    list.find((item) => item.key === fallbackKey) ||
    { key: fallbackKey, label: "Default", score: 1.0 }
  );
}

export function deriveRainfallBucket(weather) {
  const rainfall = toNumber(weather?.rainfall_total ?? weather?.last_30_days?.rainfall_total, NaN);
  if (!Number.isFinite(rainfall)) {
    return { ...findScore(SCORE_TABLES.rainfall, "normal"), source: "default" };
  }
  if (rainfall < 5) return { ...findScore(SCORE_TABLES.rainfall, "very_dry"), source: "weather" };
  if (rainfall < 20) return { ...findScore(SCORE_TABLES.rainfall, "dry"), source: "weather" };
  if (rainfall < 45) return { ...findScore(SCORE_TABLES.rainfall, "normal"), source: "weather" };
  if (rainfall < 80) return { ...findScore(SCORE_TABLES.rainfall, "good"), source: "weather" };
  return { ...findScore(SCORE_TABLES.rainfall, "excellent"), source: "weather" };
}

export function deriveHeatBucket(weather) {
  const temperature = toNumber(weather?.temperature_avg ?? weather?.last_30_days?.temperature_avg, NaN);
  if (!Number.isFinite(temperature)) {
    return { ...findScore(SCORE_TABLES.heat, "normal"), source: "default" };
  }
  if (temperature >= 32) return { ...findScore(SCORE_TABLES.heat, "severe"), source: "weather" };
  if (temperature >= 28) return { ...findScore(SCORE_TABLES.heat, "hot"), source: "weather" };
  if (temperature >= 18) return { ...findScore(SCORE_TABLES.heat, "normal"), source: "weather" };
  return { ...findScore(SCORE_TABLES.heat, "mild"), source: "weather" };
}

function getCultivarSuitability(cultivar, region) {
  const c = lower(cultivar);
  const r = lower(region);
  const northHints = ["bizerte", "zaghouan", "nabeul", "beja", "jendouba", "tunis", "north"];
  const centerSouthHints = ["sfax", "sousse", "mahdia", "kairouan", "gabes", "sidi bouzid", "south", "center"];
  const inNorth = northHints.some((token) => r.includes(token));
  const inCenterSouth = centerSouthHints.some((token) => r.includes(token));

  if (c.includes("chemlali")) {
    return {
      key: inCenterSouth ? "chemlali_fit" : "chemlali_outside",
      label: inCenterSouth ? "Chemlali in center/south" : "Chemlali outside suitable zone",
      score: inCenterSouth ? 1.03 : 0.97,
      source: "farm",
    };
  }
  if (c.includes("chetoui")) {
    return {
      key: inNorth ? "chetoui_fit" : "chetoui_outside",
      label: inNorth ? "Chetoui in north" : "Chetoui in center/south",
      score: inNorth ? 1.05 : 0.92,
      source: "farm",
    };
  }
  return { key: "unknown", label: "Unknown cultivar", score: 1.0, source: "default" };
}

function deriveIrrigationBucket(climateNotes, irrigationNotes) {
  const text = `${lower(climateNotes)} ${lower(irrigationNotes)}`.trim();
  if (!text) return { ...findScore(SCORE_TABLES.irrigation, "default"), source: "default" };
  if (text.includes("rainfed") || text.includes("dry") || text.includes("stressed")) {
    return { ...findScore(SCORE_TABLES.irrigation, "rainfed_stressed"), source: "farm" };
  }
  if (text.includes("limited") || text.includes("deficit")) {
    return { ...findScore(SCORE_TABLES.irrigation, "limited"), source: "farm" };
  }
  if (text.includes("strong") || text.includes("heavy")) {
    return { ...findScore(SCORE_TABLES.irrigation, "strong"), source: "farm" };
  }
  return { ...findScore(SCORE_TABLES.irrigation, "adequate"), source: "farm" };
}

function deriveDiseaseBucket(widgets, scans) {
  const alerts = toNumber(widgets?.disease_alerts, 0);
  const pending = toNumber(widgets?.pending_review_cases, 0);
  const diseaseScans = (scans || []).filter((scan) => String(scan.module_type || "").toLowerCase() === "disease_scan");
  const severeSignals = diseaseScans.filter((scan) => lower(scan.summary).includes("severe")).length;

  if (!widgets && !diseaseScans.length) {
    return { ...findScore(SCORE_TABLES.disease, "default"), source: "default" };
  }
  if (alerts >= 4 || pending >= 6 || severeSignals >= 2) {
    return { ...findScore(SCORE_TABLES.disease, "high"), source: "dashboard" };
  }
  if (alerts >= 2 || pending >= 3 || severeSignals >= 1) {
    return { ...findScore(SCORE_TABLES.disease, "moderate"), source: "dashboard" };
  }
  if (alerts >= 1) {
    return { ...findScore(SCORE_TABLES.disease, "low"), source: "dashboard" };
  }
  return { ...findScore(SCORE_TABLES.disease, "very_healthy"), source: "dashboard" };
}

function averageTreeAge(treeGroups) {
  const groups = Array.isArray(treeGroups) ? treeGroups : [];
  const ages = groups
    .map((group) => {
      if (group.age_mode === "exact" && toNumber(group.age_exact) > 0) return toNumber(group.age_exact);
      if (group.age_mode === "range") {
        const min = toNumber(group.age_min, NaN);
        const max = toNumber(group.age_max, NaN);
        if (Number.isFinite(min) && Number.isFinite(max) && min > 0 && max > 0) return (min + max) / 2;
      }
      return null;
    })
    .filter((age) => age != null);

  if (!ages.length) return null;
  return ages.reduce((sum, age) => sum + Number(age), 0) / ages.length;
}

function deriveAgeBucket(treeGroups) {
  const avgAge = averageTreeAge(treeGroups);
  if (avgAge == null) return { ...findScore(SCORE_TABLES.age, "default"), source: "default", avgAge: null };
  if (avgAge <= 3) return { ...findScore(SCORE_TABLES.age, "young"), source: "farm", avgAge };
  if (avgAge <= 8) return { ...findScore(SCORE_TABLES.age, "growing"), source: "farm", avgAge };
  if (avgAge <= 25) return { ...findScore(SCORE_TABLES.age, "mature"), source: "farm", avgAge };
  return { ...findScore(SCORE_TABLES.age, "old"), source: "farm", avgAge };
}

export function deriveAutoScores({ weather, farmProfile, dashboard, cultivar, region, irrigationNotes }) {
  const assumptions = [];
  const rain = deriveRainfallBucket(weather);
  const heat = deriveHeatBucket(weather);
  const cultivarScore = getCultivarSuitability(cultivar, region || farmProfile?.region);
  const irrigation = deriveIrrigationBucket(farmProfile?.climate_notes, irrigationNotes);
  const disease = deriveDiseaseBucket(dashboard?.widgets, dashboard?.recent_scans || []);
  const age = deriveAgeBucket(farmProfile?.tree_groups);

  if (rain.source === "default") assumptions.push("rainfall_unavailable");
  if (heat.source === "default") assumptions.push("heat_unavailable");
  if (cultivarScore.source === "default") assumptions.push("cultivar_unavailable");
  if (irrigation.source === "default") assumptions.push("irrigation_unavailable");
  if (disease.source === "default") assumptions.push("disease_unavailable");
  if (age.source === "default") assumptions.push("age_unavailable");

  return {
    assumptions,
    scores: {
      rainfall: rain,
      heat,
      cultivar: cultivarScore,
      irrigation,
      disease,
      age,
    },
  };
}

export function calculateProductionForecast({ yt1, yt2, yt3, autoScores }) {
  const Yt_1 = toNumber(yt1);
  const Yt_2 = toNumber(yt2);
  const Yt_3 = toNumber(yt3);
  const hasThreeYears = Yt_3 > 0;
  const baseYield = hasThreeYears
    ? 0.5 * Yt_1 + 0.3 * Yt_2 + 0.2 * Yt_3
    : 0.6 * Yt_1 + 0.4 * Yt_2;
  const denominator = Math.max((Yt_1 + Yt_2) / 2, 1);
  const bearingFactor = 1 + 0.25 * ((Yt_2 - Yt_1) / denominator);

  const R = autoScores.scores.rainfall.score;
  const T = autoScores.scores.heat.score;
  const C = autoScores.scores.cultivar.score;
  const I = autoScores.scores.irrigation.score;
  const D = autoScores.scores.disease.score;
  const A = autoScores.scores.age.score;

  const nextYearForecast = baseYield * bearingFactor * R * T * C * I * D * A;
  const lowRange = nextYearForecast * 0.9;
  const highRange = nextYearForecast * 1.1;

  const historyCount = hasThreeYears ? 3 : 2;
  const historyAverage = hasThreeYears ? (Yt_1 + Yt_2 + Yt_3) / 3 : (Yt_1 + Yt_2) / 2;
  const vsLastYearKg = nextYearForecast - Yt_1;
  const vsLastYearPct = Yt_1 > 0 ? (vsLastYearKg / Yt_1) * 100 : 0;
  const vsAverageKg = nextYearForecast - historyAverage;
  const vsAveragePct = historyAverage > 0 ? (vsAverageKg / historyAverage) * 100 : 0;

  const dataSignals = [
    Number.isFinite(toNumber(yt1, NaN)) && toNumber(yt1) > 0,
    Number.isFinite(toNumber(yt2, NaN)) && toNumber(yt2) > 0,
    hasThreeYears,
    autoScores.scores.rainfall.source !== "default",
    autoScores.scores.heat.source !== "default",
    autoScores.scores.cultivar.source !== "default",
    autoScores.scores.irrigation.source !== "default",
    autoScores.scores.disease.source !== "default",
    autoScores.scores.age.source !== "default",
  ];
  const dataCoverage = dataSignals.filter(Boolean).length / dataSignals.length;
  const assumptionPenalty = Math.min(autoScores.assumptions.length * 0.03, 0.18);
  const confidenceScore = Math.max(0.45, Math.min(0.9, 0.52 + dataCoverage * 0.35 - assumptionPenalty));
  const confidenceLabelKey = confidenceScore >= 0.8 ? "high" : confidenceScore >= 0.65 ? "medium" : "low";
  const confidenceLabel = confidenceLabelKey.charAt(0).toUpperCase() + confidenceLabelKey.slice(1);

  const multipliers = [
    { id: "bearing", labelKey: "bearing", label: "Alternate-bearing effect", value: bearingFactor },
    { id: "rainfall", labelKey: "rainfall", label: "Rainfall", value: R },
    { id: "heat", labelKey: "heat", label: "Heat stress", value: T },
    { id: "cultivar", labelKey: "cultivar", label: "Cultivar fit", value: C },
    { id: "irrigation", labelKey: "irrigation", label: "Irrigation", value: I },
    { id: "disease", labelKey: "disease", label: "Disease pressure", value: D },
    { id: "age", labelKey: "age", label: "Tree age profile", value: A },
  ];
  const keyDrivers = multipliers
    .map((item) => ({ ...item, impactPercent: (item.value - 1) * 100 }))
    .sort((a, b) => Math.abs(b.impactPercent) - Math.abs(a.impactPercent))
    .slice(0, 4);

  const trendIndicator = vsLastYearPct > 5 ? "up" : vsLastYearPct < -5 ? "down" : "stable";

  let recommendationKey = "stable";
  let recommendation =
    "Use this range for labor and processing planning, and update monthly with weather and disease changes.";
  if (trendIndicator === "down") {
    recommendationKey = "down";
    recommendation =
      "Yield outlook is constrained. Prioritize irrigation consistency, disease pressure control, and stress mitigation.";
  } else if (trendIndicator === "up") {
    recommendationKey = "up";
    recommendation =
      "Yield outlook is favorable. Plan logistics early and protect canopy/fruit health to preserve potential.";
  }
  if (confidenceLabelKey === "low") {
    recommendationKey = "low_confidence";
    recommendation =
      "Forecast confidence is limited. Add missing data (irrigation, tree age, or additional history) before major commitments.";
  }

  return {
    hasThreeYears,
    historyCount,
    baseYield,
    bearingFactor,
    nextYearForecast,
    lowRange,
    highRange,
    confidenceScore,
    confidenceLabel,
    confidenceLabelKey,
    trendIndicator,
    keyDrivers,
    recommendation,
    recommendationKey,
    chartLabelNext: "Next",
    comparisons: {
      vsLastYearKg,
      vsLastYearPct,
      vsAverageKg,
      vsAveragePct,
      historyAverage,
    },
    formulaInputs: { Yt_1, Yt_2, Yt_3, R, T, C, I, D, A },
  };
}
