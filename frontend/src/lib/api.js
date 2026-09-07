import axios from "axios";

// Auth via httpOnly cookie (gu_token) impostato dal backend - niente token in localStorage
// Su qualsiasi dominio servito dall'ingress (preview, produzione, dominio custom) /api e' same-origin:
// il cookie viaggia sempre. Solo in dev locale (localhost:3000) si usa l'URL assoluto del backend.
const isLocalDev = ["localhost", "127.0.0.1"].includes(window.location.hostname);
const baseURL = isLocalDev ? `${process.env.REACT_APP_BACKEND_URL}/api` : `${window.location.origin}/api`;
const api = axios.create({
  baseURL,
  withCredentials: true,
});

api.interceptors.response.use(
  (res) => res,
  (err) => {
    const url = err.config?.url || "";
    if (err.response?.status === 401 && !url.includes("/auth/") && window.location.pathname !== "/login") {
      window.location.href = "/login";
    }
    return Promise.reject(err);
  }
);

export function apiError(e, fallback = "Si è verificato un errore") {
  const status = e?.response?.status;
  if (status && status >= 500) return fallback;
  const detail = e?.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((d) => d.msg || JSON.stringify(d)).join(" ");
  return fallback;
}

export const downloadBlob = async (path, filename) => {
  const res = await api.get(path, { responseType: "blob" });
  const url = URL.createObjectURL(res.data);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
};

export default api;
