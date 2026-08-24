import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  ArrowLeft, BadgeDollarSign, CheckCircle2, ClipboardList, FileText, FlaskConical,
  History, Image, LogOut, Pencil, Plus, Printer, RefreshCw, Save, Search, Settings, ShieldCheck,
  Trash2, UploadCloud, UserRoundCog, Users, Wrench, X,
} from "lucide-react";

import { apiClient } from "../../shared/api/apiClient";
import type { AuthUser } from "../auth/AuthCard";
import { ActionButton } from "./components/ActionButton";
import { QuoteEditor } from "./components/QuoteEditor";
import { MaterialsPanel } from "./components/MaterialsPanel";
import { EquipmentDocumentsPanel } from "./components/EquipmentDocumentsPanel";
import type {
  CompanyCode, Customer, Priority, StatusHistory, Technician, WorkOrder,
  WorkOrderPage, WorkOrderStatus, WorkOrderSummary,
} from "./types";
import "./laboratory.css";

type Props = { user: AuthUser; onLogout: () => void };
type View = "orders" | "invoiced" | "no_repair" | "warranty";
type SettingsTab = "customers" | "technicians";
type DetailTab = "general" | "technical" | "financial" | "materials" | "status" | "documents" | "history" | "quote";

type FormState = {
  company_code: CompanyCode; customer_id: string; customer_name: string; serial_number: string;
  manufacturer: string; model: string; equipment_type: string; power: string; voltage: string;
  entry_invoice: string; exit_invoice: string; assigned_technician_id: string; priority: Priority;
  reported_defect: string; entry_condition: string; accessories_received: string; parts_cost: string;
  quoted_value: string; approved_value: string; internal_notes: string; customer_notes: string;
};

type DetailState = FormState & { id: number; number: string; status: WorkOrderStatus; version: number };
type LaboratoryPeriods = { latest_month: number; latest_year: number; years: number[] };

const companyLabels: Record<CompanyCode, string> = {
  universo_eletronica: "Universo Eletrônica",
  universo_automacao: "Universo Automação",
  solucoes_eletronica: "Soluções Eletrônica",
};
const priorityLabels: Record<Priority, string> = { low: "Baixa", normal: "Normal", high: "Alta", urgent: "Urgente" };
const monthLabels = [
  "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
  "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
];
const statusLabels: Record<WorkOrderStatus, string> = {
  received: "Entrada",
  awaiting_analysis: "Aguardando análise",
  in_analysis: "Analisado",
  awaiting_quote: "Analisado • preparando orçamento",
  quote_sent: "Ag. Aprovação",
  awaiting_approval: "Ag. Aprovação",
  approved: "Aprovado",
  rejected: "Reprovado",
  awaiting_parts: "Aprovado • ag. peças",
  in_repair: "Aprovado • em reparo",
  in_testing: "Aprovado • em testes",
  completed: "Pronto",
  awaiting_pickup: "Liberado",
  delivered: "Liberado • entregue",
  warranty: "Garantia",
  invoiced: "Faturado",
  cancelled: "Cancelado",
  no_repair: "Sem conserto",
};

// Status comerciais usados historicamente pela operação. Mantemos o fluxo técnico
// detalhado por baixo (análise, peças, reparo, testes), mas o operador pode continuar
// trabalhando com os mesmos marcos que já conhece no NEXUS.
const businessStatusOptions: Array<{ value: WorkOrderStatus; label: string }> = [
  { value: "received", label: "Entrada" },
  { value: "awaiting_approval", label: "Ag. Aprovação" },
  { value: "in_analysis", label: "Analisado" },
  { value: "approved", label: "Aprovado" },
  { value: "no_repair", label: "Sem conserto" },
  { value: "completed", label: "Pronto" },
  { value: "awaiting_pickup", label: "Liberado" },
  { value: "warranty", label: "Garantia" },
  { value: "invoiced", label: "Faturado" },
];

const operationalStatusOptions: Array<{ value: WorkOrderStatus; label: string }> = [
  { value: "awaiting_analysis", label: "Aguardando análise" },
  { value: "awaiting_quote", label: "Preparando orçamento" },
  { value: "quote_sent", label: "Orçamento enviado" },
  { value: "awaiting_parts", label: "Aguardando peças" },
  { value: "in_repair", label: "Em reparo" },
  { value: "in_testing", label: "Em testes" },
  { value: "delivered", label: "Entregue" },
  { value: "rejected", label: "Reprovado" },
  { value: "cancelled", label: "Cancelado" },
];

const operationalTransitions: Partial<Record<WorkOrderStatus, WorkOrderStatus[]>> = {
  received: ["awaiting_analysis"],
  awaiting_analysis: ["in_analysis"],
  in_analysis: ["awaiting_quote", "in_repair"],
  awaiting_quote: ["quote_sent"],
  quote_sent: ["awaiting_approval"],
  awaiting_approval: [],
  approved: ["awaiting_parts", "in_repair"],
  rejected: [],
  awaiting_parts: ["in_repair"],
  in_repair: ["awaiting_parts", "in_testing"],
  in_testing: ["in_repair"],
  completed: ["delivered"],
  awaiting_pickup: ["delivered"],
  delivered: [],
  warranty: ["in_analysis", "awaiting_parts", "in_repair", "in_testing"],
  invoiced: [],
  cancelled: [],
  no_repair: ["delivered"],
};

