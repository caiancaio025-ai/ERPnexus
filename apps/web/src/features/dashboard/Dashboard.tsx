import { useEffect, useMemo, useState } from "react";
import {
  ArrowUpRight,
  ChevronLeft,
  ChevronRight,
  Check,
  Settings2,
  RotateCcw,
  Eye,
  EyeOff,
  Bell,
  Expand,
  Building2,
  Boxes,
  CalendarClock,
  CalendarRange,
  ClipboardPlus,
  FileClock,
  Gauge,
  FlaskConical,
  Handshake,
  LayoutDashboard,
  LogOut,
  PackageOpen,
  ReceiptText,
  Search,
  ShoppingCart,
  TriangleAlert,
  Truck,
  UserRound,
  UsersRound,
  WalletCards,
  Wrench,
} from "lucide-react";
import { SenticoSidebar } from "../../shared/ui/SenticoSidebar";
import { SeasonalDashboardBanner } from "../../shared/theme/SeasonalDashboardBanner";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useLocation, useNavigate } from "react-router-dom";

import type { AuthUser } from "../auth/AuthCard";
import { formatarNumeroOS, textoEmPortugues } from "../../shared/i18n/portugues";
import type { Alert, DashboardSummary, NotificationItem, NotificationSummary, PurchaseEvent, QuickAction, WorkQueue } from "./types";
import {
  availableDashboardAreas, alertDashboardArea, dashboardAreaLabels,
  dashboardPreferenceKey, readHiddenDashboardAreas, serializeHiddenDashboardAreas,
  type DashboardArea,
} from "./dashboardPreferences";
import {
  dashboardPeriodKey, parseDashboardPeriod, dashboardPeriodError,
  dashboardPeriodLabel, dashboardPeriodQuery, periodOptions,
  DEFAULT_DASHBOARD_PERIOD, type DashboardPeriodPreference, type PeriodPreset,
} from "./dashboardPeriod";
import { apiClient } from "../../shared/api/apiClient";
import "./dashboard.css";

type DashboardProps = { user: AuthUser; onLogout: () => void };
type EventFilter = "all" | PurchaseEvent["status"];

const alertIcons = {
  delayed_purchases: TriangleAlert,
  delayed_invoices: FileClock,
  active_work_orders: Wrench,
  quotes_pending: ReceiptText,
  lab_entries: FlaskConical,
  lab_approved: Wrench,
  requests_buy: ShoppingCart,
  finance_overdue: WalletCards,
  purchases_due_soon: CalendarClock,
  pending_finance: WalletCards,
  unread_notifications: Bell,
  monthly_equipment: Gauge,
};

const areaIcons = {
  laboratorio: FlaskConical, orcamentos: ReceiptText, compras: ShoppingCart,
  financeiro: WalletCards, estoque: Boxes, notificacoes: Bell,
  atalhos: Gauge, geral: LayoutDashboard,
};

function readDashboardPeriodPreference(userId: number): DashboardPeriodPreference {
  try { return parseDashboardPeriod(window.localStorage.getItem(dashboardPeriodKey(userId))); }
  catch { return { ...DEFAULT_DASHBOARD_PERIOD }; }
}

function readDashboardPreference(userId: number): DashboardArea[] {
  try { return readHiddenDashboardAreas(window.localStorage.getItem(dashboardPreferenceKey(userId))); }
  catch { return []; } // O painel continua funcional quando o navegador bloqueia armazenamento.
}

const actionIcons = {
  new_work_order: ClipboardPlus,
  new_budget: ReceiptText,
  unnoted_movement: PackageOpen,
};

function initials(name: string) {
  return name.trim().split(/\s+/).slice(0, 2).map((part) => part[0]?.toUpperCase()).join("");
}

function displayName(name: string) {
  return name.replace(/\b\p{L}/gu, (letter) => letter.toUpperCase());
}


function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function currentMonthLabel() {
  return new Intl.DateTimeFormat("pt-BR", { month: "long", year: "numeric" }).format(new Date());
}

