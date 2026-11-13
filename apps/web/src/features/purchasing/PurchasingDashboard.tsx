import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  ArrowLeft,
  Bell,
  Boxes,
  Building2,
  CalendarClock,
  CheckCircle2,
  ChevronRight,
  ClipboardList,
  FileBarChart,
  FileSearch,
  History,
  Link2,
  LogOut,
  PackageCheck,
  PackagePlus,
  Paperclip,
  Plus,
  Search,
  Settings,
  ShoppingCart,
  Store,
  Truck,
  X,
} from "lucide-react";
import { SenticoSidebar } from "../../shared/ui/SenticoSidebar";
import { AnimatePresence, motion } from "motion/react";
import { useNavigate } from "react-router-dom";

import { apiClient } from "../../shared/api/apiClient";
import type { AuthUser } from "../auth/AuthCard";
import { MaterialRequestsPanel } from "./MaterialRequestsPanel";
import { PurchasingSpendingReport } from "./PurchasingSpendingReport";
import type {
  CompanyCode,
  MaterialRequest,
  PurchaseAudit,
  PurchaseOrder,
  PurchaseOrigin,
  PurchaseStatus,
  PurchaseSummary,
  Supplier,
} from "./types";
import "./purchasing.css";

type Props = { user: AuthUser; onLogout: () => void };
type View = "dashboard" | "requests" | "new" | "orders" | "report" | "audit";

type PurchaseNotification = {
  id: number;
  category: string;
  severity: string;
  title: string;
  message: string;
  target: string | null;
  entity_type: string | null;
  entity_id: number | null;
  is_read: boolean;
  created_at: string;
};
type PurchaseNotificationSummary = { unread_count: number; items: PurchaseNotification[] };

type StockOption = { id: number; stock_code: string; name: string; quantity: number; mode: "bulk" | "serialized"; category: string; manufacturer_serial: string | null };
type StockFormat = { id: number; category: string; name: string; code: string };
type StockLookup = { items: StockOption[]; formats: StockFormat[] };

type FormState = {
  company_code: CompanyCode;
  supplier_id: string;
  equipment_serial: string;
  invoice_number: string;
  client_destination: string;
  product_name: string;
  inventory_destination: "" | "new" | "existing";
  inventory_item_id: string;
  inventory_name: string;
  inventory_mode: "bulk" | "serialized";
  inventory_serial: string;
  inventory_category: string;
  inventory_format_id: string;
  quantity: string;
  total_amount: string;
  origin: PurchaseOrigin;
  tracking_code: string;
  purchase_date: string;
  estimated_delivery_date: string;
  status: PurchaseStatus;
  product_link: string;
  notes: string;
};

const today = () => new Date().toISOString().slice(0, 10);
const inSevenDays = () => {
  const date = new Date();
  date.setDate(date.getDate() + 7);
  return date.toISOString().slice(0, 10);
};

const companies: { code: CompanyCode; label: string }[] = [
  { code: "universo_eletronica", label: "Universo Eletrônica" },
  { code: "universo_automacao", label: "Universo Automação" },
  { code: "solucoes_eletronica", label: "Soluções Eletrônica" },
];

const statusLabels: Record<PurchaseStatus, string> = {
  awaiting_payment: "Ag. pagamento",
  ordered: "Pedido realizado",
  processing: "Em preparação",
  shipped: "Em transporte",
  customs: "Na alfândega",
  delivered: "Entregue",
  cancelled: "Cancelada",
};

const emptyForm = (): FormState => ({
  company_code: "universo_eletronica",
  supplier_id: "",
  equipment_serial: "",
  invoice_number: "",
  client_destination: "",
  product_name: "",
  inventory_destination: "",
  inventory_item_id: "",
  inventory_name: "",
  inventory_mode: "bulk",
  inventory_serial: "",
  inventory_category: "componentes",
  inventory_format_id: "",
  quantity: "1",
  total_amount: "",
  origin: "national",
  tracking_code: "",
  purchase_date: today(),
  estimated_delivery_date: inSevenDays(),
  status: "awaiting_payment",
  product_link: "",
  notes: "",
});

