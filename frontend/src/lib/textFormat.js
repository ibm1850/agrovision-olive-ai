function cleanMojibake(text) {
  return String(text || "")
    .replace(/\uFFFD/g, "")
    .replace(/Â\s*°/g, "\u00B0")
    .replace(/Â·/g, "\u00B7")
    .replace(/\s*[•\u00B7]\s*/g, " \u00B7 ")
    .replace(/\s{2,}/g, " ")
    .trim();
}

export function sanitizeText(value) {
  if (value == null) return "";
  return cleanMojibake(value);
}

export function formatMetaLine(parts = []) {
  const cleaned = parts
    .map((part) => sanitizeText(part))
    .filter(Boolean);
  return cleaned.join(" \u00B7 ");
}

export function formatTemperature(value) {
  if (value == null || value === "") return "--";
  const num = Number(value);
  const formatted = Number.isFinite(num) ? num.toFixed(1).replace(/\.0$/, "") : sanitizeText(value);
  return `${formatted}\u00B0C`;
}
