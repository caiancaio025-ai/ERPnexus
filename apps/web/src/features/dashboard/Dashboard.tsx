import { useEffect, useMemo, useState } from "react";
import {
  ArrowUpRight,
  Bell,
  Building2,
  Boxes,
  CalendarClock,
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
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useLocation, useNavigate } from "react-router-dom";

import type { AuthUser } from "../auth/AuthCard";
import type { Alert, DashboardSummary, NotificationItem, NotificationSummary, PurchaseEvent, QuickAction } from "./types";
import { apiClient } from "../../shared/api/apiClient";
import "./dashboard.css";

type DashboardProps = { user: AuthUser; onLogout: () => void };
type EventFilter = "all" | PurchaseEvent["status"];

const modules = [
  { label: "Painel", icon: LayoutDashboard, target: "/painel", active: true },
  { label: "Financeiro", icon: WalletCards, target: "/financeiro" },
  { label: "Laboratório", icon: FlaskConical, target: "/laboratorio" },
  { label: "Clientes", icon: Building2, target: "/clientes" },
  { label: "Colaboradores", icon: UsersRound, target: "/colaboradores" },
  { label: "Estoque", icon: Boxes, target: "/estoque" },
  { label: "Compras", icon: ShoppingCart, target: "/compras" },
  { label: "Comercial", icon: Handshake, target: "/comercial" },
];

const alertIcons = {
  delayed_purchases: TriangleAlert,
  delayed_invoices: FileClock,
  active_work_orders: Wrench,
  purchases_due_soon: CalendarClock,
  pending_finance: WalletCards,
  unread_notifications: Bell,
  monthly_equipment: Gauge,
};

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