const emptyForm = (): FormState => ({
  company_code: "universo_eletronica", customer_id: "", customer_name: "", serial_number: "",
  manufacturer: "", model: "", equipment_type: "", power: "", voltage: "", entry_invoice: "",
  exit_invoice: "", assigned_technician_id: "", priority: "normal", reported_defect: "",
  entry_condition: "", accessories_received: "", parts_cost: "", quoted_value: "",
  approved_value: "", internal_notes: "", customer_notes: "",
});

function toDetail(order: WorkOrder): DetailState {
  return {
    id: order.id, number: order.number, status: order.status, version: order.version,
    company_code: order.company_code, customer_id: String(order.customer_id ?? ""),
    customer_name: order.customer_name, serial_number: order.equipment_serial ?? "",
    manufacturer: order.manufacturer ?? "", model: order.model ?? "",
    equipment_type: order.equipment_type ?? "", power: order.power ?? "", voltage: order.voltage ?? "",
    entry_invoice: order.entry_invoice ?? "", exit_invoice: order.exit_invoice ?? "",
    assigned_technician_id: String(order.assigned_technician_id ?? ""), priority: order.priority,
    reported_defect: order.reported_defect, entry_condition: order.entry_condition ?? "",
    accessories_received: order.accessories_received ?? "", parts_cost: order.parts_cost ?? "",
    quoted_value: order.quoted_value ?? "", approved_value: order.approved_value ?? "",
    internal_notes: order.internal_notes ?? "", customer_notes: order.customer_notes ?? "",
  };
}

