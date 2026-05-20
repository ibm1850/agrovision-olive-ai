function toNumber(value) {
  const n = Number(value);
  return Number.isFinite(n) ? n : 0;
}

export function formatKg(value) {
  const kg = Math.round(toNumber(value));
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(kg);
}

export function formatTons(value) {
  const tons = toNumber(value) / 1000;
  const digits = Math.abs(tons) >= 10 ? 1 : 2;
  return new Intl.NumberFormat("en-US", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(tons);
}

export function formatKgWithTons(value) {
  const n = toNumber(value);
  if (!n) return "--";
  return `${formatKg(n)} kg (${formatTons(n)} t)`;
}

export function formatKgRangeWithTons(low, high) {
  const l = toNumber(low);
  const h = toNumber(high);
  if (!l && !h) return "--";
  return `${formatKg(l)}-${formatKg(h)} kg (${formatTons(l)}-${formatTons(h)} t)`;
}

export function formatDeltaKg(value) {
  const n = toNumber(value);
  const sign = n > 0 ? "+" : "";
  return `${sign}${formatKg(n)} kg`;
}

export function formatPercent(value) {
  const n = toNumber(value);
  const sign = n > 0 ? "+" : "";
  return `${sign}${n.toFixed(1)}%`;
}