function normalizeSummary(payload: unknown): DashboardSummary {
  if (!isRecord(payload)) throw new Error("A API retornou um resumo inválido.");

  const alerts: Alert[] = Array.isArray(payload.alerts)
    ? payload.alerts.filter(isRecord).map((alert) => ({
        key: String(alert.key ?? "alert"),
        label: String(alert.label ?? "Alerta"),
        value: Number(alert.value ?? 0),
        detail: String(alert.detail ?? "Ver detalhes"),
        tone: alert.tone === "danger" || alert.tone === "warning" ? alert.tone : "info",
        target: String(alert.target ?? "/painel"),
      }))
    : [];

  const purchaseEvents: PurchaseEvent[] = Array.isArray(payload.purchase_events)
    ? payload.purchase_events.filter(isRecord).map((event, index) => ({
        id: Number(event.id ?? index + 1),
        code: String(event.code ?? "Compra"),
        supplier: String(event.supplier ?? "Fornecedor não informado"),
        message: String(event.message ?? "Pedido aguardando acompanhamento."),
        due_label: String(event.due_label ?? "Prazo não informado"),
        status: event.status === "due_soon" ? "due_soon" : "overdue",
        target: String(event.target ?? "/compras"),
      }))
    : [];

  const workQueues: WorkQueue[] = Array.isArray(payload.work_queues)
    ? payload.work_queues.filter(isRecord).map((queue) => ({
      key: String(queue.key ?? "fila"),
      section: (["laboratorio", "orcamentos", "compras", "financeiro", "estoque"] as string[])
        .includes(String(queue.section)) ? queue.section as WorkQueue["section"] : "laboratorio",
      title: String(queue.title ?? "Pendências"),
      description: String(queue.description ?? ""),
      tone: (["warning", "danger", "success"] as unknown[]).includes(queue.tone)
        ? queue.tone as WorkQueue["tone"] : "info",
      total: Number(queue.total ?? 0),
      target: String(queue.target ?? "/painel"),
      items: Array.isArray(queue.items) ? queue.items.filter(isRecord).map((item) => ({
        id: Number(item.id ?? 0),
        title: String(item.title ?? "Registro"),
        description: String(item.description ?? ""),
        meta: item.meta == null ? null : String(item.meta),
        status: String(item.status ?? "Pendente"),
        target: String(item.target ?? queue.target ?? "/painel"),
        date_label: item.date_label == null ? null : String(item.date_label),
      })) : [],
    })) : [];

  const rawActions = Array.isArray(payload.quick_actions)
    ? payload.quick_actions.filter(isRecord)
    : [];
  const quickActions = rawActions.every(
    (action) =>
      action.key === "new_work_order" ||
      action.key === "new_budget" ||
      action.key === "unnoted_movement",
  )
    ? rawActions.map((action) => ({
        key: action.key as QuickAction["key"],
        label: String(action.label ?? "Ação rápida"),
        description: String(action.description ?? "Abrir operação"),
        target: String(action.target ?? "/painel"),
      }))
    : [];

  const monthly = isRecord(payload.monthly_equipment_entries)
    ? payload.monthly_equipment_entries
    : {};

  return {
    schema_version: "3",
    audience: (["gestao", "admin", "lab", "compras", "estoque"] as unknown[]).includes(payload.audience)
      ? payload.audience as DashboardSummary["audience"] : "outros",
    work_queues: workQueues,
    alerts,
    purchase_events: purchaseEvents,
    quick_actions: quickActions,
    monthly_equipment_entries: {
      month_label: String(monthly.month_label ?? currentMonthLabel()),
      count: Number(monthly.count ?? 0),
    },
    filtered_period: payload.filtered_period === true,
  };
}

