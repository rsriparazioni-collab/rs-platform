import { createContext, useContext, useEffect, useMemo, useState } from "react";
import api from "../lib/api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);

  useEffect(() => {
    api.get("/auth/me")
      .then((res) => setUser(res.data))
      .catch(() => setUser(false));
  }, []);

  // Heartbeat: mentre l'utente lavora (mouse/tastiera/touch) rinnova la sessione ogni 5 minuti
  useEffect(() => {
    if (!user) return undefined;
    let last = Date.now();
    let attivo = false;
    const segna = () => { attivo = true; };
    const eventi = ["mousemove", "keydown", "click", "touchstart", "scroll"];
    eventi.forEach((e) => window.addEventListener(e, segna, { passive: true }));
    const id = setInterval(() => {
      if (attivo && Date.now() - last >= 5 * 60 * 1000) {
        attivo = false;
        last = Date.now();
        api.get("/auth/me").catch(() => {});
      }
    }, 30000);
    return () => { clearInterval(id); eventi.forEach((e) => window.removeEventListener(e, segna)); };
  }, [user]);

  const login = async (email, password) => {
    const res = await api.post("/auth/login", { email, password });
    if (res.data.mfa_required) return { mfaToken: res.data.mfa_token };
    setUser(res.data.user);
    return res.data.user;
  };

  const loginMfa = async (mfaToken, code) => {
    const res = await api.post("/auth/login/mfa", { mfa_token: mfaToken, code });
    setUser(res.data.user);
    return res.data.user;
  };

  const logout = async () => {
    try {
      await api.post("/auth/logout");
    } catch (e) {
      console.warn("Logout: sessione già scaduta lato server", e);
    }
    setUser(false);
  };

  const value = useMemo(() => ({ user, setUser, login, loginMfa, logout }), [user]);

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
