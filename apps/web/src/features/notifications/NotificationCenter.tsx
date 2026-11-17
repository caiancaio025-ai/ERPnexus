import { useCallback, useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";
import { Activity, ArrowLeft, ArrowUpRight, Bell, Boxes, CalendarDays, Check, CheckCheck, ChevronDown, ChevronLeft, ChevronRight, FileText, FilterX, FlaskConical, RefreshCw, Search, ShoppingCart, SlidersHorizontal, UsersRound, WalletCards } from "lucide-react";
import { useNavigate } from "react-router-dom";

import { apiClient } from "../../shared/api/apiClient";
import { SenticoSidebar } from "../../shared/ui/SenticoSidebar";
import type { AuthUser } from "../auth/AuthCard";
import type { NotificationItem } from "../dashboard/types";
import { formatarNumeroOS, textoEmPortugues } from "../../shared/i18n/portugues";
import "./notification-center.css";

type Props = { user: AuthUser; onLogout: () => void };
type History = { items: NotificationItem[]; unread_count: number; total: number; page: number; page_size: number };
type Actor = { id: number; name: string };
type Filters = {
  search: string; module: string; action: string; actor_id: string;
  work_order: string; date_from: string; date_to: string; unread_only: boolean;
};

const initialFilters: Filters = { search: "", module: "", action: "", actor_id: "", work_order: "", date_from: "", date_to: "", unread_only: false };
const moduleOptions = [
  { value: "laboratorio", label: "Laboratório" },
  { value: "orcamentos", label: "Orçamentos" },
  { value: "compras", label: "Compras e materiais" },
  { value: "estoque", label: "Estoque" },
  { value: "comercial", label: "Comercial" },
  { value: "financeiro", label: "Financeiro" },
  { value: "colaboradores", label: "Colaboradores" },
  { value: "configuracoes", label: "Configurações" },
];
const actionOptions = [
  { value: "os_created", label: "OS criada" },
  { value: "os_updated", label: "OS atualizada" },
  { value: "os_status_changed", label: "Status da OS" },
  { value: "analysis_completed", label: "Análise concluída" },
  { value: "substatus_changed", label: "Etapa da OS" },
  { value: "quote_created", label: "Orçamento criado" },
  { value: "quote_updated", label: "Orçamento editado" },
  { value: "quote_issued", label: "Orçamento emitido" },
  { value: "material_requested", label: "Material solicitado" },
  { value: "material_approved", label: "Material aprovado" },
  { value: "material_purchased", label: "Material comprado" },
  { value: "material_received", label: "Material recebido" },
  { value: "material_delivered", label: "Entrega ao laboratório" },
  { value: "purchase_created", label: "Pedido registrado" },
  { value: "purchase_deleted", label: "Compra excluída" },
  { value: "finance_entry_deleted", label: "Lançamento excluído" },
  { value: "finance_entry_settled", label: "Baixa financeira" },
  { value: "finance_entry_reopened", label: "Baixa estornada" },
  { value: "painting_created", label: "Pintura preparada" },
  { value: "painting_sent", label: "Material enviado à pintura" },
  { value: "painting_returned", label: "Pintura recebida" },
  { value: "customer_created", label: "Cliente cadastrado" },
  { value: "customer_updated", label: "Cliente atualizado" },
  { value: "user_created", label: "Usuário cadastrado" },
  { value: "user_updated", label: "Usuário alterado" },
  { value: "user_deactivated", label: "Usuário desativado" },
  { value: "purchase_received", label: "Compra entregue" },
  { value: "inventory_receipt", label: "Entrada no estoque" },
  { value: "inventory_issue", label: "Saída do estoque" },
  { value: "inventory_return", label: "Devolução ao estoque" },
  { value: "inventory_updated", label: "Alteração de item" },
  { value: "finance_entry_created", label: "Lançamento financeiro" },
  { value: "commercial_quote_status", label: "Status comercial" },
];

const dateFormatter = new Intl.DateTimeFormat("pt-BR", { dateStyle: "medium", timeStyle: "short" });
function visibleModules(user: AuthUser) {
  if (["gestao", "super_admin"].includes(user.role)) return moduleOptions;
  if (user.role === "admin") return moduleOptions.filter((module) => module.value === "orcamentos");
  return moduleOptions.filter((module) => !["financeiro", "orcamentos"].includes(module.value) && (user.modules || []).includes(module.value));
}
function formatDate(date: string) {
  try { return dateFormatter.format(new Date(date)); } catch { return date; }
}
function buildUrl(filters: Filters, page: number) {
  const params = new URLSearchParams({ page: String(page), page_size: "25" });
  Object.entries(filters).forEach(([key, value]) => {
    if (typeof value === "boolean") { if (value) params.set(key, "true"); }
    else if (value.trim()) params.set(key, value.trim());
  });
  return `/api/notifications/history?${params.toString()}`;
}

export function NotificationCenter({ user, onLogout }: Props) {
  const navigate = useNavigate();
  const [draft, setDraft] = useState<Filters>(initialFilters);
  const [filters, setFilters] = useState<Filters>(initialFilters);
  const [page, setPage] = useState(1);
  const [history, setHistory] = useState<History>({ items: [], unread_count: 0, total: 0, page: 1, page_size: 25 });
  const [actors, setActors] = useState<Actor[]>([]);
  const [loading, setLoading] = useState(true);
  const [filtrosAbertos, setFiltrosAbertos] = useState(false);
  const [error, setError] = useState("");
  const [requestId, setRequestId] = useState(0);
  const allowedModules = useMemo(() => visibleModules(user), [user]);

  const refresh = useCallback(() => setRequestId((previous) => previous + 1), []);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError("");
    apiClient.get<History>(buildUrl(filters, page), { signal: controller.signal })
      .then((data) => setHistory(data))
      .catch((e: Error) => { if (e.name !== "AbortError") setError(e.message); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [filters, page, requestId]);

  useEffect(() => {
    apiClient.get<Actor[]>("/api/notifications/actors").then(setActors).catch(() => setActors([]));
  }, [requestId]);

  useEffect(() => {
    const id = window.setInterval(() => { if (document.visibilityState === "visible") refresh(); }, 60000);
    return () => window.clearInterval(id);
  }, [refresh]);

  function applyFilters(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (draft.date_from && draft.date_to && draft.date_to < draft.date_from) { setError("A data final deve ser igual ou posterior à inicial."); return; }
    setPage(1);
    setFilters({ ...draft });
    refresh();
  }
  function resetFilters() { setDraft(initialFilters); setFilters(initialFilters); setPage(1); refresh(); }
  async function markRead(item: NotificationItem) {
    if (item.is_read) return;
    try {
      await apiClient.post(`/api/notifications/${item.id}/read`, {});
      setHistory((current) => ({
        ...current, unread_count: Math.max(0, current.unread_count - 1),
        items: current.items.map((entry) => entry.id === item.id ? { ...entry, is_read: true } : entry),
      }));
    } catch (e) { setError(e instanceof Error ? e.message : "Falha ao marcar notificação como lida."); }
  }
  async function markAllRead() {
    try {
      await apiClient.post("/api/notifications/read-all", {});
      setHistory((current) => ({ ...current, unread_count: 0, items: current.items.map((entry) => ({ ...entry, is_read: true })) }));
      if (filters.unread_only) refresh();
    } catch (e) { setError(e instanceof Error ? e.message : "Não foi possível atualizar as leituras."); }
  }
  const totalPages = Math.max(1, Math.ceil(history.total / history.page_size));
  const comFiltros = Object.entries(filters).some(([, valor]) => typeof valor === "boolean" ? valor : Boolean(valor));
  function alternarNaoLidas() {
    const proximo = { ...filters, unread_only: !filters.unread_only };
    setDraft(proximo); setFilters(proximo); setPage(1);
  }
  function somenteHoje() {
    const atual = new Date();
    const hoje = [atual.getFullYear(), String(atual.getMonth() + 1).padStart(2, "0"), String(atual.getDate()).padStart(2, "0")].join("-");
    const proximo = { ...filters, date_from: hoje, date_to: hoje };
    setDraft(proximo); setFilters(proximo); setPage(1);
  }
  const hojeAtivo = Boolean(filters.date_from && filters.date_from === filters.date_to);
  const moduloIcones = { laboratorio: FlaskConical, orcamentos: FileText, compras: ShoppingCart, estoque: Boxes, financeiro: WalletCards, colaboradores: UsersRound };


  return <div className="dashboard-shell sentico-shell sentico-notifications">
    <SenticoSidebar user={user} onLogout={onLogout} />
    <main className="sentico-content sentico-notifications__main">
      <div className="sentico-notifications__topline"><button type="button" onClick={() => navigate("/painel")}><ArrowLeft size={16}/> Painel inicial</button><span>ATIVIDADES DO SISTEMA</span></div>
      <header className="sentico-notifications__heading">
        <div className="sentico-notifications__intro"><h1>Central de notificações</h1><p>Histórico das movimentações, com responsável, ordem de serviço e equipamento. Exibimos somente o que seu perfil permite acompanhar.</p></div>
        <div className="sentico-notifications__header-actions"><button type="button" onClick={refresh} disabled={loading}><RefreshCw size={16} /> Atualizar</button>{history.unread_count > 0 && <button type="button" onClick={() => void markAllRead()}><CheckCheck size={16} /> Marcar todas como lidas</button>}</div>
      </header>
      <div className="sentico-notifications__overview" aria-label="Resumo das notificações">
        <div className="sentico-notifications__overview-main"><span className="sentico-notifications__overview-icon"><Activity size={21}/></span><div><span>Atividades encontradas</span><strong>{history.total}</strong></div></div>
        <button type="button" className={filters.unread_only ? "is-selected" : ""} aria-pressed={filters.unread_only} onClick={alternarNaoLidas}><span>Não lidas</span><strong>{history.unread_count}</strong><small>{filters.unread_only ? "Exibindo pendentes" : "Ver pendentes"}</small></button>
        <button type="button" onClick={somenteHoje} className={hojeAtivo ? "is-selected" : ""} aria-pressed={hojeAtivo}><span>Período</span><strong>Hoje</strong><small>Filtrar atividades de hoje</small></button>
      </div>
      <section className="sentico-notifications__filters" aria-label="Pesquisar e filtrar notificações">
        <div className="sentico-notifications__filter-heading"><div><SlidersHorizontal size={18}/><h2>Encontrar uma atividade</h2>{comFiltros && <span className="sentico-notifications__active-tag">Filtros ativos</span>}</div><button type="button" className="sentico-notifications__filter-toggle" onClick={() => setFiltrosAbertos(!filtrosAbertos)} aria-expanded={filtrosAbertos} aria-controls="notificacoes-filtros-avancados">{filtrosAbertos ? "Recolher filtros" : "Mais filtros"}<ChevronDown size={16}/></button></div>
        <form onSubmit={applyFilters}>
          <label className="sentico-notifications__wide"><span>Buscar por atividade, pessoa, cliente ou equipamento</span><div className="sentico-notifications__search"><Search size={18}/><input value={draft.search} onChange={(e) => setDraft({...draft, search:e.target.value})} placeholder="Ex.: OS 39405, CAPRICHE, WEG CFW11" maxLength={120}/></div></label>
          <div id="notificacoes-filtros-avancados" className={`sentico-notifications__advanced ${filtrosAbertos ? "is-open" : ""}`}>
            <label><span>Setor</span><select value={draft.module} onChange={(e)=>setDraft({...draft,module:e.target.value})}><option value="">Todos os setores autorizados</option>{allowedModules.map((op)=><option key={op.value} value={op.value}>{op.label}</option>)}</select></label>
            <label><span>Ação realizada</span><select value={draft.action} onChange={(e)=>setDraft({...draft,action:e.target.value})}><option value="">Todas as ações</option>{actionOptions.map((op)=><option key={op.value} value={op.value}>{op.label}</option>)}</select></label>
            <label><span>Responsável</span><select value={draft.actor_id} onChange={(e)=>setDraft({...draft,actor_id:e.target.value})}><option value="">Todos os responsáveis</option>{actors.map((actor)=><option value={actor.id} key={actor.id}>{actor.name}</option>)}</select></label>
            <label><span>Número da OS</span><input value={draft.work_order} onChange={(e)=>setDraft({...draft,work_order:e.target.value})} placeholder="Ex.: 39405" maxLength={40}/></label>
            <label><span>Data inicial</span><input type="date" value={draft.date_from} onChange={(e)=>setDraft({...draft,date_from:e.target.value})}/></label>
            <label><span>Data final</span><input type="date" value={draft.date_to} onChange={(e)=>setDraft({...draft,date_to:e.target.value})}/></label>
            <label className="sentico-notifications__only-unread"><input type="checkbox" checked={draft.unread_only} onChange={(e)=>setDraft({...draft,unread_only:e.target.checked})}/><span>Somente não lidas</span></label>
          </div>
          <div className="sentico-notifications__filter-actions"><button type="submit"><Search size={16}/> Pesquisar</button><button type="button" onClick={resetFilters}><FilterX size={16}/> Limpar filtros</button></div>
        </form>
      </section>
      <section className="sentico-notifications__results" aria-label="Histórico de atividades" aria-live="polite">
        <div className="sentico-notifications__results-heading"><div><span className="sentico-notifications__eyebrow">HISTÓRICO OPERACIONAL</span><h2>Atividades registradas</h2></div><span>{history.total} resultado{history.total === 1 ? "" : "s"}</span></div>
        {error && <p className="sentico-notifications__error" role="alert">{error}</p>}
        {loading && <p className="sentico-notifications__state">Carregando atividades...</p>}
        {!loading && history.items.length === 0 && <div className="sentico-notifications__empty"><Bell size={25}/><h3>Sem atividades para esses filtros</h3><p>Altere a pesquisa ou remova os filtros para visualizar mais registros.</p><button type="button" onClick={resetFilters}>Limpar filtros</button></div>}
        {!loading && history.items.length > 0 && <div className="sentico-notifications__list">
          {history.items.map((item, index) => {
            const Icone = moduloIcones[item.activity_module as keyof typeof moduloIcones] ?? Bell;
            const modulo = moduleOptions.find((op)=>op.value === item.activity_module)?.label ?? "Atividade geral";
            const dataAnterior = index > 0 ? formatDate(history.items[index - 1].created_at).split(" às ")[0] : null;
            const dataAtual = formatDate(item.created_at).split(" às ")[0];
            return <div key={item.id} className="sentico-notifications__entry-wrap">
              {dataAtual !== dataAnterior && <div className="sentico-notifications__date-divider"><CalendarDays size={14}/>{dataAtual}</div>}
              <article className={`sentico-notifications__item ${item.is_read ? "is-read" : "is-unread"}`} data-modulo={item.activity_module} data-acao={item.action}>
                <span className="sentico-notifications__item-icon"><Icone size={19} strokeWidth={1.8}/></span>
                <div className="sentico-notifications__item-body">
                  <div className="sentico-notifications__item-top"><span className="sentico-notifications__module">{modulo}</span>{!item.is_read && <span className="sentico-notifications__new"><span/>Não lida</span>}<time dateTime={item.created_at}>{formatDate(item.created_at)}</time></div>
                  <h3>{textoEmPortugues(item.title)}</h3>
                  <p>{textoEmPortugues(item.message)}</p>
                  <dl className="sentico-notifications__metadata">
                    <div><dt>Responsável</dt><dd>{item.actor_name || "Não registrado"}</dd></div>
                    {item.work_order_number && <div><dt>Ordem de serviço</dt><dd>{formatarNumeroOS(item.work_order_number)}</dd></div>}
                    {item.equipment_name && <div><dt>Equipamento / material</dt><dd>{item.equipment_name}</dd></div>}
                    {item.action && <div><dt>Ação</dt><dd>{actionOptions.find((op)=>op.value===item.action)?.label ?? textoEmPortugues(item.action.replace(/_/g," "))}</dd></div>}
                    {item.details && <div className="sentico-notifications__detail"><dt>Observações</dt><dd>{textoEmPortugues(item.details)}</dd></div>}
                  </dl>
                  <div className="sentico-notifications__item-actions">{!item.is_read && <button type="button" onClick={()=>void markRead(item)}><Check size={15}/> Marcar como lida</button>}{item.target && <button type="button" onClick={()=>{void markRead(item);navigate(item.target!);}}>Abrir registro <ArrowUpRight size={16}/></button>}</div>
                </div>
              </article>
            </div>;
          })}
        </div>}
        <footer className="sentico-notifications__pagination"><span>Página {page} de {totalPages}</span><div><button type="button" disabled={page <= 1 || loading} onClick={()=>setPage((p)=>p-1)}><ChevronLeft size={17}/> Anterior</button><button type="button" disabled={page >= totalPages || loading} onClick={()=>setPage((p)=>p+1)}>Próxima <ChevronRight size={17}/></button></div></footer>
      </section>
    </main>
  </div>;
}