function AlertCard({ alert }: { alert: Alert }) {
  const navigate = useNavigate();
  const Icon = alertIcons[alert.key as keyof typeof alertIcons] ?? TriangleAlert;

  return (
    <motion.button
      className={`overview-card overview-card--${alert.tone}`}
      onClick={() => navigate(alert.target)}
      whileHover={{ y: -4, scale: 1.01 }}
      whileTap={{ scale: 0.985 }}
      transition={{ type: "spring", stiffness: 320, damping: 24 }}
    >
      <span className="overview-card__glow" />
      <span className="overview-card__top">
        <span className="overview-card__label">{alert.label}</span>
        <span className="overview-card__icon"><Icon size={20} /></span>
      </span>
      <strong>{alert.value}</strong>
      <span className="overview-card__detail">{alert.detail}<ArrowUpRight size={14} /></span>
    </motion.button>
  );
}

function PurchaseEventCard({ event }: { event: PurchaseEvent }) {
  const navigate = useNavigate();
  const overdue = event.status === "overdue";

  return (
    <motion.article
      layout
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.98 }}
      className={`purchase-event purchase-event--${event.status}`}
    >
      <span className="purchase-event__status">{overdue ? "Atrasada" : "Próxima"}</span>
      <div className="purchase-event__identity">
        <strong>{event.code}</strong>
        <span>{event.supplier}</span>
      </div>
      <p title={event.message}>{event.message}</p>
      <span className="purchase-event__date"><CalendarClock size={14} />{event.due_label}</span>
      <button onClick={() => navigate(event.target)}>Abrir <ArrowUpRight size={14} /></button>
    </motion.article>
  );
}

function QuickActionButton({ action }: { action: QuickAction }) {
  const navigate = useNavigate();
  const Icon = actionIcons[action.key];

  return (
    <motion.button
      className={`quick-action quick-action--${action.key}`}
      onClick={() => navigate(action.target)}
      whileHover={{ x: 3, y: -2 }}
      whileTap={{ scale: 0.985 }}
      transition={{ type: "spring", stiffness: 360, damping: 25 }}
    >
      <span className="quick-action__icon"><Icon size={22} /></span>
      <span><strong>{action.label}</strong><small>{action.description}</small></span>
      <ArrowUpRight className="quick-action__arrow" size={17} />
    </motion.button>
  );
}

const sectionNames: Record<WorkQueue["section"], string> = {
  laboratorio: "LABORATÓRIO", orcamentos: "ORÇAMENTOS", compras: "COMPRAS",
  financeiro: "FINANCEIRO", estoque: "ESTOQUE",
};
const sectionIcons = {
  laboratorio: FlaskConical, orcamentos: ReceiptText, compras: ShoppingCart,
  financeiro: WalletCards, estoque: Boxes,
};

function WorkQueueCard({ queue }: { queue: WorkQueue }) {
  const navigate = useNavigate();
  const Icon = sectionIcons[queue.section];
  return (
    <article className={`work-queue work-queue--${queue.tone}`}>
      <header className="work-queue__header">
        <div className="work-queue__heading">
          <span className="work-queue__section"><Icon size={15} />{sectionNames[queue.section]}</span>
          <h2>{queue.title}</h2>
          <p>{queue.description}</p>
        </div>
        <span className="work-queue__count" aria-label={`${queue.total} registros`}>{queue.total}</span>
      </header>
      <div className="work-queue__rows">
        {queue.items.map((item) => <button type="button" key={item.id} className="work-queue__item" onClick={() => navigate(item.target)}>
          <span className="work-queue__info">
            <strong>{item.title}</strong>
            <small>{item.description}</small>
            {(item.meta || item.date_label) && <em>{[item.meta, item.date_label].filter(Boolean).join(" · ")}</em>}
          </span>
          <span className="work-queue__end"><span className="work-queue__status">{item.status}</span><ArrowUpRight size={16}/></span>
        </button>)}
        {queue.items.length === 0 && <div className="work-queue__empty">Nenhuma pendência nesta etapa.</div>}
      </div>
      <button type="button" className="work-queue__footer" onClick={() => navigate(queue.target)}>
        Ver no módulo <ArrowUpRight size={16} />
      </button>
    </article>
  );
}

