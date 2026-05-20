import i18n from "../i18n";

const configuredApiBase = import.meta.env.VITE_API_BASE?.trim();
const API_BASE = configuredApiBase
  ? configuredApiBase.replace(/\/+$/, "")
  : "/api";

async function parseApiResponse(response) {
  const text = await response.text();
  if (!text) return {};
  try {
    return JSON.parse(text);
  } catch {
    return { detail: text };
  }
}

function extractApiError(data, response) {
  if (typeof data?.message === "string" && data.message.trim()) return data.message;
  if (typeof data?.detail === "string" && data.detail.trim()) return data.detail;
  if (Array.isArray(data?.detail) && data.detail.length) {
    return data.detail
      .map((item) => item?.msg || item?.message || JSON.stringify(item))
      .join(" ");
  }
  if (typeof data?.error?.message === "string" && data.error.message.trim()) return data.error.message;
  return i18n.t("common.requestFailed", { status: response.status });
}

async function request(path, options = {}) {
  let response;
  try {
    response = await fetch(`${API_BASE}${path}`, options);
  } catch (error) {
    throw new Error(i18n.t("common.backendUnavailable"));
  }
  const data = await parseApiResponse(response);
  if (!response.ok) {
    throw new Error(extractApiError(data, response));
  }
  return data;
}

export const api = {
  parseApiResponse,

  getFarmProfiles() {
    return request("/farm/profile");
  },

  createFarmProfile(payload) {
    return request("/farm/profile", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  },

  getFarmProfile(farmId) {
    return request(`/farm/profile/${farmId}`);
  },

  updateFarmProfile(farmId, payload) {
    return request(`/farm/profile/${farmId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  },

  createTreeGroup(farmId, payload) {
    return request(`/farm/${farmId}/tree-groups`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  },

  updateTreeGroup(farmId, groupId, payload) {
    return request(`/farm/${farmId}/tree-groups/${groupId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  },

  deleteTreeGroup(farmId, groupId) {
    return request(`/farm/${farmId}/tree-groups/${groupId}`, { method: "DELETE" });
  },

  getFarmDashboard(farmId) {
    return request(`/farm/${farmId}/dashboard`);
  },

  getFarmScans(farmId, limit = 200) {
    return request(`/farm/${farmId}/scans?limit=${limit}`);
  },

  createFarmScan(farmId, payload) {
    return request(`/farm/${farmId}/scans`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  },

  updateFarmScanStatus(farmId, scanId, status) {
    return request(`/farm/${farmId}/scans/${scanId}/status`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status }),
    });
  },

  getFarmAlerts(farmId, includeResolved = false) {
    return request(`/farm/${farmId}/alerts?include_resolved=${includeResolved ? "true" : "false"}`);
  },

  getFarmNotes(farmId) {
    return request(`/farm/${farmId}/notes`);
  },

  createFarmNote(farmId, payload) {
    return request(`/farm/${farmId}/notes`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  },

  updateFarmNoteStatus(farmId, noteId, status) {
    return request(`/farm/${farmId}/notes/${noteId}/status`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status }),
    });
  },

  async detectOlives(file, options = {}) {
    const form = new FormData();
    form.append("file", file);
    if (options.conf != null) form.append("conf", String(options.conf));
    if (options.iou != null) form.append("iou", String(options.iou));
    if (options.imgsz != null) form.append("imgsz", String(options.imgsz));
    return request("/detect-olives", { method: "POST", body: form });
  },

  async analyzeImage(file, options = {}) {
    const form = new FormData();
    form.append("file", file);
    if (options.language) form.append("language", options.language);
    if (options.cultivar) form.append("cultivar", options.cultivar);
    if (options.target_style) form.append("target_style", options.target_style);
    if (options.location) form.append("location", options.location);
    if (options.sample_date) form.append("sample_date", options.sample_date);
    if (options.week_no) form.append("week_no", String(options.week_no));
    return request("/analyze-image", { method: "POST", body: form });
  },

  async predictLeafDisease(file, options = {}) {
    const form = new FormData();
    form.append("file", file);
    if (options.language) form.append("language", options.language);
    return request("/predict-leaf-disease", { method: "POST", body: form });
  },

  async diseaseScanExpert(file, options = {}) {
    const form = new FormData();
    form.append("file", file);
    if (options.language) form.append("language", options.language);
    return request("/disease-scan-expert", { method: "POST", body: form });
  },

  async predictHarvestImage(file, options = {}) {
    const form = new FormData();
    form.append("file", file);
    if (options.language) form.append("language", options.language);
    if (options.cultivar) form.append("cultivar", options.cultivar);
    if (options.intended_use) form.append("intended_use", options.intended_use);
    if (options.target_style) form.append("target_style", options.target_style);
    if (options.location) form.append("location", options.location);
    if (options.latitude != null) form.append("latitude", String(options.latitude));
    if (options.longitude != null) form.append("longitude", String(options.longitude));
    if (options.sample_date) form.append("sample_date", options.sample_date);
    if (options.tree_age != null) form.append("tree_age", String(options.tree_age));
    if (options.irrigation_notes) form.append("irrigation_notes", options.irrigation_notes);
    if (options.disease) form.append("disease", options.disease);
    if (options.health_score != null) form.append("health_score", String(options.health_score));
    return request("/predict-harvest-image", { method: "POST", body: form });
  },

  chat(message, language = "fr") {
    return request("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, language }),
    });
  },

  getWeatherInsights(latitude, longitude) {
    return request(`/weather-insights?latitude=${latitude}&longitude=${longitude}`);
  },
};
