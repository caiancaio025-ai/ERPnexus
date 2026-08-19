import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import type { AuthUser } from "../features/auth/AuthCard";
import { apiClient } from "../shared/api/apiClient";
import { AppRouter } from "./router/AppRouter";

export function App() {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [checking, setChecking] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    apiClient.get<AuthUser>("/api/auth/me", { redirectOnUnauthorized: false })
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setChecking(false));
  }, []);

  useEffect(() => {
    const expireSession = () => {
      setUser(null);
      navigate("/login", { replace: true });
    };

    window.addEventListener("nexus:session-expired", expireSession);
    return () => window.removeEventListener("nexus:session-expired", expireSession);
  }, [navigate]);

  function handleLogin(authenticatedUser: AuthUser) {
    setUser(authenticatedUser);
    navigate("/painel", { replace: true });
  }

  async function logout() {
    try {
      await apiClient.post<void>("/api/auth/logout", undefined, { redirectOnUnauthorized: false });
    } finally {
      setUser(null);
      navigate("/login", { replace: true });
    }
  }

  if (checking) return <main className="loading-screen">Carregando NEXUS...</main>;

  return <AppRouter user={user} onLogin={handleLogin} onLogout={logout} />;
}
