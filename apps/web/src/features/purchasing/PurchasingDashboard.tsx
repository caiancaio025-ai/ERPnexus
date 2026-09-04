import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  ArrowLeft,
  Boxes,
  Building2,
  CalendarClock,
  CheckCircle2,
  ChevronRight,
  ClipboardList,
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
import { NexusMark } from "../../shared/ui/NexusMark";
import { AnimatePresence, motion } from "motion/react";
import { useNavigate } from "react-router-dom";

import { apiClient } from "../../shared/api/apiClient";
import type { AuthUser } from "../auth/AuthCard";
import { MaterialRequestsPanel } from "./MaterialRequestsPanel";
import type {
  CompanyCode,
  PurchaseAudit,
  PurchaseOrder,
  PurchaseOrigin,
  PurchaseStatus,
  PurchaseSummary,
  Supplier,
} from "./types";
import "./purchasing.css";

type Props = { user: AuthUser; onLogout: () => void };
type View = "dashboard" | "requests" | "new" | "orders" | "audit";

type FormState = {
  company_code: CompanyCode;
  supplier_id: string;
  equipment_serial: string;
  invoice_number: string;
  client_destination: string;
  product_name: string;
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
    const [summaryResult, ordersResult, suppliersResult] = await Promise.allSettled([
      apiClient.request<PurchaseSummary>(`/api/purchasing/summary${companyQuery}`),
      apiClient.request<PurchaseOrder[]>(`/api/purchasing/orders${query ? `?${query}` : ""}`),
      apiClient.request<Supplier[]>("/api/purchasing/suppliers"),
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
      if (!form.supplier_id && supplierData[0]) {
        setForm((current) => ({ ...current, supplier_id: String(supplierData[0].id) }));
      }
    } else {
      failures.push(`Fornecedores: ${suppliersResult.reason instanceof Error ? suppliersResult.reason.message : "falha ao carregar"}`);
    }

    if (failures.length) {
      setError(failures.join(" | "));
    }
  }

  useEffect(() => {
    void load();
  }, [query, company]);

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
    const purchaseId = Number(params.get("pedido"));

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
    setForm(next);
    setView("new");
  }

  function openEdit(order: PurchaseOrder) {
    if (!canViewValues) return;
    setEditing(order);
    setAttachment(null);
    setForm({
      company_code: order.company_code,
      supplier_id: String(order.supplier_id),
      equipment_serial: order.equipment_serial || "",
      invoice_number: order.invoice_number || "",
      client_destination: order.client_destination || "",
      product_name: order.product_name,
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
      const payload = {
        ...form,
        supplier_id: Number(form.supplier_id),
        quantity: Number(form.quantity),
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
      setMessage(editing ? "Compra atualizada." : `Compra ${order.code} registrada.`);
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

  const nav: { id: View; label: string; icon: typeof ShoppingCart }[] = [
    { id: "dashboard", label: "Dashboard & alertas", icon: Boxes },
    { id: "requests", label: "Solicitações de material", icon: FileSearch },
    ...(canViewValues ? [{ id: "new" as View, label: "Lançar nova compra", icon: PackagePlus }] : []),
    { id: "orders", label: "Gerenciar pedidos", icon: ClipboardList },
    { id: "audit", label: "Auditoria de compras", icon: History },
  ];

  return (
    <main className="purchasing-shell">
      <aside className="purchasing-sidebar">
        <div className="purchasing-brand"><NexusMark/><strong>NEXUS</strong></div>
        <div className="purchasing-module"><ShoppingCart size={20} /><div><small>MÓDULO</small><strong>Compras</strong></div></div>
        <nav>
          {nav.map((item) => {
            const Icon = item.icon;
            return <motion.button key={item.id} className={view === item.id ? "active" : ""} onClick={() => item.id === "new" ? openNew() : setView(item.id)} whileTap={{ scale: 0.97 }}><Icon size={18} />{item.label}</motion.button>;
          })}
          <button onClick={() => navigate("/painel")}><ArrowLeft size={18} />Voltar ao painel geral</button>
        </nav>
        <div className="purchasing-user"><span>{user.name.slice(0, 2).toUpperCase()}</span><div><strong>{user.name}</strong><small>{user.role}</small></div><button onClick={onLogout} aria-label="Sair"><LogOut size={18} /></button></div>
      </aside>

      <section className="purchasing-content">
        <header className="purchasing-header">
          <div><p>GESTÃO DE SUPRIMENTOS</p><h1>{view === "new" ? (editing ? "Editar compra" : "Registrar pedido de compra") : view === "requests" ? "Solicitações de material" : view === "orders" ? "Gerenciar pedidos" : view === "audit" ? "Auditoria de compras" : "Compras e entregas"}</h1></div>
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

        {canViewValues && view === "new" && <form className="purchase-form" onSubmit={saveOrder}>
          <div className="form-top"><button type="button" className="supplier-manager" onClick={() => { setSupplierError(""); setSupplierModal(true); }}><Settings size={17} />Cadastrar / selecionar fornecedor</button>{editing && <span className="purchase-code">{editing.code}</span>}</div>
          <div className="form-grid">
            <Field label="Empresa"><select value={form.company_code} onChange={(e) => setForm({ ...form, company_code: e.target.value as CompanyCode })}>{companies.map((item) => <option key={item.code} value={item.code}>{item.label}</option>)}</select></Field>
            <Field label="Nº série do equipamento"><input value={form.equipment_serial} onChange={(e) => setForm({ ...form, equipment_serial: e.target.value })} placeholder="Vínculo futuro com o laboratório" /></Field>
            <Field label="NF da compra"><input value={form.invoice_number} onChange={(e) => setForm({ ...form, invoice_number: e.target.value })} /></Field>
            <Field label="Cliente/destino"><input value={form.client_destination} onChange={(e) => setForm({ ...form, client_destination: e.target.value })} placeholder="Para quem é?" /></Field>
            <Field label="Produto comprado*" wide><input required value={form.product_name} onChange={(e) => setForm({ ...form, product_name: e.target.value })} placeholder="Ex.: Inversor, máscara, cabos..." /></Field>
            <Field label="Quantidade*"><input required type="number" min="1" value={form.quantity} onChange={(e) => setForm({ ...form, quantity: e.target.value })} /></Field>
            <Field label="Valor total (R$)*"><input required value={form.total_amount} onChange={(e) => setForm({ ...form, total_amount: e.target.value })} placeholder="0,00" /></Field>
            <Field label="Loja/fornecedor*"><select required value={form.supplier_id} onChange={(e) => setForm({ ...form, supplier_id: e.target.value })}><option value="">Selecione</option>{suppliers.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></Field>
            <Field label="Origem"><select value={form.origin} onChange={(e) => setForm({ ...form, origin: e.target.value as PurchaseOrigin })}><option value="national">Nacional</option><option value="international">Internacional</option></select></Field>
            <Field label="Código de rastreio"><input value={form.tracking_code} onChange={(e) => setForm({ ...form, tracking_code: e.target.value })} /></Field>
            <Field label="Data da compra"><input type="date" value={form.purchase_date} onChange={(e) => setForm({ ...form, purchase_date: e.target.value })} /></Field>
            <Field label="Prazo de entrega estimado"><input type="date" value={form.estimated_delivery_date} onChange={(e) => setForm({ ...form, estimated_delivery_date: e.target.value })} /></Field>
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
