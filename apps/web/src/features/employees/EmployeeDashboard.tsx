import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  ArrowLeft,
  KeyRound,
  Pencil,
  Plus,
  RefreshCw,
  Search,
  ShieldCheck,
  UserRound,
  UsersRound,
  X,
} from "lucide-react";
import { useNavigate } from "react-router-dom";

import type { AuthUser } from "../auth/AuthCard";
import { apiClient } from "../../shared/api/apiClient";
import "./employees.css";

type AccessRole = "lab" | "gestao" | "admin";

type Collaborator = {
  employee_id: number | null;
  user_id: number;
  first_name: string;
  last_name: string;
  full_name: string;
  phone: string | null;
  role: AccessRole;
  username: string;
  is_active: boolean;
};

type Props = { user: AuthUser; onLogout: () => void };

const roleLabels: Record<AccessRole, string> = {
  lab: "LAB",
  gestao: "GESTÃO",
  admin: "ADM",
};

function initials(value: string) {
  return value
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("");
}

function normalizeRole(role: string): AccessRole {
  if (role === "super_admin") return "gestao";
  if (role === "tecnico") return "lab";
  if (role === "admin" || role === "gestao" || role === "lab") return role;
  return "lab";
}

export function EmployeeDashboard({ user, onLogout }: Props) {
  const navigate = useNavigate();
  const [items, setItems] = useState<Collaborator[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<Collaborator | null>(null);

  // super_admin é o usuário bootstrap legado e equivale à Gestão.
  const canManage = ["gestao", "super_admin"].includes(user.role);

  async function load() {
    setLoading(true);
    setError("");
    try {
      const response = await apiClient.get<Collaborator[]>("/api/employees/access");
      setItems(response);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Não foi possível carregar os colaboradores.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  const filtered = useMemo(() => {
    const term = search.trim().toLocaleLowerCase("pt-BR");
    if (!term) return items;
    return items.filter((item) =>
      [item.full_name, item.phone || "", item.username, roleLabels[normalizeRole(item.role)]]
        .join(" ")
        .toLocaleLowerCase("pt-BR")
        .includes(term),
    );
  }, [items, search]);

  return (
    <div className="employees-shell">
      <aside className="employees-sidebar">
        <button className="employees-brand" onClick={() => navigate("/painel")}>
          <span>N</span><strong>NEXUS</strong>
        </button>
        <button onClick={() => navigate("/painel")}><ArrowLeft size={18}/>Painel</button>
        <button className="active"><UsersRound size={18}/>Colaboradores</button>
        <div className="employees-user">
          <span>{initials(user.name)}</span>
          <div><strong>{user.name}</strong><small>{user.role === "super_admin" ? "gestao" : user.role}</small></div>
        </div>
        <button onClick={onLogout}>Sair do sistema</button>
      </aside>

      <main className="employees-main">
        <header className="employees-header">
          <div>
            <small>ACESSOS AO NEXUS</small>
            <h1>Colaboradores</h1>
            <p>Você cria o ID, define o perfil e controla o acesso ao sistema.</p>
          </div>
          {canManage && (
            <button className="employees-primary" onClick={() => setCreating(true)}>
              <Plus size={18}/>Novo colaborador
            </button>
          )}
        </header>

        <section className="employees-summary">
          <article><span>Total</span><strong>{items.length}</strong></article>
          <article><span>Ativos</span><strong>{items.filter((item) => item.is_active).length}</strong></article>
          <article><span>Desativados</span><strong>{items.filter((item) => !item.is_active).length}</strong></article>
        </section>

        <section className="employees-panel">
          <div className="employees-toolbar">
            <label>
              <Search size={18}/>
              <input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Buscar nome, telefone, ID ou perfil..."
              />
            </label>
            <button onClick={() => void load()}><RefreshCw size={17}/>Atualizar</button>
          </div>

          {!canManage && (
            <div className="employees-info">
              <ShieldCheck size={17}/>
              Somente o perfil Gestão pode cadastrar, alterar senha, trocar perfil ou desativar colaboradores.
            </div>
          )}

          {error && <div className="employees-error">{error}</div>}

          <div className="employees-table-wrap">
            <table>
              <thead>
                <tr>
                  <th>COLABORADOR</th>
                  <th>TELEFONE</th>
                  <th>PERFIL</th>
                  <th>ID DE ACESSO</th>
                  <th>STATUS</th>
                  {canManage && <th>AÇÕES</th>}
                </tr>
              </thead>
              <tbody>
                {filtered.map((item) => (
                  <tr key={item.user_id}>
                    <td><strong>{item.full_name}</strong></td>
                    <td>{item.phone || "—"}</td>
                    <td><span className={`employee-role employee-role--${normalizeRole(item.role)}`}>{roleLabels[normalizeRole(item.role)]}</span></td>
                    <td><code>{item.username}</code></td>
                    <td><span className={item.is_active ? "employee-status active" : "employee-status inactive"}>{item.is_active ? "Ativo" : "Desativado"}</span></td>
                    {canManage && (
                      <td>
                        <button className="employee-manage" onClick={() => setEditing(item)}>
                          <Pencil size={15}/>Gerenciar
                        </button>
                      </td>
                    )}
                  </tr>
                ))}
                {!loading && !filtered.length && (
                  <tr><td colSpan={canManage ? 6 : 5} className="employees-empty">Nenhum colaborador encontrado.</td></tr>
                )}
              </tbody>
            </table>
          </div>
          {loading && <div className="employees-loading">Carregando colaboradores...</div>}
        </section>
      </main>

      {creating && (
        <CollaboratorModal
          mode="create"
          onClose={() => setCreating(false)}
          onSaved={async () => { setCreating(false); await load(); }}
        />
      )}
      {editing && (
        <CollaboratorModal
          mode="edit"
          collaborator={editing}
          currentUserId={user.id}
          onClose={() => setEditing(null)}
          onSaved={async () => { setEditing(null); await load(); }}
        />
      )}
    </div>
  );
}

type CollaboratorModalProps = {
  mode: "create" | "edit";
  collaborator?: Collaborator;
  currentUserId?: number;
  onClose: () => void;
  onSaved: () => Promise<void>;
};

function CollaboratorModal({ mode, collaborator, currentUserId, onClose, onSaved }: CollaboratorModalProps) {
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [role, setRole] = useState<AccessRole>(collaborator ? normalizeRole(collaborator.role) : "lab");
  const [active, setActive] = useState(collaborator?.is_active ?? true);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError("");
    const form = new FormData(event.currentTarget);

    const payload = {
      first_name: String(form.get("first_name") || "").trim(),
      last_name: String(form.get("last_name") || "").trim(),
      phone: String(form.get("phone") || "").trim(),
      role,
      username: String(form.get("username") || "").trim().toLowerCase(),
      ...(mode === "create" || String(form.get("password") || "")
        ? { password: String(form.get("password") || "") }
        : {}),
      ...(mode === "edit" ? { is_active: active } : {}),
    };

    try {
      if (mode === "create") {
        await apiClient.post("/api/employees/access", payload);
      } else if (collaborator) {
        await apiClient.put(`/api/employees/access/${collaborator.user_id}`, payload);
      }
      await onSaved();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Não foi possível salvar o colaborador.");
    } finally {
      setSaving(false);
    }
  }

  const editingSelf = mode === "edit" && collaborator?.user_id === currentUserId;

  return (
    <div className="employee-modal-backdrop">
      <section className="employee-modal employee-modal--simple">
        <header>
          <div>
            <small>{mode === "create" ? "NOVO ACESSO" : "GERENCIAR ACESSO"}</small>
            <h2>{mode === "create" ? "Cadastrar colaborador" : collaborator?.full_name}</h2>
            <p>Somente os dados necessários para acessar e trabalhar no NEXUS.</p>
          </div>
          <button onClick={onClose}><X size={22}/></button>
        </header>

        <form onSubmit={submit}>
          <div className="employee-form-section">
            <div className="employee-form-grid">
              <label>Nome<input name="first_name" defaultValue={collaborator?.first_name || ""} minLength={2} required/></label>
              <label>Sobrenome<input name="last_name" defaultValue={collaborator?.last_name || ""} minLength={2} required/></label>
              <label>Telefone<input name="phone" defaultValue={collaborator?.phone || ""} minLength={8} required placeholder="(81) 99999-9999"/></label>
              <label>Perfil / setor
                <select value={role} onChange={(event) => setRole(event.target.value as AccessRole)}>
                  <option value="lab">LAB</option>
                  <option value="gestao">GESTÃO</option>
                  <option value="admin">ADM</option>
                </select>
              </label>
              <label>ID de acesso<input name="username" defaultValue={collaborator?.username || ""} minLength={3} maxLength={30} pattern="[a-zA-Z0-9._-]+" required autoComplete="off"/></label>
              <label>{mode === "create" ? "Senha" : "Nova senha (opcional)"}
                <input
                  name="password"
                  type="password"
                  minLength={8}
                  maxLength={64}
                  required={mode === "create"}
                  placeholder={mode === "create" ? "Mínimo 8 caracteres" : "Deixe vazio para manter"}
                  autoComplete="new-password"
                />
              </label>
            </div>

            <div className="employee-role-note">
              <ShieldCheck size={18}/>
              <div>
                <strong>{roleLabels[role]}</strong>
                <span>
                  {role === "lab"
                    ? "Sem Financeiro e sem permissão para criar, alterar ou emitir orçamento."
                    : role === "gestao"
                      ? "Acesso geral e gestão exclusiva dos colaboradores."
                      : "Acesso geral ao ERP, sem administração de colaboradores."}
                </span>
              </div>
            </div>

            {mode === "edit" && (
              <div className="employee-account-state">
                <div>
                  <strong>Status do acesso</strong>
                  <span>{active ? "O colaborador consegue entrar no sistema." : "O login está bloqueado."}</span>
                </div>
                <button
                  type="button"
                  className={active ? "danger" : "success"}
                  disabled={editingSelf && active}
                  onClick={() => setActive((value) => !value)}
                  title={editingSelf && active ? "Você não pode desativar seu próprio acesso." : undefined}
                >
                  {active ? "Desativar" : "Reativar"}
                </button>
              </div>
            )}
          </div>

          <div className="employee-password-tip"><KeyRound size={17}/><span>Senha: mínimo de <strong>8 caracteres</strong>. Recomendado usar 10 a 12 para os acessos entregues aos colaboradores.</span></div>
          {error && <div className="employees-error">{error}</div>}

          <footer>
            <button type="button" onClick={onClose}>Cancelar</button>
            <button type="submit" className="employees-primary" disabled={saving}>
              {saving ? "Salvando..." : mode === "create" ? "Criar acesso" : "Salvar alterações"}
            </button>
          </footer>
        </form>
      </section>
    </div>
  );
}
