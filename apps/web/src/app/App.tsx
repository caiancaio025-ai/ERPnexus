import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import type { AuthUser } from "../features/auth/AuthCard";
import { apiClient } from "../shared/api/apiClient";
import { ApiError } from "../shared/api/apiError";
import { AppRouter } from "./router/AppRouter";
import { revokeDevicePush } from "../shared/notifications/pushClient";
import { SeasonalDecorations } from "../shared/theme/SeasonalDecorations";

export function App() {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [checking, setChecking] = useState(true);
  const [authError, setAuthError] = useState("");
  const navigate = useNavigate();

  async function checkSession() {
    setChecking(true); setAuthError("");
    try { setUser(await apiClient.get<AuthUser>("/api/auth/me", { redirectOnUnauthorized: false })); }
    catch (cause) {
      if (cause instanceof ApiError && (cause.status === 401 || cause.status === 403)) setUser(null);
      else setAuthError(cause instanceof Error ? cause.message : "Não foi possível verificar sua sessão.");
    } finally { setChecking(false); }
  }

  useEffect(() => { void checkSession(); }, []);

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
      // O computador compartilhado deixa de receber alertas deste usuário após Sair.
      await revokeDevicePush().catch(() => undefined);
      await apiClient.post<void>("/api/auth/logout", undefined, { redirectOnUnauthorized: false });
    } finally {
      setUser(null);
      navigate("/login", { replace: true });
    }
  }

  if (authError) return <main className="loading-screen"><section role="alert"><h1>Conexão temporariamente indisponível</h1><p>{authError}</p><button type="button" onClick={() => void checkSession()}>Tentar conectar novamente</button></section></main>;

  if (checking) return <main className="loading-screen">Carregando SÊNTICO...</main>;

  return <>
    <AppRouter user={user} onLogin={handleLogin} onLogout={logout} />
    {user && <SeasonalDecorations />}
  </>;
}
