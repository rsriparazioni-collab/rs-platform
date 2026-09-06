import axios from "axios";

// Auth via httpOnly cookie (gu_token) impostato dal backend - niente token in localStorage
const api = axios.create({
  baseURL: `${process.env.REACT_APP_BACKEND_URL}/api`,
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