function money(value: number | string | null | undefined) {
  return Number(value ?? 0).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

function dateLabel(value: string) {
  return new Intl.DateTimeFormat("pt-BR", { timeZone: "UTC" }).format(new Date(`${value}T00:00:00Z`));
}

function notificationDestination(item: PurchaseNotification) {
  if (item.category === "commercial_sale_approved" && item.entity_id) {
    return `/comercial?tab=orcamento&quote=${item.entity_id}`;
  }
  return item.target;
}

function statusTone(order: PurchaseOrder) {
  if (order.status === "delivered") return "delivered";
  if (order.status === "cancelled") return "cancelled";
  const due = new Date(`${order.estimated_delivery_date}T23:59:59`);
  const diff = Math.ceil((due.getTime() - Date.now()) / 86400000);
  if (diff < 0) return "overdue";
  if (diff <= 7) return "due";
  return "open";
}

export function PurchasingDashboard({ user, onLogout }: Props) {
  const navigate = useNavigate();
  const canViewValues = ["gestao", "super_admin"].includes(user.role);
  const [view, setView] = useState<View>("dashboard");
  const [company, setCompany] = useState<CompanyCode | "all">("all");
  const [summary, setSummary] = useState<PurchaseSummary | null>(null);
  const [orders, setOrders] = useState<PurchaseOrder[]>([]);
  const [materialRequests, setMaterialRequests] = useState<MaterialRequest[]>([]);
  const [notifications, setNotifications] = useState<PurchaseNotificationSummary>({ unread_count: 0, items: [] });
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [audit, setAudit] = useState<PurchaseAudit[]>([]);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<PurchaseStatus | "all" | "overdue" | "due_soon">("all");
  const [form, setForm] = useState<FormState>(emptyForm);
  const [editing, setEditing] = useState<PurchaseOrder | null>(null);
  const [supplierModal, setSupplierModal] = useState(false);
  const [supplierName, setSupplierName] = useState("");
  const [supplierSaving, setSupplierSaving] = useState(false);
  const [supplierError, setSupplierError] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [attachment, setAttachment] = useState<File | null>(null);
  const [stockSearch, setStockSearch] = useState("");
  const [stockOptions, setStockOptions] = useState<StockOption[]>([]);
  const [stockFormats, setStockFormats] = useState<StockFormat[]>([]);
  const [stockLoading, setStockLoading] = useState(false);
  const [stockError, setStockError] = useState("");
  const selectedStock = stockOptions.find((item) => String(item.id) === form.inventory_item_id);
  const stockDisplayName = form.inventory_destination === "existing"
    ? selectedStock?.name || form.inventory_name || "Selecione um item do estoque"
    : form.inventory_destination === "new"
      ? form.inventory_name.trim() || "Preencha o nome técnico do item"
      : "Será definido ao receber";


  const query = useMemo(() => {
    const params = new URLSearchParams();
    if (company !== "all") params.set("company_code", company);
    if (search.trim()) params.set("search", search.trim());
    if (statusFilter === "overdue") params.set("overdue", "true");
    else if (statusFilter === "due_soon") params.set("due_soon", "true");
    else if (statusFilter !== "all") params.set("status", statusFilter);
    return params.toString();
  }, [company, search, statusFilter]);

  async function load() {
    setError("");
    const companyQuery = company === "all" ? "" : `?company_code=${company}`;
    const requestQuery = company === "all" ? "" : `?company_code=${company}`;
    const [summaryResult, ordersResult, suppliersResult, requestsResult, notificationsResult] = await Promise.allSettled([
      apiClient.request<PurchaseSummary>(`/api/purchasing/summary${companyQuery}`),
      apiClient.request<PurchaseOrder[]>(`/api/purchasing/orders${query ? `?${query}` : ""}`),
      apiClient.request<Supplier[]>("/api/purchasing/suppliers"),
      apiClient.request<MaterialRequest[]>(`/api/purchasing/material-requests${requestQuery}`),
      apiClient.request<PurchaseNotificationSummary>("/api/notifications?limit=20&unread_only=true"),
    ]);

    const failures: string[] = [];

    if (summaryResult.status === "fulfilled") {
      setSummary(summaryResult.value);
    } else {
      failures.push(`Resumo: ${summaryResult.reason instanceof Error ? summaryResult.reason.message : "falha ao carregar"}`);
    }

    if (ordersResult.status === "fulfilled") {
      setOrders(ordersResult.value);
    } else {
      failures.push(`Pedidos: ${ordersResult.reason instanceof Error ? ordersResult.reason.message : "falha ao carregar"}`);
    }

    if (suppliersResult.status === "fulfilled") {
      const supplierData = suppliersResult.value;
      setSuppliers(supplierData);
      setForm((current) => {
        if (current.supplier_id || !supplierData[0]) return current;
        return { ...current, supplier_id: String(supplierData[0].id) };
      });
    } else {
      failures.push(`Fornecedores: ${suppliersResult.reason instanceof Error ? suppliersResult.reason.message : "falha ao carregar"}`);
    }

    if (requestsResult.status === "fulfilled") {
      setMaterialRequests(requestsResult.value);
    } else {
      failures.push(`Solicitações: ${requestsResult.reason instanceof Error ? requestsResult.reason.message : "falha ao carregar"}`);
    }

    if (notificationsResult.status === "fulfilled") {
      setNotifications(notificationsResult.value);
    } else {
      failures.push(`Notificações: ${notificationsResult.reason instanceof Error ? notificationsResult.reason.message : "falha ao carregar"}`);
    }

    if (failures.length) {
      setError(failures.join(" | "));
    }
  }

  useEffect(() => {
    void load();
    const refresh = () => void load();
    const timer = window.setInterval(refresh, 30000);
    window.addEventListener("focus", refresh);
    return () => { window.clearInterval(timer); window.removeEventListener("focus", refresh); };
  }, [query, company]);

  // A pesquisa é informativa antes da compra e permite escolher o destino
  // físico somente no recebimento. Ela não altera o pedido ou o estoque.
  useEffect(() => {
    if (view !== "new" || !canViewValues) return;
    let active = true;
    const timer = window.setTimeout(async () => {
      setStockLoading(true);
      setStockError("");
      try {
        const q = stockSearch.trim() || form.product_name.trim();
        const selectedId = form.inventory_destination === "existing" ? Number(form.inventory_item_id) || 0 : 0;
        const data = await apiClient.request<StockLookup>(
          `/api/purchasing/stock-options?company_code=${encodeURIComponent(form.company_code)}&search=${encodeURIComponent(q)}${selectedId ? `&selected_id=${selectedId}` : ""}`,
        );
        if (active) { setStockOptions(data.items); setStockFormats(data.formats); }
      } catch (cause) {
        if (active) setStockError(cause instanceof Error ? cause.message : "Consulta de estoque indisponível.");
      } finally {
        if (active) setStockLoading(false);
      }
    }, 300);
    return () => { active = false; window.clearTimeout(timer); };
  }, [view, form.company_code, form.product_name, form.inventory_destination, form.inventory_item_id, stockSearch, canViewValues]);

  useEffect(() => {
    if (view === "audit") {
      setError("");
      apiClient.request<PurchaseAudit[]>("/api/purchasing/audit")
        .then(setAudit)
        .catch((reason: Error) => setError(`Auditoria: ${reason.message}`));
    }
  }, [view]);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const filter = params.get("filtro");
    const requestedView = params.get("view") as View | null;
    const purchaseId = Number(params.get("pedido"));

    if (requestedView && ["dashboard", "requests", "new", "orders", "report", "audit"].includes(requestedView)) {
      setView(requestedView);
    }

    if (filter === "atrasados") {
      setStatusFilter("overdue");
      setView("orders");
    } else if (filter === "proximas") {
      setStatusFilter("due_soon");
      setView("orders");
    }

    if (Number.isInteger(purchaseId) && purchaseId > 0) {
      apiClient.request<PurchaseOrder>(`/api/purchasing/orders/${purchaseId}`)
        .then(openEdit)
        .catch((reason: Error) => setError(reason.message));
    }
  }, []);

  function openNew() {
    if (!canViewValues) return;
    const next = emptyForm();
    if (suppliers[0]) next.supplier_id = String(suppliers[0].id);
    setEditing(null);
    setAttachment(null);
    setStockSearch("");
    setStockOptions([]);
    setForm(next);
    setView("new");
  }

  function openEdit(order: PurchaseOrder) {
    if (!canViewValues) return;
    setEditing(order);
    setAttachment(null);
    setStockSearch("");
    setStockOptions([]);
    setForm({
      company_code: order.company_code,
      supplier_id: String(order.supplier_id),
      equipment_serial: order.equipment_serial || "",
      invoice_number: order.invoice_number || "",
      client_destination: order.client_destination || "",
      product_name: order.product_name,
      inventory_destination: order.inventory_destination || "",
      inventory_item_id: order.inventory_item_id ? String(order.inventory_item_id) : "",
      inventory_name: order.inventory_name || "",
      inventory_mode: order.inventory_mode || "bulk",
      inventory_serial: order.inventory_serial || "",
      inventory_category: order.inventory_category || "componentes",
      inventory_format_id: order.inventory_format_id ? String(order.inventory_format_id) : "",
      quantity: String(order.quantity),
      total_amount: String(order.total_amount ?? "").replace(".", ","),
      origin: order.origin,
      tracking_code: order.tracking_code || "",
      purchase_date: order.purchase_date,
      estimated_delivery_date: order.estimated_delivery_date,
      status: order.status,
      product_link: order.product_link || "",
      notes: order.notes || "",
    });
    setView("new");
  }

  async function saveOrder(event: React.FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError("");
    setMessage("");
    try {
      if (!form.supplier_id || !Number.isInteger(Number(form.supplier_id)) || Number(form.supplier_id) <= 0) {
        throw new Error("Selecione ou cadastre um fornecedor antes de salvar a compra.");
      }
      // Pedidos antigos já recebidos na V2 não possuíam estes campos:
      // permitir alterar dados não físicos sem forçar novo destino.
      if (form.status === "delivered" && editing?.status !== "delivered") {
        if (!form.inventory_destination) throw new Error("Antes de confirmar a entrega, escolha o destino no Estoque.");
        if (form.inventory_destination === "existing" && !form.inventory_item_id) throw new Error("Selecione o item existente para somar a quantidade.");
        if (form.inventory_destination === "new" && form.inventory_name.trim().length < 2) {
          throw new Error("Informe o nome técnico do item no Estoque; não será copiado automaticamente do título da compra.");
        }
        if (form.inventory_destination === "new" && form.inventory_mode === "serialized" && (Number(form.quantity) !== 1 || !form.inventory_serial.trim())) {
          throw new Error("Item individualizado exige quantidade 1 e número de série.");
        }
      }
      const payload = {
        ...form,
        supplier_id: Number(form.supplier_id),
        quantity: Number(form.quantity),
        inventory_destination: form.inventory_destination || null,
        inventory_item_id: form.inventory_destination === "existing" ? Number(form.inventory_item_id) || null : null,
        inventory_name: form.inventory_destination === "new" ? form.inventory_name.trim() || null
          : form.inventory_destination === "existing" ? (editing?.status === "delivered" ? form.inventory_name || null : selectedStock?.name || form.inventory_name || null)
          : null,
        inventory_mode: form.inventory_destination === "new" ? form.inventory_mode : null,
        inventory_serial: form.inventory_destination === "new" && form.inventory_mode === "serialized" ? form.inventory_serial.trim() || null : null,
        inventory_category: form.inventory_destination === "new" ? form.inventory_category : null,
        inventory_format_id: form.inventory_destination === "new" && form.inventory_format_id ? Number(form.inventory_format_id) : null,
        total_amount: Number(form.total_amount.replace(/\./g, "").replace(",", ".")),
        equipment_serial: form.equipment_serial || null,
        invoice_number: form.invoice_number || null,
        client_destination: form.client_destination || null,
        tracking_code: form.tracking_code || null,
        product_link: form.product_link || null,
        notes: form.notes || null,
        ...(editing ? { delivered_at: editing.delivered_at || null } : {}),
      };
      const order = await apiClient.request<PurchaseOrder>(
        editing ? `/api/purchasing/orders/${editing.id}` : "/api/purchasing/orders",
        {
          method: editing ? "PUT" : "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        },
      );
      if (attachment) {
        const body = new FormData();
        body.append("file", attachment);
        await apiClient.request(`/api/purchasing/orders/${order.id}/attachment`, { method: "POST", body });
      }
      setMessage(form.status === "delivered" ? "Compra entregue: entrada lançada automaticamente no Estoque. Consulte a etiqueta no módulo Estoque." : (editing ? "Compra atualizada." : `Compra ${order.code} registrada.`));
      setView("orders");
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Não foi possível salvar a compra.");
    } finally {
      setSaving(false);
    }
  }

  async function deleteOrder() {
    if (!editing || !window.confirm(`Excluir a compra ${editing.code}?`)) return;
    await apiClient.request(`/api/purchasing/orders/${editing.id}`, { method: "DELETE" });
    setEditing(null);
    setView("orders");
    await load();
  }

  async function addSupplier(event: React.FormEvent) {
    event.preventDefault();
    const name = supplierName.trim().replace(/\s+/g, " ");
    if (name.length < 2) {
      setSupplierError("Informe um nome de fornecedor com pelo menos 2 caracteres.");
      return;
    }

    setSupplierSaving(true);
    setSupplierError("");
    try {
      const supplier = await apiClient.request<Supplier>("/api/purchasing/suppliers", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, origin: form.origin }),
      });

      // O POST só retorna depois do COMMIT no backend. Portanto o objeto
      // retornado já é o fornecedor persistido e pode ser selecionado
      // imediatamente. A atualização da lista é feita sem transformar uma
      // eventual falha de GET em falso erro de cadastro.
      setSuppliers((items) => {
        const withoutCurrent = items.filter((item) => item.id !== supplier.id);
        return [...withoutCurrent, supplier].sort((a, b) => a.name.localeCompare(b.name));
      });
      setForm((current) => ({ ...current, supplier_id: String(supplier.id) }));
      setSupplierName("");
      setSupplierModal(false);
      setMessage(`Fornecedor ${supplier.name} salvo e selecionado.`);

      void apiClient.request<Supplier[]>("/api/purchasing/suppliers")
        .then(setSuppliers)
        .catch(() => undefined);
    } catch (reason) {
      setSupplierError(reason instanceof Error ? reason.message : "Não foi possível cadastrar o fornecedor.");
    } finally {
      setSupplierSaving(false);
    }
  }

  const requestStats = useMemo(() => ({
    approval: materialRequests.filter((item) => item.status === "awaiting_approval").length,
    buying: materialRequests.filter((item) => ["approved", "purchasing"].includes(item.status)).length,
    waiting: materialRequests.filter((item) => ["purchased", "in_transit"].includes(item.status)).length,
  }), [materialRequests]);
  const activeRequests = useMemo(() => materialRequests.filter((item) => !["rejected", "cancelled", "delivered_to_lab"].includes(item.status)).slice(0, 6), [materialRequests]);
  const purchaseAlerts = useMemo(() => notifications.items.filter((item) => ["purchase_request", "material_request_approved", "purchase", "commercial_sale_approved"].includes(item.category)).slice(0, 5), [notifications]);

  const nav: { id: View; label: string; icon: typeof ShoppingCart }[] = [
    { id: "dashboard", label: "Dashboard & alertas", icon: Boxes },
    { id: "requests", label: "Solicitações de material", icon: FileSearch },
    ...(canViewValues ? [{ id: "new" as View, label: "Lançar nova compra", icon: PackagePlus }] : []),
    { id: "orders", label: "Gerenciar pedidos", icon: ClipboardList },
    ...(canViewValues ? [{ id: "report" as View, label: "Relatório de gastos", icon: FileBarChart }] : []),
    { id: "audit", label: "Auditoria de compras", icon: History },
  ];

  return (
    <main className="purchasing-shell sentico-shell">
      <SenticoSidebar
        user={user}
        onLogout={onLogout}
        sectionLabel="Compras"
        sectionItems={nav.map(({ id, label, icon }) => ({
          id, label, icon, active: view === id,
          onClick: () => id === "new" ? openNew() : setView(id),
        }))}
      />

      <section className="purchasing-content sentico-content">
        <header className="purchasing-header">
          <div><p>GESTÃO DE SUPRIMENTOS</p><h1>{view === "new" ? (editing ? "Editar compra" : "Registrar pedido de compra") : view === "requests" ? "Solicitações de material" : view === "orders" ? "Gerenciar pedidos" : view === "report" ? "Relatório de gastos" : view === "audit" ? "Auditoria de compras" : "Compras e entregas"}</h1></div>
          {canViewValues && <motion.button className="primary-action" onClick={openNew} whileHover={{ y: -2 }} whileTap={{ scale: 0.97 }}><Plus size={18} />Nova compra</motion.button>}
        </header>

        <div className="company-switcher">
          <Building2 size={17} />
          <button className={company === "all" ? "active" : ""} onClick={() => setCompany("all")}>Consolidado</button>
          {companies.map((item) => <button key={item.code} className={company === item.code ? "active" : ""} onClick={() => setCompany(item.code)}>{item.label}</button>)}
        </div>

        {error && <div className="purchase-alert error">{error}</div>}
        {message && <div className="purchase-alert success">{message}</div>}

        {view === "dashboard" && <>
          <section className="purchase-kpis">
            <article><ShoppingCart /><span>Pedidos em aberto</span><strong>{summary?.total_open ?? 0}</strong></article>
            <article className="danger"><AlertTriangle /><span>Entregas atrasadas</span><strong>{summary?.overdue ?? 0}</strong></article>
            <article className="warning"><CalendarClock /><span>Próximos 7 dias</span><strong>{summary?.due_soon ?? 0}</strong></article>
            <article className="success"><PackageCheck /><span>Entregues no mês</span><strong>{summary?.delivered_month ?? 0}</strong></article>
            {canViewValues && <article><Boxes /><span>Valor em aberto</span><strong>{money(summary?.total_value_open)}</strong></article>}
          </section>
          <section className="material-request-kpis purchase-dashboard-demands">
            <button onClick={() => setView("requests")}><CheckCircle2 /><span>Solicitações aguardando aprovação</span><strong>{requestStats.approval}</strong></button>
            <button onClick={() => setView("requests")}><ShoppingCart /><span>Materiais para comprar</span><strong>{requestStats.buying}</strong></button>
            <button onClick={() => setView("requests")}><Truck /><span>Comprados / aguardando chegada</span><strong>{requestStats.waiting}</strong></button>
          </section>
          <section className="purchase-panel purchase-demand-panel">
            <div className="panel-title"><div><small>CENTRAL DE DEMANDAS</small><h2>Solicitações e notificações recentes</h2></div><button onClick={() => setView("requests")}>Abrir solicitações <ChevronRight size={16} /></button></div>
            <div className="purchase-demand-grid">
              <div className="purchase-demand-list">
                <h3>Materiais pendentes</h3>
                {activeRequests.map((item) => <button key={item.id} onClick={() => setView("requests")}><div><strong>{item.code} · {item.item_name}</strong><span>{item.work_order_number || "Compra avulsa"} · {item.quantity} un.</span></div><em className={`material-request-status ${item.status}`}>{item.status === "awaiting_approval" ? "Aguardando aprovação" : item.status === "approved" ? "Aprovado" : item.status === "purchasing" ? "Em compra" : item.status === "purchased" ? "Comprado" : item.status === "in_transit" ? "Em trânsito" : item.status}</em></button>)}
                {!activeRequests.length && <p className="purchase-demand-empty">Nenhuma solicitação pendente.</p>}
              </div>
              <div className="purchase-notification-list">
                <h3><Bell size={16}/> Alertas do módulo</h3>
                {purchaseAlerts.map((item) => {
                  const destination = notificationDestination(item);
                  return <button key={item.id} onClick={() => destination ? navigate(destination) : undefined}>
                    <strong>{item.title}</strong>
                    <span>{item.message}</span>
                    <small>{new Date(item.created_at).toLocaleString("pt-BR")}</small>
                    {item.category === "commercial_sale_approved" && destination && <em className="purchase-notification-action">Abrir orçamento no Comercial <ChevronRight size={14}/></em>}
                  </button>;
                })}
                {!purchaseAlerts.length && <p className="purchase-demand-empty">Nenhum alerta novo para Compras.</p>}
              </div>
            </div>
          </section>
          <section className="purchase-panel">
            <div className="panel-title"><div><small>RADAR DE COMPRAS</small><h2>Pedidos que exigem atenção</h2></div><button onClick={() => setView("orders")}>Ver todos <ChevronRight size={16} /></button></div>
            <OrderTable orders={orders.slice(0, 8)} onOpen={canViewValues ? openEdit : undefined} canViewValues={canViewValues} />
          </section>
        </>}

        {view === "orders" && <section className="purchase-panel">
          <div className="panel-title orders-title"><div><small>ACOMPANHAMENTO</small><h2>Pedidos de compra</h2></div><div className="order-filters"><label><Search size={17} /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Série, NF, produto, fornecedor..." /></label><select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value as typeof statusFilter)}><option value="all">Todos os status</option><option value="overdue">Atrasados</option><option value="due_soon">Próximas entregas</option>{Object.entries(statusLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></div></div>
          <OrderTable orders={orders} onOpen={canViewValues ? openEdit : undefined} canViewValues={canViewValues} />
        </section>}

        {view === "requests" && <MaterialRequestsPanel canViewValues={canViewValues} />}

        {canViewValues && view === "report" && <PurchasingSpendingReport company={company} />}

        {canViewValues && view === "new" && <form className="purchase-form" onSubmit={saveOrder}>
          <div className="form-top"><button type="button" className="supplier-manager" onClick={() => { setSupplierError(""); setSupplierModal(true); }}><Settings size={17} />Cadastrar / selecionar fornecedor</button>{editing && <span className="purchase-code">{editing.code}</span>}</div>
          <div className="form-grid">
            <Field label="Empresa"><select value={form.company_code} disabled={editing?.status === "delivered"} onChange={(e) => setForm({ ...form, company_code: e.target.value as CompanyCode, inventory_destination: "", inventory_item_id: "", inventory_name: "" })}>{companies.map((item) => <option key={item.code} value={item.code}>{item.label}</option>)}</select></Field>
            <Field label="Nº série do equipamento"><input value={form.equipment_serial} onChange={(e) => setForm({ ...form, equipment_serial: e.target.value })} placeholder="Vínculo futuro com o laboratório" /></Field>
            <Field label="NF da compra"><input value={form.invoice_number} onChange={(e) => setForm({ ...form, invoice_number: e.target.value })} /></Field>
            <Field label="Cliente/destino"><input value={form.client_destination} onChange={(e) => setForm({ ...form, client_destination: e.target.value })} placeholder="Para quem é?" /></Field>
            <Field label="Título / descrição da compra*" wide><input required value={form.product_name} onChange={(e) => setForm({ ...form, product_name: e.target.value })} placeholder="Ex.: Inversor, máscara, cabos..." /></Field>
            <Field label="Quantidade*"><input required type="number" min="1" value={form.quantity} onChange={(e) => setForm({ ...form, quantity: e.target.value })} /></Field>
            <Field label="Valor total (R$)*"><input required value={form.total_amount} onChange={(e) => setForm({ ...form, total_amount: e.target.value })} placeholder="0,00" /></Field>
            <Field label="Loja/fornecedor*"><select required value={form.supplier_id} onChange={(e) => setForm({ ...form, supplier_id: e.target.value })}><option value="">Selecione</option>{suppliers.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></Field>
            <Field label="Origem"><select value={form.origin} onChange={(e) => setForm({ ...form, origin: e.target.value as PurchaseOrigin })}><option value="national">Nacional</option><option value="international">Internacional</option></select></Field>
            <Field label="Código de rastreio"><input value={form.tracking_code} onChange={(e) => setForm({ ...form, tracking_code: e.target.value })} /></Field>
            <Field label="Data da compra"><input type="date" value={form.purchase_date} onChange={(e) => setForm({ ...form, purchase_date: e.target.value })} /></Field>
            <Field label="Prazo de entrega estimado"><input type="date" value={form.estimated_delivery_date} onChange={(e) => setForm({ ...form, estimated_delivery_date: e.target.value })} /></Field>
            <div className="purchase-stock-panel">
              <div className="purchase-stock-heading"><Boxes size={19}/><div><strong>Item de estoque e destino do recebimento</strong><p>O título comercial da compra é independente do nome técnico que ficará no Estoque.</p></div></div>
              <div className="purchase-name-comparison" aria-live="polite">
                <div><small>Título do pedido</small><strong>{form.product_name.trim() || "Informe o título da compra"}</strong></div>
                <span aria-hidden="true">≠</span>
                <div><small>Nome no Estoque</small><strong>{stockDisplayName}</strong></div>
              </div>
              <label className="purchase-stock-search">Pesquisar antes de comprar — nome, etiqueta ou série
                <input value={stockSearch} onChange={(e) => setStockSearch(e.target.value)} placeholder="Buscar no estoque existente..." />
              </label>
              {stockLoading && <small>Consultando estoque...</small>}
              {stockError && <small className="purchase-stock-error">{stockError}</small>}
              <div className="purchase-stock-found">
                {stockOptions.slice(0, 8).map((item) => <div key={item.id}>
                  <span><strong>{item.stock_code} · {item.name}</strong><small>{item.mode === "serialized" ? `Individual / Série ${item.manufacturer_serial || "—"}` : "Componente por quantidade"}</small></span>
                  <em>{item.quantity} disponível{item.quantity !== 1 ? "is" : ""}</em>
                  {item.mode === "bulk" && <button type="button" disabled={editing?.status === "delivered"} onClick={() => setForm((f) => ({ ...f, inventory_destination: "existing", inventory_item_id: String(item.id), inventory_name: item.name }))}>Usar este item</button>}
                </div>)}
                {!stockOptions.length && !stockLoading && !stockError && <p>Nenhum item encontrado. É possível cadastrar um novo ao receber.</p>}
              </div>
              <div className="purchase-stock-choice">
                <label>Quando chegar, enviar para:
                  <select value={form.inventory_destination} disabled={editing?.status === "delivered"} onChange={(e) => setForm((f) => ({ ...f, inventory_destination: e.target.value as FormState["inventory_destination"], inventory_item_id: "", inventory_name: e.target.value === "existing" ? "" : f.inventory_name }))}>
                    <option value="">Definir no recebimento (opcional agora)</option>
                    <option value="existing">Somar quantidade em item existente</option>
                    <option value="new">Criar novo item no Estoque</option>
                  </select>
                </label>
                {form.inventory_destination === "existing" && <label>Item que receberá o saldo
                  <select required={form.status === "delivered"} disabled={editing?.status === "delivered"} value={form.inventory_item_id} onChange={(e) => { const chosen = stockOptions.find(item => String(item.id) === e.target.value); setForm((f) => ({ ...f, inventory_item_id: e.target.value, inventory_name: chosen?.name || "" })); }}>
                    <option value="">Selecione um componente cadastrado</option>
                    {stockOptions.filter((item) => item.mode === "bulk").map((item) => <option key={item.id} value={item.id}>{item.stock_code} · {item.name} — saldo {item.quantity}</option>)}
                    {form.inventory_item_id && !stockOptions.some((item) => String(item.id) === form.inventory_item_id) && <option value={form.inventory_item_id}>Item selecionado #{form.inventory_item_id} (fora do filtro)</option>}
                  </select>
                </label>}
                {form.inventory_destination === "existing" && <label>Nome adotado do item já cadastrado
                  <input readOnly value={stockDisplayName} aria-label="Nome no Estoque (cadastro existente)" title="O nome vem do cadastro selecionado no Estoque" />
                </label>}
                {form.inventory_destination === "new" && <>
                  <label>Nome técnico do novo item no Estoque (independente do pedido)
                    <input required={form.status === "delivered"} value={form.inventory_name} disabled={editing?.status === "delivered"} maxLength={220} onChange={(e) => setForm((f) => ({ ...f, inventory_name: e.target.value }))} placeholder="Ex.: Capacitor 470uF 450V"/>
                  </label>
                  <label>Tipo de controle
                    <select disabled={editing?.status === "delivered"} value={form.inventory_mode} onChange={(e) => setForm((f) => ({ ...f, inventory_mode: e.target.value as "bulk" | "serialized", inventory_serial: "" }))}>
                      <option value="bulk">Quantidade / componentes (mesma etiqueta)</option>
                      <option value="serialized">Item único / número de série</option>
                    </select>
                  </label>
                  <label>Categoria técnica
                    <input disabled={editing?.status === "delivered"} maxLength={80} value={form.inventory_category} onChange={(e) => setForm((f) => ({ ...f, inventory_category: e.target.value, inventory_format_id: "" }))} placeholder="resistor, capacitor, transistor..."/>
                  </label>
                  <label>Formato / encapsulamento
                    <select disabled={editing?.status === "delivered"} value={form.inventory_format_id} onChange={(e) => setForm((f) => ({ ...f, inventory_format_id: e.target.value }))}>
                      <option value="">Sem formato especificado</option>
                      {stockFormats.filter((v) => v.category === form.inventory_category.trim().toLowerCase()).map((v) => <option key={v.id} value={v.id}>{v.name}</option>)}
                    </select>
                  </label>
                  {form.inventory_mode === "serialized" && <label>Número de série do item recebido
                    <input required={form.status === "delivered"} disabled={editing?.status === "delivered"} maxLength={120} value={form.inventory_serial} onChange={(e) => setForm((f) => ({ ...f, inventory_serial: e.target.value }))} placeholder="Série da peça, não da OS" />
                  </label>}
                </>}
              </div>
              <p className="purchase-stock-footnote">A confirmação de Entregue exige decidir o destino. A entrada mantém custo histórico e número da compra. O local físico poderá ser definido depois no mapa do Estoque.</p>
              {editing?.status === "delivered" && <small>Recebimento já registrado: alterações de destino exigem estorno auditado.</small>}
            </div>
            <Field label="Status atual" wide><select value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value as PurchaseStatus })}>{Object.entries(statusLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></Field>
            <Field label="Observações / link do produto" wide><textarea value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} placeholder="Observações do pedido" /><div className="link-field"><Link2 size={16} /><input value={form.product_link} onChange={(e) => setForm({ ...form, product_link: e.target.value })} placeholder="https://..." /></div></Field>
            <Field label="Anexo" wide><label className="attachment-input"><Paperclip size={18} /><span>{attachment?.name || editing?.attachment_name || "Anexar pedido, boleto, nota ou comprovante"}</span><input type="file" accept=".pdf,.jpg,.jpeg,.png,.webp" onChange={(e) => setAttachment(e.target.files?.[0] || null)} /></label></Field>
          </div>
          <div className="form-actions">{editing && <button type="button" className="danger-button" onClick={deleteOrder}>Excluir compra</button>}<button type="button" className="secondary-button" onClick={() => setView("orders")}>Cancelar</button><motion.button className="save-button" disabled={saving} whileTap={{ scale: 0.98 }}>{saving ? "Salvando..." : editing ? "Salvar alterações" : "Salvar compra no sistema"}</motion.button></div>
        </form>}

        {view === "audit" && <section className="purchase-panel"><div className="panel-title"><div><small>RASTREABILIDADE</small><h2>Histórico de ações</h2></div></div><div className="audit-list">{audit.map((item) => <article key={item.id}><History size={17} /><div><strong>{item.description}</strong><span>{item.user_name} · {new Date(item.created_at).toLocaleString("pt-BR")}</span></div></article>)}{audit.length === 0 && <div className="empty-state">Nenhum evento de auditoria.</div>}</div></section>}
      </section>

      <AnimatePresence>{supplierModal && <motion.div className="modal-backdrop" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}><motion.form className="supplier-modal" onSubmit={addSupplier} initial={{ y: 24, opacity: 0 }} animate={{ y: 0, opacity: 1 }} exit={{ y: 24, opacity: 0 }}><button type="button" className="modal-close" onClick={() => setSupplierModal(false)}><X /></button><Store size={28} /><h2>Novo fornecedor</h2><p>Cadastre lojas e fornecedores para reutilizar nos pedidos. O fornecedor é obrigatório para concluir uma compra.</p>{supplierError && <div className="purchase-alert error">{supplierError}</div>}<input autoFocus required minLength={2} value={supplierName} onChange={(e) => { setSupplierName(e.target.value); if (supplierError) setSupplierError(""); }} placeholder="Nome da loja ou fornecedor" /><button className="save-button" disabled={supplierSaving}>{supplierSaving ? "Cadastrando..." : "Cadastrar e selecionar"}</button></motion.form></motion.div>}</AnimatePresence>
    </main>
  );
}

