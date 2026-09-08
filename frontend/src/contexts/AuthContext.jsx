import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import apiClient, { setActivityHandler, setUnauthorizedHandler } from "../api/client";

const AuthContext = createContext(null);

// Debe reflejar Config.SESSION_TIMEOUT en el backend (10 min de inactividad).
const SESSION_MS = 10 * 60 * 1000;
const WARNING_MS = 60 * 1000;
const TOKEN_KEY = "datil_token";
const USER_KEY = "datil_user";

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    const raw = localStorage.getItem(USER_KEY);
    return raw ? JSON.parse(raw) : null;
  });
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY));
  const [showWarning, setShowWarning] = useState(false);

  const warningTimer = useRef(null);
  const logoutTimer = useRef(null);

  const clearSession = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    setToken(null);
    setUser(null);
    setShowWarning(false);
    clearTimeout(warningTimer.current);
    clearTimeout(logoutTimer.current);
  }, []);

  const logout = useCallback(async () => {
    try {
      await apiClient.post("/api/auth/logout");
    } catch {
      // Se cierra la sesion local sin importar si el servidor respondio.
    }
    clearSession();
  }, [clearSession]);

  const scheduleTimers = useCallback(() => {
    clearTimeout(warningTimer.current);
    clearTimeout(logoutTimer.current);
    setShowWarning(false);
    warningTimer.current = setTimeout(() => setShowWarning(true), SESSION_MS - WARNING_MS);
    logoutTimer.current = setTimeout(clearSession, SESSION_MS);
  }, [clearSession]);

  useEffect(() => {
    setActivityHandler(() => {
      if (localStorage.getItem(TOKEN_KEY)) {
        scheduleTimers();
      }
    });
    setUnauthorizedHandler(clearSession);
  }, [scheduleTimers, clearSession]);

  useEffect(() => {
    if (token) {
      scheduleTimers();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  const login = useCallback(async (username, password) => {
    const { data } = await apiClient.post("/api/auth/login", { username, password });
    localStorage.setItem(TOKEN_KEY, data.token);
    localStorage.setItem(USER_KEY, JSON.stringify(data.user));
    setToken(data.token);
    setUser(data.user);
  }, []);

  const extendSession = useCallback(async () => {
    await apiClient.get("/api/auth/verify");
    scheduleTimers();
  }, [scheduleTimers]);

  return (
    <AuthContext.Provider
      value={{ user, token, isAuthenticated: Boolean(token), login, logout, extendSession, showWarning }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth debe usarse dentro de AuthProvider");
  return ctx;
}
