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

  const value = useMemo(() => ({ user, login, loginMfa, logout }), [user]);

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