const fallbackActions: QuickAction[] = [
  {
    key: "new_work_order",
    label: "Criar nova OS",
    description: "Entrada de equipamento no laboratório",
    target: "/laboratorio/os/nova",
  },
  {
    key: "new_budget",
    label: "Fazer orçamento",
    description: "Abrir a área de orçamentos das OS",
    target: "/laboratorio/os?aba=orcamentos",
  },
  {
    key: "unnoted_movement",
    label: "Documento sem nota",
    description: "Registrar entrada ou saída de mercadoria",
    target: "/estoque/movimentos/sem-nota/novo",
  },
];

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
    : fallbackActions;

  const monthly = isRecord(payload.monthly_equipment_entries)
    ? payload.monthly_equipment_entries
    : {};

  return {
    schema_version: "2",
    alerts,
    purchase_events: purchaseEvents,
    quick_actions: quickActions.length ? quickActions : fallbackActions,
    monthly_equipment_entries: {
      month_label: String(monthly.month_label ?? currentMonthLabel()),
      count: Number(monthly.count ?? 0),
    },
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

export function Dashboard({ user, onLogout }: DashboardProps) {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [filter, setFilter] = useState<EventFilter>("all");
  const [error, setError] = useState("");
  const [notifications, setNotifications] = useState<NotificationSummary>({ unread_count: 0, items: [] });
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const location = useLocation();

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    if (params.get("notificacoes") === "1") setNotificationsOpen(true);
  }, [location.search]);
  const reduceMotion = useReducedMotion();
  const navigate = useNavigate();

  useEffect(() => {
    const controller = new AbortController();

    Promise.all([
      apiClient.get<DashboardSummary>("/api/dashboard/summary", { signal: controller.signal }),
      apiClient.get<NotificationSummary>("/api/notifications?limit=10&unread_only=true", { signal: controller.signal }),
    ])
      .then(([response, notificationResponse]) => {
        setSummary(normalizeSummary(response));
        setNotifications(notificationResponse);
      })
      .catch((requestError: Error) => {
        if (requestError.name !== "AbortError") setError(requestError.message);
      });

    return () => controller.abort();
  }, []);

  const visibleEvents = useMemo(() => {
    if (!summary || filter === "all") return summary?.purchase_events ?? [];
    return summary.purchase_events.filter((event) => event.status === filter);
  }, [filter, summary]);

  const fullName = displayName(user.name);

  async function openNotification(item: NotificationItem) {
    if (!item.is_read) {
      await apiClient.post(`/api/notifications/${item.id}/read`, {});
      setNotifications((current) => ({
        unread_count: Math.max(0, current.unread_count - 1),
        items: current.items.filter((entry) => entry.id !== item.id),
      }));
    }
    setNotificationsOpen(false);
    if (item.target) navigate(item.target);
  }

  async function readAllNotifications() {
    await apiClient.post("/api/notifications/read-all", {});
    setNotifications((current) => ({
      unread_count: 0,
      items: [],
    }));
  }

  return (
    <div className="dashboard-shell">
      <aside className="sidebar">
        <div>
          <button className="brand" onClick={() => navigate("/painel")} aria-label="Abrir painel NEXUS">
            <span className="brand__mark">N</span><strong>NEXUS</strong>
          </button>
          <p className="sidebar__section">Geral</p>
          <nav aria-label="Módulos">
            {modules.filter((item) => item.target !== "/financeiro" || !(["tecnico", "lab"].includes(user.role))).map(({ label, icon: Icon, target, active }) => (
              <button className={active ? "active" : ""} key={label} onClick={() => navigate(target)}>
                <Icon size={19} /><span>{label}</span>
              </button>
            ))}
          </nav>
        </div>

        <div className="sidebar__footer">
          <div className="sidebar__user"><span>{initials(user.name)}</span><div><strong>{fullName}</strong><small>{user.role}</small></div></div>
          <button className="sidebar__logout" onClick={onLogout}><LogOut size={18} />Sair do sistema</button>
        </div>
      </aside>

      <main className="dashboard-main">
        <header className="dashboard-header">
          <div className="dashboard-heading">
            <span>Visão geral</span>
            <h1>Painel operacional</h1>
            <p>Olá, {fullName}. Estes são os pontos que exigem atenção hoje.</p>
          </div>
          <div className="dashboard-tools">
            <label className="global-search"><Search size={17} /><input placeholder="Buscar OS, cliente ou compra..." /></label>
            <div className="notification-anchor">
              <button className={`round-button ${notifications.unread_count ? "has-notifications" : ""}`} aria-label="Notificações" onClick={() => setNotificationsOpen((value) => !value)}>
                <Bell size={18} />
                {notifications.unread_count > 0 && <b className="notification-count">{notifications.unread_count > 99 ? "99+" : notifications.unread_count}</b>}
              </button>
              {notificationsOpen && <section className="notification-popover">
                <header><div><span>CENTRAL NEXUS</span><strong>Notificações</strong></div>{notifications.unread_count > 0 && <button onClick={() => void readAllNotifications()}>Marcar todas como lidas</button>}</header>
                <div className="notification-list">
                  {notifications.items.map((item) => <button key={item.id} className={`notification-item ${item.is_read ? "is-read" : "is-unread"}`} onClick={() => void openNotification(item)}>
                    <span className={`notification-dot notification-dot--${item.severity}`} />
                    <span><strong>{item.title}</strong><small>{item.message}</small><em>{new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "short" }).format(new Date(item.created_at))}</em></span>
                    {item.amount != null && <b>{new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(item.amount)}</b>}
                  </button>)}
                  {!notifications.items.length && <p className="notification-empty">Nenhuma notificação até agora.</p>}
                </div>
              </section>}
            </div>
            <button className="user-button" aria-label="Perfil do usuário"><UserRound size={18} /><span>{initials(user.name)}</span></button>
          </div>
        </header>

        {error && <p className="dashboard-error" role="alert">{error}</p>}
        {!summary && !error && <div className="dashboard-loading"><span />Carregando visão geral...</div>}

        {summary && (
          <motion.div initial={reduceMotion ? false : { opacity: 0 }} animate={{ opacity: 1 }}>
            <section className="overview-grid" aria-label="Indicadores principais">
              {summary.alerts.map((alert) => <AlertCard alert={alert} key={alert.key} />)}
            </section>

            <section className="dashboard-content-grid">
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

              <aside className="quick-panel">
                <header><span className="section-kicker">ATALHOS</span><h2>Ações rápidas</h2><p>Operações frequentes sem procurar pelo menu.</p></header>
                <div className="quick-actions">
                  {summary.quick_actions.map((action) => <QuickActionButton action={action} key={action.key} />)}
                </div>
                <div className="dashboard-notification-feed">
                  <header><span><Bell size={14}/>Notificações recentes</span>{notifications.unread_count > 0 && <b>{notifications.unread_count} não lida{notifications.unread_count === 1 ? "" : "s"}</b>}</header>
                  {notifications.items.slice(0, 3).map((item) => <button key={item.id} className={item.is_read ? "is-read" : ""} onClick={() => void openNotification(item)}>
                    <span><strong>{item.title}</strong><small>{item.message}</small></span>
                    {item.amount != null && <b>{new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(item.amount)}</b>}
                  </button>)}
                  {!notifications.items.length && <p>Nenhum evento novo.</p>}
                </div>
                <div className="quick-panel__note"><Truck size={18} /><p>Compras recebidas devem ser baixadas no módulo de Compras, mantendo o histórico do pedido.</p></div>
              </aside>
            </section>

            <footer className="monthly-equipment-bar">
              <div><span className="monthly-equipment-bar__icon"><PackageOpen size={21} /></span><p>Equipamentos com entrada em <strong>{summary.monthly_equipment_entries.month_label}</strong></p></div>
              <strong>{summary.monthly_equipment_entries.count}</strong>
            </footer>
          </motion.div>
        )}
      </main>
    </div>
  );
}
