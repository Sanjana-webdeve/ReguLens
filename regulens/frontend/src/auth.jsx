import { createContext, useContext, useEffect, useState } from "react";
import api from "./api";

const Ctx = createContext(null);
export const useAuth = () => useContext(Ctx);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(!!localStorage.getItem("token"));

  useEffect(() => {
    if (!localStorage.getItem("token")) return;
    api.get("/auth/me").then((r) => setUser(r.data)).catch(() => localStorage.removeItem("token")).finally(() => setLoading(false));
  }, []);

  const login = async (email, password) => {
    const r = await api.post("/auth/login", { email, password });
    localStorage.setItem("token", r.data.access_token);
    setUser(r.data.user);
  };
  const logout = async () => {
    try { await api.post("/auth/logout"); } catch {}
    localStorage.removeItem("token");
    setUser(null);
  };
  const can = (...roles) => user && roles.includes(user.role);

  return <Ctx.Provider value={{ user, loading, login, logout, can }}>{children}</Ctx.Provider>;
}