export function Dashboard({ user, onLogout }: DashboardProps) {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [filter, setFilter] = useState<EventFilter>("all");
  const [globalQuery, setGlobalQuery] = useState("");
  const [error, setError] = useState("");
  const [notifications, setNotifications] = useState<NotificationSummary>({ unread_count: 0, items: [] });
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [visibilityOpen, setVisibilityOpen] = useState(false);
  const [savedAreas, setSavedAreas] = useState<{ ownerId: number; hidden: DashboardArea[] }>(
    () => ({ ownerId: user.id, hidden: readDashboardPreference(user.id) }),
  );
  const [savedPeriod, setSavedPeriod] = useState<{ ownerId: number; value: DashboardPeriodPreference }>(
    () => ({ ownerId: user.id, value: readDashboardPeriodPreference(user.id) }),
  );
  const appliedPeriod = savedPeriod.ownerId === user.id ? savedPeriod.value : readDashboardPeriodPreference(user.id);
  const [draftPeriod, setDraftPeriod] = useState<DashboardPeriodPreference>(() => readDashboardPeriodPreference(user.id));
  const [periodError, setPeriodError] = useState("");
  const periodQuery = useMemo(() => dashboardPeriodQuery(appliedPeriod),
    [appliedPeriod.preset, appliedPeriod.start, appliedPeriod.end]);
  const hiddenAreas = savedAreas.ownerId === user.id ? savedAreas.hidden : readDashboardPreference(user.id);
  const availableAreas = useMemo(() => summary ? availableDashboardAreas(summary) : [], [summary]);
  const selectedAreasCount = availableAreas.filter((area) => !hiddenAreas.includes(area)).length;
  const isAreaVisible = (area: DashboardArea) => !hiddenAreas.includes(area);
  const visibleAlerts = summary?.alerts.filter((alert) => isAreaVisible(alertDashboardArea(alert.key))) ?? [];
  const visibleQueues = summary?.work_queues.filter((queue) => isAreaVisible(queue.section)) ?? [];
  const showPurchases = !!summary && ["gestao", "compras"].includes(summary.audience) && isAreaVisible("compras");
  const showShortcuts = !!summary && summary.quick_actions.length > 0 && isAreaVisible("atalhos");
  const showRecent = isAreaVisible("notificacoes");
  const showSidebarPanel = showShortcuts || showRecent;

  function saveHiddenAreas(next: DashboardArea[]) {
    const clean = Array.from(new Set(next));
    setSavedAreas({ ownerId: user.id, hidden: clean });
    try { window.localStorage.setItem(dashboardPreferenceKey(user.id), serializeHiddenDashboardAreas(clean)); }
    catch { /* Modo de armazenamento privado: seleção mantida nesta sessão. */ }
  }

  function applyDashboardPeriod(next: DashboardPeriodPreference) {
    const validation = dashboardPeriodError(next);
    if (validation) { setPeriodError(validation); return; }
    setPeriodError("");
    setSavedPeriod({ ownerId: user.id, value: next });
    setDraftPeriod(next);
    try { window.localStorage.setItem(dashboardPeriodKey(user.id), JSON.stringify(next)); }
    catch { /* A preferência continua nesta sessão quando o armazenamento é bloqueado. */ }
  }

  useEffect(() => {
    setDraftPeriod(readDashboardPeriodPreference(user.id));
    setPeriodError("");
  }, [user.id]);

  function toggleDashboardArea(area: DashboardArea) {
    saveHiddenAreas(isAreaVisible(area) ? [...hiddenAreas, area] : hiddenAreas.filter((item) => item !== area));
  }

  function showOnlyDashboardArea(area: DashboardArea) {
    saveHiddenAreas(availableAreas.filter((item) => item !== area));
    setVisibilityOpen(false);
  }

  const location = useLocation();

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    if (params.get("notificacoes") === "1") setNotificationsOpen(true);
  }, [location.search]);
  const reduceMotion = useReducedMotion();
  const navigate = useNavigate();

  useEffect(() => {
    const controller = new AbortController();

    // As notificações em tempo real não são alteradas pelo filtro de indicadores.
    apiClient.get<NotificationSummary>("/api/notifications?limit=10", { signal: controller.signal })
      .then(setNotifications)
      .catch((requestError: Error) => {
        if (requestError.name !== "AbortError") setError(requestError.message);
      });

    return () => controller.abort();
  }, [user.id]);

  useEffect(() => {
    const controller = new AbortController();
    setSummary(null);
    setError("");
    apiClient.get<DashboardSummary>(periodQuery, { signal: controller.signal })
      .then((response) => setSummary(normalizeSummary(response)))
      .catch((requestError: Error) => {
        if (requestError.name !== "AbortError") setError(requestError.message);
      });
    return () => controller.abort();
  }, [periodQuery, user.id]);

  useEffect(() => {
    let active = true;
    const refreshSummary = () => {
      if (document.visibilityState === "hidden") return;
      apiClient.get<DashboardSummary>(periodQuery)
        .then((response) => { if (active) setSummary(normalizeSummary(response)); })
        .catch(() => { /* Falha momentânea não apaga o painel já exibido. */ });
    };
    const intervalId = window.setInterval(refreshSummary, 60000);
    window.addEventListener("focus", refreshSummary);
    return () => { active = false; window.clearInterval(intervalId); window.removeEventListener("focus", refreshSummary); };
  }, [periodQuery, user.id]);

  useEffect(() => {
    const refresh = () => {
      if (document.visibilityState === "hidden") return;
      apiClient.get<NotificationSummary>("/api/notifications?limit=10")
        .then(setNotifications)
        .catch(() => { /* Mantém as atividades já exibidas em caso de desconexão. */ });
    };
    const intervalId = window.setInterval(refresh, 40000);
    window.addEventListener("focus", refresh);
    return () => { window.clearInterval(intervalId); window.removeEventListener("focus", refresh); };
  }, []);

  const visibleEvents = useMemo(() => {
    if (!summary || filter === "all") return summary?.purchase_events ?? [];
    return summary.purchase_events.filter((event) => event.status === filter);
  }, [filter, summary]);

  const fullName = displayName(user.name);
  const dashboardRoleName: Record<DashboardSummary["audience"], string> = {
    gestao: "Visão da Gestão", admin: "Orçamentos e aprovações",
    lab: "Atividades do Laboratório", compras: "Solicitações de Compras",
    estoque: "Controle do Estoque", outros: "Atividades do sistema",
  };

  async function openNotification(item: NotificationItem) {
    if (!item.is_read) {
      try {
        await apiClient.post(`/api/notifications/${item.id}/read`, {});
        setNotifications((current) => ({
          unread_count: Math.max(0, current.unread_count - 1),
          items: current.items.map((entry) => entry.id === item.id ? { ...entry, is_read: true } : entry),
        }));
      } catch { /* A falha de leitura não deve impedir a navegação. */ }
    }
    setNotificationsOpen(false);
    if (item.target) navigate(item.target);
  }

  async function readAllNotifications() {
    await apiClient.post("/api/notifications/read-all", {});
    setNotifications((current) => ({
      unread_count: 0,
      items: current.items.map((item) => ({ ...item, is_read: true })),
    }));
  }

  return (
    <div className="dashboard-shell sentico-shell">
      <SenticoSidebar user={user} onLogout={onLogout} />

      <main className="dashboard-main sentico-content">
        <header className="dashboard-header">
          <div className="dashboard-heading">
            <span>Visão geral</span>
            <h1>{summary ? dashboardRoleName[summary.audience] : "Painel operacional"}</h1>
            <p>Olá, {fullName}. Estes são os pontos que exigem atenção hoje.</p>
          </div>
          <div className="dashboard-tools">
            {(!summary || ["gestao", "admin", "lab"].includes(summary.audience)) &&
              <label className="global-search"><Search size={17} /><input
                aria-label="Pesquisar OS ou equipamento no laboratório"
                placeholder="Buscar OS ou equipamento..."
                value={globalQuery}
                onChange={(event) => setGlobalQuery(event.target.value)}
                onKeyDown={(event) => { if (event.key === "Enter" && globalQuery.trim()) navigate(`/laboratorio?busca=${encodeURIComponent(globalQuery.trim())}`); }}
              /></label>}
            <div className="notification-anchor">
              <button className={`round-button ${notifications.unread_count ? "has-notifications" : ""}`} aria-label="Notificações" onClick={() => setNotificationsOpen((value) => !value)}>
                <Bell size={18} />
                {notifications.unread_count > 0 && <b className="notification-count">{notifications.unread_count > 99 ? "99+" : notifications.unread_count}</b>}
              </button>
              {notificationsOpen && <section className="notification-popover">
                <header className="notification-popover__header"><div><span>CENTRAL SÊNTICO</span><strong>Últimas atividades</strong></div><div className="notification-popover__actions"><button type="button" onClick={() => { setNotificationsOpen(false); navigate("/notificacoes"); }}><Expand size={14} /> Ampliar</button>{notifications.unread_count > 0 && <button type="button" onClick={() => void readAllNotifications()}>Marcar lidas</button>}</div></header>
                <div className="notification-list">
                  {notifications.items.map((item) => <button key={item.id} className={`notification-item ${item.is_read ? "is-read" : "is-unread"}`} data-modulo={item.activity_module} onClick={() => void openNotification(item)}>
                    <span className={`notification-dot notification-dot--${item.severity}`} />
                    <span><strong>{textoEmPortugues(item.title)}</strong><small>{textoEmPortugues(item.message)}</small><em>{[item.actor_name, item.work_order_number ? formatarNumeroOS(item.work_order_number) : null, item.equipment_name].filter(Boolean).join(" · ")}</em><em>{new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "short" }).format(new Date(item.created_at))}</em></span>
                    {item.amount != null && <b>{new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(item.amount)}</b>}
                  </button>)}
                  {!notifications.items.length && <p className="notification-empty">Nenhuma notificação até agora.</p>}
                </div>
                <button className="notification-expand" type="button" onClick={() => { setNotificationsOpen(false); navigate("/notificacoes"); }}><Expand size={16} /> Abrir central completa de notificações</button>
              </section>}
            </div>
            <button className="user-button" aria-label="Perfil do usuário"><UserRound size={18} /><span>{initials(user.name)}</span></button>
          </div>
        </header>
        <SeasonalDashboardBanner />

        {error && <p className="dashboard-error" role="alert">{error}</p>}
        {!summary && !error && <div className="dashboard-loading"><span />Carregando visão geral...</div>}

        {summary && <section className="dashboard-visibility" aria-label="Personalizar as informações do painel">
          <div className="dashboard-visibility__summary">
            <div className="dashboard-visibility__copy">
              <span className="dashboard-visibility__eyebrow">SEU PAINEL</span>
              <strong>Escolha o que deseja acompanhar</strong>
              <small>{selectedAreasCount} de {availableAreas.length} áreas visíveis · Sua escolha fica salva neste navegador</small>
              <span className="dashboard-visibility__period"><CalendarRange size={15}/> {dashboardPeriodLabel(appliedPeriod)}</span>
            </div>
            <div className="dashboard-visibility__actions">
              {selectedAreasCount < availableAreas.length && <button type="button" className="dashboard-visibility__reset" onClick={() => saveHiddenAreas([])}><RotateCcw size={15}/> Mostrar tudo</button>}
              <button type="button" className="dashboard-visibility__open" aria-expanded={visibilityOpen} aria-controls="dashboard-visibility-options" onClick={() => setVisibilityOpen((open) => !open)}><Settings2 size={16}/> {visibilityOpen ? "Concluir" : "Personalizar painel"}</button>
            </div>
          </div>
          {visibilityOpen && <div id="dashboard-visibility-options" className="dashboard-visibility__options">
            <section className="dashboard-period" aria-label="Selecionar período do painel">
              <div className="dashboard-period__heading"><CalendarRange size={19}/><div><strong>Período dos indicadores</strong><p>Escolha quais datas devem entrar nas contagens e pendências do painel.</p></div></div>
              <div className="dashboard-period__controls">
                <label>Período de referência
                  <select value={draftPeriod.preset} onChange={(event) => { setPeriodError(""); setDraftPeriod((current) => ({ ...current, preset: event.target.value as PeriodPreset })); }}>
                    {periodOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
                  </select>
                </label>
                {draftPeriod.preset === "personalizado" && <div className="dashboard-period__dates">
                  <label>Data inicial (opcional)<input type="date" value={draftPeriod.start} onChange={(event) => { setPeriodError(""); setDraftPeriod((current) => ({ ...current, start: event.target.value })); }} /></label>
                  <label>Data final (opcional)<input type="date" value={draftPeriod.end} onChange={(event) => { setPeriodError(""); setDraftPeriod((current) => ({ ...current, end: event.target.value })); }} /></label>
                </div>}
                <div className="dashboard-period__buttons">
                  <button type="button" className="dashboard-period__apply" onClick={() => applyDashboardPeriod(draftPeriod)}><Check size={16}/> Aplicar período</button>
                  <button type="button" onClick={() => applyDashboardPeriod({ ...DEFAULT_DASHBOARD_PERIOD })}><RotateCcw size={15}/> Todo o histórico</button>
                </div>
              </div>
              {periodError && <p className="dashboard-period__error" role="alert">{periodError}</p>}
              <p className="dashboard-period__help">Laboratório e Orçamentos: <strong>entrada da OS</strong> · Compras: <strong>data da solicitação ou compra</strong> · Financeiro: <strong>vencimento ou faturamento</strong>. As notificações continuam em tempo real. Nenhum registro antigo é apagado.</p>
            </section>
            <div className="dashboard-visibility__hint">Ative ou oculte áreas individualmente. Use <strong>Somente esta</strong> para acompanhar apenas um setor.</div>
            <div className="dashboard-visibility__grid">
              {availableAreas.map((area) => {
                const Icon = areaIcons[area];
                const enabled = isAreaVisible(area);
                return <div className={`dashboard-visibility__option ${enabled ? "is-enabled" : "is-hidden"}`} key={area} data-area={area}>
                  <span className="dashboard-visibility__icon"><Icon size={19}/></span>
                  <div className="dashboard-visibility__info"><strong>{dashboardAreaLabels[area].title}</strong><small>{dashboardAreaLabels[area].description}</small></div>
                  <div className="dashboard-visibility__controls">
                    <button type="button" className="dashboard-visibility__toggle" role="switch" aria-label={`${enabled ? "Ocultar" : "Mostrar"} ${dashboardAreaLabels[area].title}`} aria-checked={enabled} onClick={() => toggleDashboardArea(area)}>{enabled ? <><Eye size={14}/> Visível</> : <><EyeOff size={14}/> Oculta</>}</button>
                    <button type="button" className="dashboard-visibility__only" onClick={() => showOnlyDashboardArea(area)}>Somente esta</button>
                  </div>
                </div>;
              })}
            </div>
            <button type="button" className="dashboard-visibility__show-all" onClick={() => saveHiddenAreas([])}><Check size={16}/> Mostrar todas as áreas disponíveis</button>
          </div>}
        </section>}

        {summary && (
          <motion.div initial={reduceMotion ? false : { opacity: 0 }} animate={{ opacity: 1 }}>
            {visibleAlerts.length > 0 && <section className="overview-grid" aria-label="Indicadores principais">
              {visibleAlerts.map((alert) => <AlertCard alert={alert} key={alert.key} />)}
            </section>}

            {visibleQueues.length > 0 && <section className="work-queue-section" aria-label="Pendências e atividades por função">
              <header className="work-queue-section__topline">
                <div><span className="section-kicker">O QUE PRECISA SER FEITO</span><h2>Suas prioridades</h2><p>Selecione um registro para continuar o trabalho sem procurar pelo menu.</p></div>
                <span className="work-queue-section__total">{visibleQueues.reduce((total, queue) => total + queue.total, 0)} pendências</span>
              </header>
              <div className="work-queue-grid">{visibleQueues.map((queue) => <WorkQueueCard key={queue.key} queue={queue} />)}</div>
            </section>}

            {(showPurchases || showSidebarPanel) && <section className={`dashboard-content-grid ${!showPurchases ? "dashboard-content-grid--only-aside" : ""} ${!showSidebarPanel ? "dashboard-content-grid--only-purchases" : ""}`}>
              {showPurchases && (
              <article className="purchase-center">
                <header className="section-header">
                  <div><span className="section-kicker">COMPRAS</span><h2>Central de eventos urgentes</h2><p>Atrasos e entregas previstas dos pedidos em andamento.</p></div>
                  <div className="event-filters" aria-label="Filtrar eventos de compras">
                    <button className={filter === "all" ? "active" : ""} onClick={() => setFilter("all")}>Todos</button>
                    <button className={filter === "overdue" ? "active" : ""} onClick={() => setFilter("overdue")}>Atrasadas</button>
                    <button className={filter === "due_soon" ? "active" : ""} onClick={() => setFilter("due_soon")}>Próximas</button>
                  </div>
                </header>
                <div className="purchase-events" role="table" aria-label="Eventos urgentes de compras">
                  <div className="purchase-events__head" role="row">
                    <span>Status</span><span>Pedido / fornecedor</span><span>Item vinculado</span><span>Prazo</span><span>Ação</span>
                  </div>
                  <AnimatePresence mode="popLayout">
                    {visibleEvents.map((event) => <PurchaseEventCard event={event} key={event.id} />)}
                  </AnimatePresence>
                  {!visibleEvents.length && <p className="purchase-events__empty">Nenhuma compra exige atenção neste filtro.</p>}
                </div>
              </article>
              )}

              {showSidebarPanel && <aside className="quick-panel">
                {showShortcuts && <header><span className="section-kicker">ATALHOS</span><h2>Ações rápidas</h2><p>Operações frequentes sem procurar pelo menu.</p></header>}
                {showShortcuts && <div className="quick-actions">
                  {summary.quick_actions.map((action) => <QuickActionButton action={action} key={action.key} />)}
                </div>}
                {showRecent && <div className="dashboard-notification-feed">
                  <header><span><Bell size={14}/>Atividades recentes</span><button className="feed-expand" type="button" onClick={() => navigate("/notificacoes")}><Expand size={13} /> Ver tudo</button>{notifications.unread_count > 0 && <b>{notifications.unread_count} nova{notifications.unread_count === 1 ? "" : "s"}</b>}</header>
                  {notifications.items.slice(0, 3).map((item) => <button key={item.id} className={item.is_read ? "is-read" : ""} data-modulo={item.activity_module} onClick={() => void openNotification(item)}>
                    <span><strong>{textoEmPortugues(item.title)}</strong><small>{item.actor_name ? `${item.actor_name} · ` : ""}{item.work_order_number ? `${formatarNumeroOS(item.work_order_number)} · ` : ""}{textoEmPortugues(item.message)}</small></span>
                    {item.amount != null && <b>{new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(item.amount)}</b>}
                  </button>)}
                  {!notifications.items.length && <p>Nenhuma atividade registrada para seu perfil.</p>}
                </div>}
                {showPurchases && <div className="quick-panel__note"><Truck size={18} /><p>Compras recebidas devem ser baixadas no módulo de Compras, mantendo o histórico do pedido.</p></div>}
              </aside>}
            </section>}

            {(["gestao", "lab"].includes(summary.audience)) && isAreaVisible("laboratorio") && <footer className="monthly-equipment-bar">
              <div><span className="monthly-equipment-bar__icon"><PackageOpen size={21} /></span><p>Equipamentos com entrada {summary.filtered_period ? "·" : "em"} <strong>{summary.monthly_equipment_entries.month_label}</strong></p></div>
              <strong>{summary.monthly_equipment_entries.count}</strong>
            </footer>}
            {selectedAreasCount === 0 && <div className="dashboard-visibility__empty"><EyeOff size={20}/><strong>Você ocultou todas as áreas deste painel.</strong><p>Suas informações continuam disponíveis nos módulos do SÊNTICO.</p><button type="button" onClick={() => saveHiddenAreas([])}>Mostrar tudo novamente</button></div>}
          </motion.div>
        )}
      </main>
    </div>
  );
}
