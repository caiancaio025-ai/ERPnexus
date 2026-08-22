import { FormEvent, useEffect, useRef, useState } from "react";

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
    <section className="auth-area" aria-label="Acesso ao NEXUS">
      <div className="auth-card">
        <form className="auth-face auth-front" onSubmit={submitLogin}>
          <header>
            <span>ACESSO CORPORATIVO</span>
            <h2>INICIAR SESSÃO</h2>
          </header>

          <label>
            ID de acesso
            <input
              ref={firstLoginField}
              name="identifier"
              autoComplete="username"
              disabled={loading}
              required
            />
          </label>

          <label>
            Senha
            <input
              name="password"
              type="password"
              autoComplete="current-password"
              disabled={loading}
              required
            />
          </label>

          {error && <p className="form-error" role="alert">{error}</p>}

          <button className="primary" type="submit" disabled={loading}>
            {loading ? "Entrando..." : "Acessar sistema"}
          </button>

          <p className="register-note">Acessos são criados e controlados pelo perfil Gestão.</p>
        </form>
      </div>
    </section>
  );
}
