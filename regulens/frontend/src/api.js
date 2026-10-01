import axios from "axios";

const api = axios.create({ baseURL: import.meta.env.VITE_API_URL || "/api" });

api.interceptors.request.use((cfg) => {
  const t = localStorage.getItem("token");
  if (t) cfg.headers.Authorization = `Bearer ${t}`;
  return cfg;
});

api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err.response?.status === 401 && !err.config.url.startsWith("/auth/login")) {
      localStorage.removeItem("token");
      if (location.pathname !== "/login") location.href = "/login";
    }
    return Promise.reject(err);
  }
);

export const errMsg = (e) => e?.response?.data?.detail?.[0]?.msg || e?.response?.data?.detail || "Something went wrong. Please try again.";

export async function download(url, filename) {
  const res = await api.get(url, { responseType: "blob" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(res.data);
  a.download = filename;
  a.click();
  URL.revokeObjectURL(a.href);
}

export default api;