function Field({ label, wide, children }: { label: string; wide?: boolean; children: React.ReactNode }) {
  return <label className={wide ? "field wide" : "field"}><span>{label}</span>{children}</label>;
}

function OrderTable({ orders, onOpen, canViewValues }: { orders: PurchaseOrder[]; onOpen?: (order: PurchaseOrder) => void; canViewValues: boolean }) {
  return <div className="orders-table"><div className="order-row order-head"><span>Pedido / série</span><span>Fornecedor</span><span>Produto / destino</span><span>Compra</span><span>Previsão</span><span>Status</span>{canViewValues && <span>Valor</span>}<span /></div>{orders.map((order) => { const tone = statusTone(order); return <motion.button key={order.id} className="order-row" onClick={() => onOpen?.(order)} whileHover={{ x: 2 }} whileTap={{ scale: 0.995 }}><span><strong>{order.code}</strong><small>{order.equipment_serial || "Sem série vinculada"}</small></span><span><strong>{order.supplier_name}</strong><small>{order.origin === "national" ? "Nacional" : "Internacional"}</small></span><span><strong>{order.product_name}</strong><small>{order.client_destination || "Sem destino informado"}</small></span><span>{dateLabel(order.purchase_date)}</span><span className={tone === "overdue" ? "date-overdue" : ""}>{dateLabel(order.estimated_delivery_date)}</span><span><em className={`status-pill ${tone}`}>{tone === "overdue" ? "Atrasada" : statusLabels[order.status]}</em></span>{canViewValues && <span className="amount">{money(order.total_amount)}</span>}<ChevronRight size={18} /></motion.button>; })}{orders.length === 0 && <div className="empty-state">Nenhuma compra encontrada.</div>}</div>;
}
