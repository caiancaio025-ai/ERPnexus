import { FormEvent, useEffect, useRef, useState } from "react";
import { ArrowRight, Eye, EyeOff, LockKeyhole, ShieldCheck, UserRound } from "lucide-react";

import { apiClient } from "../../shared/api/apiClient";

export type AuthUser = {
  id: number;
  name: string;
  email: string | null;
  username: string;
  role: string;
  modules: string[];
  is_active: boolean;
};

type AuthCardProps = {
  onLogin: (user: AuthUser) => void;
};

export function AuthCard({ onLogin }: AuthCardProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const firstLoginField = useRef<HTMLInputElement>(null);

  useEffect(() => {
    firstLoginField.current?.focus();
  }, []);

  async function submitLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError("");

    const data = new FormData(event.currentTarget);
    const identifier = String(data.get("identifier") ?? "").trim();
    const password = String(data.get("password") ?? "");

    try {
      const user = await apiClient.post<AuthUser>(
        "/auth/login",
        { identifier, password },
        { redirectOnUnauthorized: false },
      );
      onLogin(user);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Não foi possível entrar no sistema.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="auth-area" aria-label="Acesso ao SÊNTICO">
      <form className="auth-panel" onSubmit={submitLogin}>
        <header className="auth-panel__header">
          <span>ACESSO CORPORATIVO</span>
          <h2>Iniciar sessão</h2>
        </header>

        <label className="auth-field">
          <span>ID de acesso</span>
          <span className="auth-input">
            <UserRound size={20} aria-hidden="true" />
            <input
              ref={firstLoginField}
              name="identifier"
              autoComplete="username"
              disabled={loading}
              required
            />
          </span>
        </label>

        <label className="auth-field">
          <span>Senha</span>
          <span className="auth-input">
            <LockKeyhole size={19} aria-hidden="true" />
            <input
              name="password"
              type={showPassword ? "text" : "password"}
              autoComplete="current-password"
              disabled={loading}
              required
            />
            <button
              className="auth-password-toggle"
              type="button"
              aria-label={showPassword ? "Ocultar senha" : "Mostrar senha"}
              aria-pressed={showPassword}
              onClick={() => setShowPassword((value) => !value)}
              disabled={loading}
            >
              {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
            </button>
          </span>
        </label>

        {error && <p className="form-error" role="alert">{error}</p>}

        <button className="auth-submit" type="submit" disabled={loading}>
          <span>{loading ? "Entrando..." : "Acessar sistema"}</span>
          {!loading && <ArrowRight size={21} aria-hidden="true" />}
        </button>

        <div className="auth-note">
          <ShieldCheck size={22} aria-hidden="true" />
          <p>Acessos são criados e controlados pelo perfil <strong>Gestão</strong>.</p>
        </div>
      </form>
    </section>
  );
}