export function LaboratoryDashboard({ user, onLogout }: Props) {
  const navigate = useNavigate();
  const [summary, setSummary] = useState<WorkOrderSummary | null>(null);
  const [pageData, setPageData] = useState<WorkOrderPage>({ items: [], page: 1, page_size: 25, total: 0, pages: 0 });
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [technicians, setTechnicians] = useState<Technician[]>([]);
  const [company, setCompany] = useState<CompanyCode | "all">("all");
  const [statusFilter, setStatusFilter] = useState<WorkOrderStatus | "all">("all");
  const now = new Date();
  const [monthFilter, setMonthFilter] = useState(now.getMonth() + 1);
  const [yearFilter, setYearFilter] = useState(now.getFullYear());
  const [availableYears, setAvailableYears] = useState<number[]>([now.getFullYear()]);
  const [periodReady, setPeriodReady] = useState(false);
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [view, setView] = useState<View>("orders");
  const [showForm, setShowForm] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [settingsTab, setSettingsTab] = useState<SettingsTab>("customers");
  const [form, setForm] = useState<FormState>(emptyForm);
  const [detail, setDetail] = useState<DetailState | null>(null);
  const [detailTab, setDetailTab] = useState<DetailTab>("general");
  const [history, setHistory] = useState<StatusHistory[]>([]);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const [saved, setSaved] = useState(false);

  const query = useMemo(() => {
    const params = new URLSearchParams({
      page: String(page), page_size: "25", month: String(monthFilter), year: String(yearFilter),
    });
    if (company !== "all") params.set("company_code", company);
    const effectiveStatus =
      view === "no_repair" ? "no_repair" :
      view === "invoiced" ? "invoiced" :
      view === "warranty" ? "warranty" :
      statusFilter;
    if (effectiveStatus !== "all") params.set("status", effectiveStatus);
    if (search.trim()) params.set("search", search.trim());
    return params.toString();
  }, [company, monthFilter, page, search, statusFilter, view, yearFilter]);

  async function loadPeriods() {
    setError("");
    try {
      const companyQuery = company === "all" ? "" : `?company_code=${company}`;
      const periods = await apiClient.get<LaboratoryPeriods>(`/laboratory/periods${companyQuery}`);
      setMonthFilter(periods.latest_month);
      setYearFilter(periods.latest_year);
      setAvailableYears(periods.years.length ? periods.years : [periods.latest_year]);
      setPage(1);
      setPeriodReady(true);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Falha ao carregar períodos do Laboratório.");
      setPeriodReady(true);
    }
  }

  async function load() {
    if (!periodReady) return;
    setLoading(true); setError("");
    try {
      const companyQuery = company === "all" ? "" : `?company_code=${company}`;
      const summaryParams = new URLSearchParams({ month: String(monthFilter), year: String(yearFilter) });
      if (company !== "all") summaryParams.set("company_code", company);
      const [summaryData, orders, customerData, technicianData] = await Promise.all([
        apiClient.get<WorkOrderSummary>(`/laboratory/summary?${summaryParams.toString()}`),
        apiClient.get<WorkOrderPage>(`/laboratory/work-orders?${query}`),
        apiClient.get<Customer[]>(`/laboratory/customers${companyQuery}`),
        apiClient.get<Technician[]>(`/laboratory/technicians${companyQuery}`),
      ]);
      setSummary(summaryData); setPageData(orders); setCustomers(customerData); setTechnicians(technicianData);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Falha ao carregar o Laboratório."); }
    finally { setLoading(false); }
  }

  useEffect(() => {
    setPeriodReady(false);
    void loadPeriods();
  }, [company]);
  useEffect(() => { if (periodReady) void load(); }, [query, periodReady]);
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("acao") === "nova-os") setShowForm(true);
    const workOrderId = Number(params.get("os"));
    if (Number.isInteger(workOrderId) && workOrderId > 0) void openOrder(workOrderId);
  }, []);

  function filterByPriorityStatus(status: WorkOrderStatus) {
    setView("orders"); setStatusFilter(status); setPage(1);
  }

  async function openOrder(orderId: number) {
    setLoading(true); setError("");
    try {
      const order = await apiClient.get<WorkOrder>(`/laboratory/work-orders/${orderId}`);
      setDetail(toDetail(order)); setDetailTab("general");
      const rows = await apiClient.get<StatusHistory[]>(`/laboratory/work-orders/${orderId}/history`);
      setHistory(rows);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Falha ao abrir a O.S."); }
    finally { setLoading(false); }
  }

  async function createWorkOrder(event: React.FormEvent, entryFiles: File[]) {
    event.preventDefault(); setLoading(true); setError(""); setMessage("");
    try {
      const created = await apiClient.post<WorkOrder>("/laboratory/work-orders", payloadFromForm(form));
      let uploaded = 0;
      let failedUploads = 0;
      for (const file of entryFiles) {
        const body = new FormData();
        body.append("file", file);
        try {
          await apiClient.post(`/laboratory/work-orders/${created.id}/documents?category=entry`, body);
          uploaded += 1;
        } catch {
          failedUploads += 1;
        }
      }
      setMessage(uploaded
        ? `O.S. ${created.number} criada com sucesso. ${uploaded} foto(s)/arquivo(s) anexado(s).`
        : `O.S. ${created.number} criada com sucesso.`);
      if (failedUploads) setError(`A O.S. ${created.number} foi criada, mas ${failedUploads} anexo(s) não puderam ser enviados. Abra a aba Fotos da O.S. para tentar novamente.`);
      setForm(emptyForm()); setShowForm(false); setPage(1); await load();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Falha ao criar a O.S."); }
    finally { setLoading(false); }
  }

  async function saveDetail() {
    if (!detail) return;
    setLoading(true); setSaved(false); setError("");
    try {
      const updated = await apiClient.patch<WorkOrder>(`/laboratory/work-orders/${detail.id}`, {
        ...payloadFromForm(detail), version: detail.version,
      });
      setDetail(toDetail(updated)); setSaved(true); setMessage(`O.S. ${updated.number} atualizada.`); await load();
      window.setTimeout(() => setSaved(false), 1800);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Falha ao salvar a O.S."); }
    finally { setLoading(false); }
  }

  async function changeStatus(targetStatus: WorkOrderStatus) {
    if (!detail || targetStatus === detail.status) return;
    setLoading(true); setError(""); setMessage("");
    try {
      const currentStatus = detail.status;
      const updated = await apiClient.post<WorkOrder>(`/laboratory/work-orders/${detail.id}/status`, {
        status: targetStatus, version: detail.version, note: `Status alterado de ${statusLabels[currentStatus]} para ${statusLabels[targetStatus]} pela tela de detalhes.`,
      });
      setDetail(toDetail(updated));
      setHistory(await apiClient.get<StatusHistory[]>(`/laboratory/work-orders/${detail.id}/history`));
      setMessage(`Status da ${updated.number} alterado para ${statusLabels[updated.status]}.`);
      await load();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Não foi possível alterar o status."); }
    finally { setLoading(false); }
  }

  const filteredItems = pageData.items;

  return (
    <main className="lab-layout">
      <aside className="lab-sidebar">
        <div className="lab-brand"><FlaskConical size={22} /><strong>Laboratório</strong></div>
        <SidebarButton active={view === "orders"} icon={<Wrench size={17} />} onClick={() => setView("orders")}>Ordens de serviço</SidebarButton>
        <SidebarButton active={view === "invoiced"} icon={<BadgeDollarSign size={17} />} onClick={() => setView("invoiced")}>Faturados</SidebarButton>
        <SidebarButton active={view === "no_repair"} icon={<CheckCircle2 size={17} />} onClick={() => setView("no_repair")}>Sem conserto</SidebarButton>
        <SidebarButton active={view === "warranty"} icon={<ShieldCheck size={17} />} onClick={() => setView("warranty")}>Garantias</SidebarButton>
        <div className="lab-sidebar-spacer" />
        <SidebarButton icon={<Settings size={17} />} onClick={() => setShowSettings(true)}>Configurações</SidebarButton>
        <SidebarButton icon={<ArrowLeft size={17} />} onClick={() => navigate("/painel")}>Voltar ao painel</SidebarButton>
      </aside>

      <section className="lab-shell">
        <header className="lab-header">
          <div><p className="lab-eyebrow">NEXUS ENTERPRISE</p><h1>Operação técnica e rastreabilidade</h1><span>Controle completo de entrada, execução, orçamento e saída.</span></div>
          <div className="lab-user"><span>{user.name}</span><ActionButton variant="secondary" icon={<LogOut size={17} />} onClick={onLogout}>Sair</ActionButton></div>
        </header>
        {error && <div className="lab-alert error">{error}</div>}{message && <div className="lab-alert success">{message}</div>}

        <section className="lab-priority-kpis" aria-label="Prioridades comerciais do laboratório">
          <button className={statusFilter === "in_analysis" ? "active" : ""} onClick={() => filterByPriorityStatus("in_analysis")}>
            <span>ANALISADOS</span><strong>{summary?.analyzed ?? 0}</strong><small>Falta orçamento</small>
          </button>
          <button className={statusFilter === "awaiting_approval" ? "active" : ""} onClick={() => filterByPriorityStatus("awaiting_approval")}>
            <span>AG. APROVAÇÃO</span><strong>{summary?.awaiting_approval ?? 0}</strong><small>Orçamento enviado</small>
          </button>
          <button className={statusFilter === "approved" ? "active" : ""} onClick={() => filterByPriorityStatus("approved")}>
            <span>APROVADOS</span><strong>{summary?.approved ?? 0}</strong><small>Liberados p/ reparo</small>
          </button>
        </section>
        <section className="lab-secondary-kpis">
          <article><span>O.S. abertas</span><strong>{summary?.total_open ?? 0}</strong></article>
          <article><span>Aguardando análise</span><strong>{summary?.awaiting_analysis ?? 0}</strong></article>
          <article><span>Em reparo</span><strong>{summary?.in_repair ?? 0}</strong></article>
          <article><span>Em testes</span><strong>{summary?.in_testing ?? 0}</strong></article>
          <article className="danger"><span>Alta/Urgente</span><strong>{summary?.high_priority ?? 0}</strong></article>
        </section>

        <section className="lab-toolbar">
          <div className="lab-search"><Search size={18} /><input value={search} onChange={(e) => { setSearch(e.target.value); setPage(1); }} placeholder="Buscar O.S., cliente, equipamento, NF entrada ou saída" /></div>
          <select aria-label="Mês de entrada" value={monthFilter} onChange={(e) => { setMonthFilter(Number(e.target.value)); setPage(1); }}>
            {monthLabels.map((label, index) => <option key={label} value={index + 1}>{label}</option>)}
          </select>
          <select aria-label="Ano de entrada" value={yearFilter} onChange={(e) => { setYearFilter(Number(e.target.value)); setPage(1); }}>
            {availableYears.map((year) => <option key={year} value={year}>{year}</option>)}
          </select>
          <select value={company} onChange={(e) => { setCompany(e.target.value as CompanyCode | "all"); setPage(1); }}><option value="all">Todas as empresas</option>{Object.entries(companyLabels).map(([value,label]) => <option key={value} value={value}>{label}</option>)}</select>
          <select value={statusFilter} onChange={(e) => { setStatusFilter(e.target.value as WorkOrderStatus | "all"); setPage(1); }}>
            <option value="all">Todos os status</option>
            <optgroup label="Status principais">{businessStatusOptions.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</optgroup>
            <optgroup label="Etapas operacionais">{operationalStatusOptions.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</optgroup>
          </select>
          <ActionButton variant="secondary" icon={<RefreshCw size={17} />} loading={loading} onClick={() => void load()}>Atualizar</ActionButton>
          <ActionButton icon={<Plus size={18} />} onClick={() => setShowForm(true)}>Nova O.S.</ActionButton>
        </section>

        <section className="lab-table-card">
          <table><thead><tr><th>O.S.</th><th>Cliente</th><th>Equipamento/série</th><th>NF entrada</th><th>NF saída</th><th>Status</th><th>Prioridade</th><th>Entrada</th></tr></thead>
            <tbody>{filteredItems.map((order) => <tr key={order.id} className={`lab-order-row priority-${order.priority}`} onClick={() => void openOrder(order.id)} tabIndex={0} onKeyDown={(event) => { if (event.key === "Enter") void openOrder(order.id); }}>
              <td><button className="lab-order-link">{order.number}</button></td><td>{order.customer_name}</td><td>{order.equipment_type || order.model || order.equipment_serial || "Sem identificação"}</td><td>{order.entry_invoice || "—"}</td><td>{order.exit_invoice || "—"}</td><td><span className={`lab-status ${order.status}`}>{statusLabels[order.status]}</span></td><td><span className={`lab-priority ${order.priority}`}>{priorityLabels[order.priority]}</span></td><td>{new Date(`${order.opened_at}T12:00:00`).toLocaleDateString("pt-BR")}</td>
            </tr>)}</tbody></table>
          {!filteredItems.length && <div className="lab-empty">Nenhuma ordem encontrada.</div>}
          <footer className="lab-pagination"><strong>{pageData.total} registro(s)</strong><div><button disabled={page <= 1} onClick={() => setPage(page - 1)}>Anterior</button><span>Página {page} de {pageData.pages || 1}</span><button disabled={page >= pageData.pages} onClick={() => setPage(page + 1)}>Próxima</button></div></footer>
        </section>
      </section>

      {showForm && <OrderForm form={form} setForm={setForm} customers={customers} technicians={technicians} loading={loading} onSubmit={createWorkOrder} onClose={() => setShowForm(false)} />}
      {detail && <OrderDetail detail={detail} setDetail={setDetail} tab={detailTab} setTab={setDetailTab} customers={customers} technicians={technicians} history={history} loading={loading} saved={saved} canManageQuote={!(["lab", "tecnico"].includes(user.role))} onSave={() => void saveDetail()} onStatus={(status) => void changeStatus(status)} onClose={() => setDetail(null)} />}
      {showSettings && <SettingsModal company={company === "all" ? "universo_eletronica" : company} customers={customers} technicians={technicians} tab={settingsTab} setTab={setSettingsTab} onClose={() => setShowSettings(false)} onSaved={load} />}
    </main>
  );
}

function payloadFromForm(form: FormState) {
  return {
    ...form, customer_id: form.customer_id ? Number(form.customer_id) : null,
    assigned_technician_id: form.assigned_technician_id ? Number(form.assigned_technician_id) : null,
    serial_number: form.serial_number || null, manufacturer: form.manufacturer || null,
    model: form.model || null, equipment_type: form.equipment_type || null, power: form.power || null,
    voltage: form.voltage || null, entry_invoice: form.entry_invoice || null, exit_invoice: form.exit_invoice || null,
    entry_condition: form.entry_condition || null, accessories_received: form.accessories_received || null,
    parts_cost: form.parts_cost || null, quoted_value: form.quoted_value || null,
    approved_value: form.approved_value || null, internal_notes: form.internal_notes || null,
    customer_notes: form.customer_notes || null,
  };
}

function SidebarButton({ active, icon, children, onClick }: { active?: boolean; icon: React.ReactNode; children: React.ReactNode; onClick: () => void }) {
  return <button className={`lab-sidebar-button ${active ? "active" : ""}`} onClick={onClick}><span>{icon}</span><strong>{children}</strong></button>;
}

function OrderForm({ form, setForm, customers, technicians, loading, onSubmit, onClose }: { form: FormState; setForm: (value: FormState) => void; customers: Customer[]; technicians: Technician[]; loading: boolean; onSubmit: (event: React.FormEvent, files: File[]) => void; onClose: () => void }) {
  const [entryFiles, setEntryFiles] = useState<File[]>([]);
  return <div className="lab-modal"><form className="lab-form lab-form-wide" onSubmit={(event) => onSubmit(event, entryFiles)}>
    <header><div><p>ABERTURA CONTROLADA</p><h2><Plus size={24} /> Nova Ordem de Serviço</h2><small>O número será gerado automaticamente no formato OS-0001.</small></div><button type="button" onClick={onClose}><X /></button></header>
    <SectionTitle title="Identificação" />
    <div className="lab-grid three"><SelectCompany value={form.company_code} onChange={(value) => setForm({ ...form, company_code: value })} /><label>Cliente *<select required value={form.customer_id} onChange={(e) => { const customer = customers.find((item) => item.id === Number(e.target.value)); setForm({ ...form, customer_id: e.target.value, customer_name: customer?.legal_name ?? "" }); }}><option value="">Selecione...</option>{customers.map((item) => <option key={item.id} value={item.id}>{item.legal_name}</option>)}</select></label><label>Técnico responsável<select value={form.assigned_technician_id} onChange={(e) => setForm({ ...form, assigned_technician_id: e.target.value })}><option value="">Não atribuído</option>{technicians.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label></div>
    <SectionTitle title="Equipamento" />
    <div className="lab-grid three"><Input label="Equipamento *" value={form.equipment_type} onChange={(value) => setForm({ ...form, equipment_type: value })} required /><Input label="Fabricante" value={form.manufacturer} onChange={(value) => setForm({ ...form, manufacturer: value })} /><Input label="Modelo" value={form.model} onChange={(value) => setForm({ ...form, model: value })} /><Input label="Número de série" value={form.serial_number} onChange={(value) => setForm({ ...form, serial_number: value })} /><Input label="Potência" value={form.power} onChange={(value) => setForm({ ...form, power: value })} /><Input label="Tensão" value={form.voltage} onChange={(value) => setForm({ ...form, voltage: value })} /></div>
    <SectionTitle title="Entrada e operação" />
    <div className="lab-grid three"><Input label="NF de entrada" value={form.entry_invoice} onChange={(value) => setForm({ ...form, entry_invoice: value })} /><Input label="NF de saída" value={form.exit_invoice} onChange={(value) => setForm({ ...form, exit_invoice: value })} /><label>Prioridade<select value={form.priority} onChange={(e) => setForm({ ...form, priority: e.target.value as Priority })}>{Object.entries(priorityLabels).map(([value,label]) => <option key={value} value={value}>{label}</option>)}</select></label></div>
    <label>Defeito informado *<textarea required rows={3} value={form.reported_defect} onChange={(e) => setForm({ ...form, reported_defect: e.target.value })} /></label>
    <div className="lab-grid"><label>Condição de entrada<textarea rows={3} value={form.entry_condition} onChange={(e) => setForm({ ...form, entry_condition: e.target.value })} /></label><label>Acessórios recebidos<textarea rows={3} value={form.accessories_received} onChange={(e) => setForm({ ...form, accessories_received: e.target.value })} /></label></div>
    <label className="lab-entry-upload">
      <UploadCloud size={24} />
      <div><strong>Fotos e PDFs de entrada</strong><span>JPG, PNG, WEBP ou PDF · até 15 MB por arquivo</span></div>
      <input type="file" accept="image/jpeg,image/png,image/webp,application/pdf" multiple onChange={(event) => setEntryFiles(Array.from(event.target.files ?? []))} />
    </label>
    {entryFiles.length > 0 && <div className="lab-entry-files">{entryFiles.map((file) => <span key={`${file.name}-${file.size}`}>{file.name}</span>)}</div>}
    <footer><ActionButton type="button" variant="secondary" icon={<X size={17} />} onClick={onClose}>Cancelar</ActionButton><ActionButton type="submit" loading={loading} icon={<Save size={17} />}>Cadastrar e gerar O.S.</ActionButton></footer>
  </form></div>;
}

function OrderDetail({ detail, setDetail, tab, setTab, customers, technicians, history, loading, saved, canManageQuote, onSave, onStatus, onClose }: { detail: DetailState; setDetail: (value: DetailState) => void; tab: DetailTab; setTab: (value: DetailTab) => void; customers: Customer[]; technicians: Technician[]; history: StatusHistory[]; loading: boolean; saved: boolean; canManageQuote: boolean; onSave: () => void; onStatus: (status: WorkOrderStatus) => void; onClose: () => void }) {
  const [targetStatus, setTargetStatus] = useState<WorkOrderStatus | "">("");
  const validOperationalStatuses = new Set(operationalTransitions[detail.status] ?? []);
  const visibleOperationalStatuses = operationalStatusOptions.filter((item) => validOperationalStatuses.has(item.value));

  useEffect(() => {
    setTargetStatus("");
  }, [detail.id, detail.status]);

  return <div className="lab-modal lab-modal-top"><section className="lab-detail">
    <header className="lab-detail-header"><div><p className="lab-eyebrow">DETALHE DA O.S.</p><h2>{detail.number}</h2><span>{detail.customer_name} · {detail.equipment_type || detail.model || "Equipamento"}</span><div className="lab-detail-badges"><span className={`lab-status ${detail.status}`}>{statusLabels[detail.status]}</span><span className={`lab-priority ${detail.priority}`}>{priorityLabels[detail.priority]}</span></div></div><div className="lab-detail-header-actions"><ActionButton variant="secondary" icon={<Printer size={17}/>} onClick={() => window.open(`/api/laboratory/work-orders/${detail.id}/label.pdf`, "_blank", "noopener,noreferrer")}>Emitir etiqueta</ActionButton><button className="lab-close-button" onClick={onClose}><X /></button></div></header>
    <nav className="lab-detail-tabs">
      <TabButton active={tab === "general"} icon={<Pencil size={16} />} onClick={() => setTab("general")}>Edição completa</TabButton>
      <TabButton active={tab === "technical"} icon={<Wrench size={16} />} onClick={() => setTab("technical")}>Dados técnicos</TabButton>
      <TabButton active={tab === "financial"} icon={<BadgeDollarSign size={16} />} onClick={() => setTab("financial")}>Valores</TabButton>
      <TabButton active={tab === "materials"} icon={<Wrench size={16} />} onClick={() => setTab("materials")}>Materiais</TabButton>
      <TabButton active={tab === "status"} icon={<ClipboardList size={16} />} onClick={() => setTab("status")}>Status</TabButton>
      <TabButton active={tab === "documents"} icon={<Image size={16} />} onClick={() => setTab("documents")}>Fotos</TabButton>
      <TabButton active={tab === "quote"} icon={<FileText size={16} />} onClick={() => setTab("quote")}>Orçamento</TabButton>
      <TabButton active={tab === "history"} icon={<History size={16} />} onClick={() => setTab("history")}>Histórico</TabButton>
    </nav>
    <div className="lab-detail-content">
      {tab === "general" && <><SectionTitle title="Cliente e documentos" /><div className="lab-grid"><label>Cliente<select value={detail.customer_id} onChange={(e) => { const customer = customers.find((item) => item.id === Number(e.target.value)); setDetail({ ...detail, customer_id: e.target.value, customer_name: customer?.legal_name ?? detail.customer_name }); }}>{customers.map((item) => <option key={item.id} value={item.id}>{item.legal_name}</option>)}</select></label><SelectCompany value={detail.company_code} onChange={(value) => setDetail({ ...detail, company_code: value })} /></div><div className="lab-grid"><Input label="NF de entrada" value={detail.entry_invoice} onChange={(value) => setDetail({ ...detail, entry_invoice: value })} /><Input label="NF de saída" value={detail.exit_invoice} onChange={(value) => setDetail({ ...detail, exit_invoice: value })} /></div><label>Defeito informado<textarea rows={4} value={detail.reported_defect} onChange={(e) => setDetail({ ...detail, reported_defect: e.target.value })} /></label><div className="lab-grid"><label>Condição de entrada<textarea rows={4} value={detail.entry_condition} onChange={(e) => setDetail({ ...detail, entry_condition: e.target.value })} /></label><label>Acessórios recebidos<textarea rows={4} value={detail.accessories_received} onChange={(e) => setDetail({ ...detail, accessories_received: e.target.value })} /></label></div></>}
      {tab === "technical" && <><SectionTitle title="Informações do equipamento" /><div className="lab-grid three"><Input label="Equipamento" value={detail.equipment_type} onChange={(value) => setDetail({ ...detail, equipment_type: value })} /><Input label="Fabricante" value={detail.manufacturer} onChange={(value) => setDetail({ ...detail, manufacturer: value })} /><Input label="Modelo" value={detail.model} onChange={(value) => setDetail({ ...detail, model: value })} /><Input label="Número de série" value={detail.serial_number} onChange={(value) => setDetail({ ...detail, serial_number: value })} /><Input label="Potência" value={detail.power} onChange={(value) => setDetail({ ...detail, power: value })} /><Input label="Tensão" value={detail.voltage} onChange={(value) => setDetail({ ...detail, voltage: value })} /></div><label>Observações internas<textarea rows={6} value={detail.internal_notes} onChange={(e) => setDetail({ ...detail, internal_notes: e.target.value })} /></label></>}
      {tab === "financial" && <><SectionTitle title="Custos e valores" /><div className="lab-grid three"><Input label="Valor de peças (R$)" value={detail.parts_cost} onChange={(value) => setDetail({ ...detail, parts_cost: value })} /><Input label="Valor orçado (R$)" value={detail.quoted_value} onChange={(value) => setDetail({ ...detail, quoted_value: value })} /><Input label="Valor aprovado (R$)" value={detail.approved_value} onChange={(value) => setDetail({ ...detail, approved_value: value })} /></div><div className="lab-financial-summary"><span>Custo de peças<strong>{currency(detail.parts_cost)}</strong></span><span>Orçamento<strong>{currency(detail.quoted_value)}</strong></span><span>Valor aprovado<strong>{currency(detail.approved_value)}</strong></span></div></>}
      {tab === "materials" && <MaterialsPanel workOrderId={detail.id} />}
      {tab === "status" && <><SectionTitle title="Execução e responsabilidade" /><div className="lab-grid"><label>Técnico responsável<select value={detail.assigned_technician_id} onChange={(e) => setDetail({ ...detail, assigned_technician_id: e.target.value })}><option value="">Não atribuído</option>{technicians.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label>Prioridade<select value={detail.priority} onChange={(e) => setDetail({ ...detail, priority: e.target.value as Priority })}>{Object.entries(priorityLabels).map(([value,label]) => <option key={value} value={value}>{label}</option>)}</select></label></div><div className="lab-status-panel lab-status-workflow"><div className="lab-status-current"><span>Status atual</span><strong>{statusLabels[detail.status]}</strong></div><label>Novo status<select value={targetStatus} disabled={loading} onChange={(e) => setTargetStatus(e.target.value as WorkOrderStatus | "")}><option value="">Selecione o status...</option><optgroup label="Status principais">{businessStatusOptions.filter((item) => item.value !== detail.status).map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</optgroup>{visibleOperationalStatuses.length > 0 && <optgroup label="Próximas etapas operacionais">{visibleOperationalStatuses.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</optgroup>}</select><small>Status principais restaurados conforme o fluxo histórico. Compras e materiais continuam sincronizados pelas etapas operacionais.</small></label><ActionButton loading={loading} disabled={!targetStatus} icon={<RefreshCw size={17} />} onClick={() => { if (targetStatus) onStatus(targetStatus); }}>Aplicar status</ActionButton></div></>}
      {tab === "documents" && <EquipmentDocumentsPanel workOrderId={detail.id} />}
      {tab === "quote" && <QuoteEditor
        workOrderId={detail.id} workOrderNumber={detail.number} customerName={detail.customer_name}
        equipmentType={detail.equipment_type} manufacturer={detail.manufacturer} model={detail.model}
        serialNumber={detail.serial_number} power={detail.power} voltage={detail.voltage}
        defect={detail.reported_defect} quotedValue={detail.quoted_value} readOnly={!canManageQuote}
      />}
      {tab === "history" && <div className="lab-timeline">{history.map((item) => <article key={item.id}><span className="lab-timeline-dot" /><div><strong>{statusLabels[item.new_status as WorkOrderStatus] ?? item.new_status}</strong><p>{item.note || "Alteração de status."}</p><small>{item.user_name} · {new Date(item.created_at).toLocaleString("pt-BR")}</small></div></article>)}{!history.length && <div className="lab-empty">Nenhum evento registrado.</div>}</div>}
    </div>
    <footer className="lab-detail-footer"><ActionButton variant="secondary" icon={<X size={17} />} onClick={onClose}>Fechar</ActionButton><ActionButton loading={loading} success={saved} icon={<Save size={17} />} onClick={onSave}>{saved ? "Salvo" : "Salvar alterações"}</ActionButton></footer>
  </section></div>;
}

function SettingsModal({ company, customers, technicians, tab, setTab, onClose, onSaved }: { company: CompanyCode; customers: Customer[]; technicians: Technician[]; tab: SettingsTab; setTab: (value: SettingsTab) => void; onClose: () => void; onSaved: () => Promise<void> }) {
  const [customerName, setCustomerName] = useState(""); const [customerDocument, setCustomerDocument] = useState("");
  const [technicianName, setTechnicianName] = useState(""); const [specialty, setSpecialty] = useState("");
  const [busyId, setBusyId] = useState<number | null>(null); const [saving, setSaving] = useState(false);
  async function create() { setSaving(true); try { if (tab === "customers") { await apiClient.post("/laboratory/customers", { company_code: company, legal_name: customerName, document: customerDocument || null }); setCustomerName(""); setCustomerDocument(""); } else { await apiClient.post("/laboratory/technicians", { company_code: company, name: technicianName, specialty: specialty || null }); setTechnicianName(""); setSpecialty(""); } await onSaved(); } finally { setSaving(false); } }
  async function deactivate(kind: SettingsTab, id: number) { setBusyId(id); try { await apiClient.delete(`/laboratory/${kind}/${id}`); await onSaved(); } finally { setBusyId(null); } }
  return <div className="lab-modal"><section className="lab-settings professional"><header><div><p>CONFIGURAÇÕES</p><h2>Central de cadastros</h2><span>Administre clientes e técnicos sem perder o histórico operacional.</span></div><button onClick={onClose}><X /></button></header><div className="lab-settings-layout"><nav><TabButton active={tab === "customers"} icon={<Users size={17} />} onClick={() => setTab("customers")}>Clientes <small>{customers.length}</small></TabButton><TabButton active={tab === "technicians"} icon={<UserRoundCog size={17} />} onClick={() => setTab("technicians")}>Técnicos <small>{technicians.length}</small></TabButton></nav><div className="lab-settings-main"><div className="lab-settings-heading"><div><h3>{tab === "customers" ? "Cadastro de clientes" : "Cadastro de técnicos"}</h3><p>{tab === "customers" ? "Razão social, documento e vínculos com as ordens de serviço." : "Equipe técnica, especialidade e disponibilidade operacional."}</p></div><ActionButton loading={saving} icon={<Plus size={17} />} onClick={() => void create()}>Cadastrar</ActionButton></div>{tab === "customers" ? <div className="lab-settings-form"><Input label="Razão social / cliente" value={customerName} onChange={setCustomerName} /><Input label="CNPJ/CPF" value={customerDocument} onChange={setCustomerDocument} /></div> : <div className="lab-settings-form"><Input label="Nome do técnico" value={technicianName} onChange={setTechnicianName} /><Input label="Especialidade" value={specialty} onChange={setSpecialty} /></div>}<div className="lab-settings-list">{(tab === "customers" ? customers : technicians).map((item) => <article key={item.id}><div className="lab-avatar">{("legal_name" in item ? item.legal_name : item.name).slice(0,2).toUpperCase()}</div><div className="lab-settings-item-copy"><strong>{"legal_name" in item ? item.legal_name : item.name}</strong><span>{"document" in item ? item.document || "Sem documento" : item.specialty || "Sem especialidade"}</span></div><ActionButton variant="danger" loading={busyId === item.id} icon={<Trash2 size={16} />} onClick={() => void deactivate(tab, item.id)}>Inativar</ActionButton></article>)}</div></div></div></section></div>;
}

function TabButton({ active, icon, children, onClick }: { active: boolean; icon: React.ReactNode; children: React.ReactNode; onClick: () => void }) { return <button className={`lab-tab-button ${active ? "active" : ""}`} onClick={onClick}>{icon}<span>{children}</span></button>; }
function SectionTitle({ title }: { title: string }) { return <div className="lab-section-title"><span>{title}</span></div>; }
function Input({ label, value, onChange, required = false }: { label: string; value: string; onChange: (value: string) => void; required?: boolean }) { return <label>{label}<input required={required} value={value} onChange={(e) => onChange(e.target.value)} /></label>; }
function SelectCompany({ value, onChange }: { value: CompanyCode; onChange: (value: CompanyCode) => void }) { return <label>Empresa emissora<select value={value} onChange={(e) => onChange(e.target.value as CompanyCode)}>{Object.entries(companyLabels).map(([key,label]) => <option key={key} value={key}>{label}</option>)}</select></label>; }
function currency(value: string) { const number = Number(String(value || "0").replace(",", ".")); return Number.isFinite(number) ? number.toLocaleString("pt-BR", { style: "currency", currency: "BRL" }) : "R$ 0,00"; }
