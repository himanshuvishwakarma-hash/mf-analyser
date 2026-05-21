import axios from "axios";

const baseURL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api/v1";

export const api = axios.create({
  baseURL,
  timeout: 30000,
  headers: { "Content-Type": "application/json" },
});

api.interceptors.response.use(
  (r) => r,
  (err) => {
    // Centralised error log; replace with Sentry once wired
    if (err.response) {
      console.error(`API ${err.response.status}: ${err.config.url}`, err.response.data);
    } else {
      console.error("API network error", err.message);
    }
    return Promise.reject(err);
  },
);

export const fundsApi = {
  search: (q, limit = 20) => api.get("/funds/search", { params: { q, limit } }),
  list: (params) => api.get("/funds/list", { params }),
  detail: (schemeCode) => api.get(`/funds/${schemeCode}`),
  nav: (schemeCode, params) => api.get(`/funds/${schemeCode}/nav`, { params }),
  score: (schemeCode) => api.get(`/funds/${schemeCode}/score`),
  compare: (codes) => api.post("/funds/compare", codes),
  // Report exports (Phase D) - return blobs for browser download.
  report: (schemeCode, format = "docx", audience = "client") =>
    api.get(`/funds/${schemeCode}/report`, {
      params: { format, audience },
      responseType: "blob",
      timeout: 90000,
    }),
  compareReport: (codes, format = "docx") =>
    api.post(
      "/funds/compare/report",
      { scheme_codes: codes, format },
      { responseType: "blob", timeout: 90000 },
    ),
};

export const calculatorApi = {
  sip: (req) => api.post("/calculator/sip", req),
  lumpsum: (req) => api.post("/calculator/lumpsum", req),
};

export const healthApi = {
  ping: () => api.get("/health"),
  deep: () => api.get("/health/deep"),
};

export const adminApi = {
  // No-auth status check used by first-boot modal.
  seedStatus: () => api.get("/admin/seed-status"),
  // Token-gated cascade trigger.
  runCascade: (token) =>
    api.post("/admin/run-cascade", null, { headers: { "X-Admin-Token": token } }),
};
