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
  const [register, setRegister] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const firstLoginField = useRef<HTMLInputElement>(null);
  const firstRegisterField = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    setError("");

    if (register) {
      firstRegisterField.current?.focus();
      return;
    }

    firstLoginField.current?.focus();
  }, [register]);

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
        {
          identifier,
          password,
        },
        {
          redirectOnUnauthorized: false,
        },
      );

      onLogin(user);
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Não foi possível entrar no sistema.",
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="auth-area" aria-label="Acesso ao NEXUS">
      <p className="sr-only" aria-live="polite">
        {register
          ? "Formulário de cadastro controlado"
          : "Formulário de login"}
      </p>

      <div className={`auth-card ${register ? "is-flipped" : ""}`}>
        <form
          className="auth-face auth-front"
          onSubmit={submitLogin}
          aria-hidden={register}
        >
          <header>
            <span>ACESSO CORPORATIVO</span>
            <h2>INICIAR SESSÃO</h2>
          </header>

          <label>
            ID ou e-mail
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

          {error && (
            <p className="form-error" role="alert">
              {error}
            </p>
          )}

          <button className="primary" type="submit" disabled={loading}>
            {loading ? "Entrando..." : "Acessar sistema"}
          </button>

          <button
            className="link-button"
            type="button"
            onClick={() => setRegister(true)}
            disabled={loading}
          >
            Cadastrar usuário
          </button>
        </form>

        <form
          className="auth-face auth-back"
          onSubmit={(event) => event.preventDefault()}
          aria-hidden={!register}
        >
          <header>
            <span>CADASTRO CONTROLADO</span>
            <h2>Solicitar acesso</h2>
          </header>

          <p className="register-note">
            O cadastro será disponibilizado em Configurações, com definição
            de perfil e módulos pelo administrador.
          </p>

          <button
            ref={firstRegisterField}
            className="link-button"
            type="button"
            onClick={() => setRegister(false)}
          >
            Voltar ao login
          </button>
        </form>
      </div>
    </section>
  );
}