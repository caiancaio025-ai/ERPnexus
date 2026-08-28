import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  ArrowLeft,
  BadgeDollarSign,
  Building2,
  ChevronLeft,
  ChevronRight,
  ClipboardList,
  FileText,
  History,
  LayoutDashboard,
  LogOut,
  Mail,
  MapPin,
  Menu,
  PackageSearch,
  Paperclip,
  Pencil,
  Plus,
  ReceiptText,
  Save,
  Search,
  Trash2,
  Upload,
  UserRound,
  Users,
  Wrench,
  X,
} from "lucide-react";
import { useNavigate } from "react-router-dom";

import type { AuthUser } from "../auth/AuthCard";
import { apiClient } from "../../shared/api/apiClient";
import type {
  CustomerContact,
  CustomerDetail,
  CustomerListItem,
  CustomerPage,
} from "./types";
import "./customers.css";

type CustomerMasterProps = { user: AuthUser; onLogout: () => void };
type CustomerTab = "overview" | "data" | "contacts" | "billing" | "documents" | "equipment" | "workorders" | "quotes" | "notes";
type CompanyCode = "universo_eletronica" | "universo_automacao" | "solucoes_eletronica";

type CustomerForm = {
  legal_name: string;
  trade_name: string;
  document: string;
  state_registration: string;
  municipal_registration: string;
  phone: string;
  whatsapp: string;
  email: string;
  website: string;
  postal_code: string;
  address: string;
  address_number: string;
  complement: string;
  district: string;
  city: string;
  state: string;
  notes: string;
};

const EMPTY_FORM: CustomerForm = {
  legal_name: "", trade_name: "", document: "", state_registration: "", municipal_registration: "",
  phone: "", whatsapp: "", email: "", website: "", postal_code: "", address: "", address_number: "",
  complement: "", district: "", city: "", state: "", notes: "",
};

const STATUS_LABELS: Record<string, string> = {
  received: "Recebido", in_analysis: "Em análise", awaiting_quote_approval: "Aguardando aprovação", approved: "Aprovado",
  in_repair: "Em reparo", awaiting_parts: "Aguardando peças", completed: "Concluído", invoiced: "Faturado",
  delivered: "Entregue", cancelled: "Cancelado", draft: "Rascunho", sent: "Enviado", rejected: "Rejeitado",
};

const COMPANY_LABELS: Record<CompanyCode, string> = {
  universo_eletronica: "Universo Eletrônica",
  universo_automacao: "Universo Automação",
  solucoes_eletronica: "Soluções Eletrônica",
};

function emptyToNull(value: string) { return value.trim() || null; }
function money(value: number | null | undefined) { return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(Number(value || 0)); }
function dateBR(value: string | null | undefined) { return value ? new Date(`${value.slice(0, 10)}T12:00:00`).toLocaleDateString("pt-BR") : "—"; }
function initials(name: string) { return name.trim().split(/\s+/).slice(0, 2).map((x) => x[0]?.toUpperCase()).join("") || "CL"; }
function formFromCustomer(customer: CustomerDetail): CustomerForm {
  const result = { ...EMPTY_FORM };
  (Object.keys(result) as (keyof CustomerForm)[]).forEach((key) => { result[key] = String(customer[key] ?? ""); });
  return result;
}

const TABS: { key: CustomerTab; label: string; icon: typeof Building2 }[] = [
  { key: "overview", label: "Visão geral", icon: LayoutDashboard },
  { key: "data", label: "Dados", icon: Building2 },
  { key: "contacts", label: "Contatos", icon: Users },
  { key: "billing", label: "Faturamento", icon: ReceiptText },
  { key: "documents", label: "Documentos", icon: FileText },
  { key: "equipment", label: "Equipamentos", icon: Wrench },
  { key: "workorders", label: "OS", icon: ClipboardList },
  { key: "quotes", label: "Orçamentos", icon: BadgeDollarSign },
  { key: "notes", label: "Histórico", icon: History },
];

export function CustomerMaster({ user, onLogout }: CustomerMasterProps) {
  const navigate = useNavigate();
  const [customers, setCustomers] = useState<CustomerListItem[]>([]);
  const [customerPage, setCustomerPage] = useState({ page: 1, pages: 1, total: 0 });
  const [customer, setCustomer] = useState<CustomerDetail | null>(null);
  const [form, setForm] = useState<CustomerForm>(EMPTY_FORM);
  const [tab, setTab] = useState<CustomerTab>("overview");
  const [search, setSearch] = useState("");
  const [company, setCompany] = useState<CompanyCode>("universo_eletronica");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [creating, setCreating] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => localStorage.getItem("nexus:customers-sidebar") === "collapsed");
  const canAccess = useMemo(
    () => ["admin", "super_admin"].includes(user.role) || user.modules.some((m) => ["laboratorio", "comercial", "financeiro"].includes(m)),
    [user],
  );

  async function loadCustomers(term = search, requestedPage = 1) {
    setLoading(true); setError("");
    try {
      const params = new URLSearchParams({ company_code: company, page: String(requestedPage), page_size: "100" });
      if (term.trim()) params.set("search", term.trim());
      const data = await apiClient.get<CustomerPage>(`/customers/page?${params}`);
      setCustomers(data.items);
      setCustomerPage({ page: data.page, pages: data.pages, total: data.total });
      if (customer && !data.items.some((item) => item.id === customer.id)) { setCustomer(null); setCreating(false); }
    } catch (err) { setError(err instanceof Error ? err.message : "Falha ao carregar clientes."); }
    finally { setLoading(false); }
  }

  async function openCustomer(id: number, preserveTab = false) {
    setLoading(true); setError("");
    try {
      const data = await apiClient.get<CustomerDetail>(`/customers/${id}`);
      setCustomer(data); setForm(formFromCustomer(data)); setCreating(false);
      if (!preserveTab) setTab("overview");
    } catch (err) { setError(err instanceof Error ? err.message : "Falha ao abrir cliente."); }
    finally { setLoading(false); }
  }

  useEffect(() => { if (canAccess) void loadCustomers(""); }, [company, canAccess]); // eslint-disable-line react-hooks/exhaustive-deps

  function toggleSidebar() {
    setSidebarCollapsed((value) => {
      const next = !value;
      localStorage.setItem("nexus:customers-sidebar", next ? "collapsed" : "expanded");
      return next;
    });
  }

  function startNew() { setCustomer(null); setForm(EMPTY_FORM); setCreating(true); setTab("data"); }

  async function saveCustomer(event: FormEvent) {
    event.preventDefault();
    setLoading(true); setError("");
    const payload = Object.fromEntries(Object.entries(form).map(([key, value]) => [key, key === "legal_name" ? value.trim() : emptyToNull(value)]));
    try {
      if (creating) {
        const created = await apiClient.post<CustomerListItem>("/customers", { ...payload, company_code: company });
        await loadCustomers(); await openCustomer(created.id);
      } else if (customer) {
        const updated = await apiClient.put<CustomerDetail>(`/customers/${customer.id}`, payload);
        setCustomer(updated); setForm(formFromCustomer(updated)); await loadCustomers();
      }
    } catch (err) { setError(err instanceof Error ? err.message : "Falha ao salvar cliente."); }
    finally { setLoading(false); }
  }

  if (!canAccess) return <main className="customers-denied">Você não possui acesso ao Cadastro Mestre de Clientes.</main>;

  return (
    <div className={`customers-shell ${sidebarCollapsed ? "sidebar-collapsed" : ""}`}>
      <aside className="customers-sidebar">
        <div className="customers-sidebar-top">
          <div className="customers-brand">
            <span className="customers-brand-mark">NX</span>
            <div className="customers-brand-copy"><strong>NEXUS</strong><span>CLIENTES 360°</span></div>
          </div>
          <button className="sidebar-toggle" onClick={toggleSidebar} title={sidebarCollapsed ? "Expandir menu" : "Recolher menu"} aria-label={sidebarCollapsed ? "Expandir menu" : "Recolher menu"}>
            {sidebarCollapsed ? <ChevronRight size={18} /> : <ChevronLeft size={18} />}
          </button>
        </div>
        <nav className="customers-side-nav">
          <button onClick={() => navigate("/painel")} title="Voltar ao painel"><ArrowLeft size={18} /><span>Voltar ao painel</span></button>
        </nav>
        <div className="customers-sidebar-footer">
          <div className="customers-user"><span className="customers-user-avatar">{initials(user.name)}</span><div><strong>{user.name}</strong><small>{user.role}</small></div></div>
          <button className="logout" onClick={onLogout} title="Sair do sistema"><LogOut size={18} /><span>Sair do sistema</span></button>
        </div>
      </aside>

      <main className="customers-main">
        <header className="customers-header">
          <div className="customers-title-wrap">
            <button className="mobile-menu-button" onClick={toggleSidebar} aria-label="Alternar menu"><Menu size={19} /></button>
            <div><span>CADASTRO CORPORATIVO</span><h1>Clientes</h1><p>Relacionamento, operação e histórico em uma única visão.</p></div>
          </div>
          <button className="customers-primary" onClick={startNew}><Plus size={17} />Novo cliente</button>
        </header>

        <section className="customers-toolbar">
          <label className="customers-search"><Search size={17} /><input value={search} onChange={(e) => setSearch(e.target.value)} onKeyDown={(e) => e.key === "Enter" && void loadCustomers(search, 1)} placeholder="Razão social, CNPJ ou e-mail..." /><kbd>Enter</kbd></label>
          <select value={company} onChange={(e) => setCompany(e.target.value as CompanyCode)} aria-label="Empresa">
            {Object.entries(COMPANY_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
          <button className="customers-secondary" onClick={() => void loadCustomers(search, 1)} disabled={loading}><Search size={16} /><span>Buscar</span></button>
        </section>

        {error && <p className="customers-error">{error}</p>}

        <div className="customers-layout">
          <section className="customers-list">
            <header><div><strong>{customerPage.total}</strong><span>{customerPage.total === 1 ? "cliente" : "clientes"}</span></div><small>{loading ? "Atualizando..." : `Página ${customerPage.page} de ${customerPage.pages}`}</small></header>
            <div className="customers-list-scroll">
              {customers.map((item) => (
                <button key={item.id} className={customer?.id === item.id ? "active" : ""} onClick={() => void openCustomer(item.id)}>
                  <span className="customer-avatar">{initials(item.trade_name || item.legal_name)}</span>
                  <span className="customer-list-copy"><strong>{item.trade_name || item.legal_name}</strong><small>{item.document || "Sem CNPJ/CPF"}</small><small><MapPin size={11} />{[item.city, item.state].filter(Boolean).join(" / ") || "Localidade não informada"}</small></span>
                  <ChevronRight className="customer-list-chevron" size={16} />
                </button>
              ))}
              {!customers.length && !loading && <div className="customers-list-empty"><PackageSearch size={26} /><span>Nenhum cliente encontrado</span></div>}
            </div>
            <footer className="customers-list-pagination">
              <button disabled={loading || customerPage.page <= 1} onClick={() => void loadCustomers(search, customerPage.page - 1)}><ChevronLeft size={15} />Anterior</button>
              <span>{customerPage.page} / {customerPage.pages}</span>
              <button disabled={loading || customerPage.page >= customerPage.pages} onClick={() => void loadCustomers(search, customerPage.page + 1)}>Próxima<ChevronRight size={15} /></button>
            </footer>
          </section>

          <section className="customer-detail">
            {!customer && !creating && <div className="customer-empty"><Building2 size={42} /><h2>Selecione um cliente</h2><p>Abra um cadastro existente ou crie um novo cliente.</p><button className="customers-primary" onClick={startNew}><Plus size={16} />Novo cliente</button></div>}
            {(customer || creating) && <>
              <header className="customer-detail-header">
                <div className="customer-identity"><span>{creating ? "NOVO CADASTRO" : customer?.document || "CLIENTE"}</span><h2>{form.trade_name || form.legal_name || "Novo cliente"}</h2>{customer && <p>{[customer.city, customer.state].filter(Boolean).join(" / ") || "Localidade não informada"}</p>}</div>
                {customer && <div className="customer-kpis"><span><b>{customer.equipment.length}</b><small>Equipamentos</small></span><span><b>{customer.work_orders_count}</b><small>OS</small></span><span><b>{customer.quotes_count}</b><small>Orçamentos</small></span></div>}
              </header>
              <nav className="customer-tabs">
                {TABS.map(({ key, label, icon: Icon }) => <button key={key} className={tab === key ? "active" : ""} disabled={creating && key !== "data"} onClick={() => setTab(key)}><Icon size={15} /><span>{label}</span></button>)}
              </nav>
              <div className="customer-content">
                {tab === "overview" && customer && <Overview customer={customer} />}
                {tab === "data" && <CustomerData form={form} setForm={setForm} onSubmit={saveCustomer} loading={loading} />}
                {tab === "contacts" && customer && <Contacts customer={customer} reload={() => openCustomer(customer.id, true)} />}
                {tab === "billing" && customer && <Billing customer={customer} reload={() => openCustomer(customer.id, true)} />}
                {tab === "documents" && customer && <Documents customer={customer} reload={() => openCustomer(customer.id, true)} />}
                {tab === "equipment" && customer && <Equipment customer={customer} />}
                {tab === "workorders" && customer && <WorkOrders customer={customer} />}
                {tab === "quotes" && customer && <Quotes customer={customer} />}
                {tab === "notes" && customer && <Notes customer={customer} reload={() => openCustomer(customer.id, true)} />}
              </div>
            </>}
          </section>
        </div>
      </main>
    </div>
  );
}

function Overview({ customer }: { customer: CustomerDetail }) {
  const primary = customer.contacts.find((c) => c.is_primary);
  const latestOrders = customer.work_orders.slice(0, 4);
  return <div className="customer-panel overview-panel">
    <div className="overview-metrics">
      <article><span>Contato principal</span><strong>{primary?.name || "Não definido"}</strong><small>{primary?.department || primary?.email || "Cadastre um responsável"}</small></article>
      <article><span>Prazo de faturamento</span><strong>{customer.billing?.payment_term_days == null ? "Não definido" : `${customer.billing.payment_term_days} dias`}</strong><small>{customer.billing?.billing_cutoff_day ? `Corte no dia ${customer.billing.billing_cutoff_day}` : "Dia de corte não configurado"}</small></article>
      <article><span>Operação técnica</span><strong>{customer.work_orders_count} OS</strong><small>{customer.equipment.length} equipamentos vinculados</small></article>
      <article><span>Orçamentos</span><strong>{customer.quotes_count}</strong><small>{money(customer.quotes.reduce((sum, item) => sum + Number(item.total || 0), 0))} em histórico</small></article>
    </div>
    <section className="overview-wide"><header><div><span>ATIVIDADE RECENTE</span><h3>Últimas ordens de serviço</h3></div><ClipboardList size={19} /></header>
      <div className="overview-table">
        {latestOrders.map((order) => <div key={order.id}><strong>{order.number}</strong><span className={`customers-status-pill customers-status-${order.status}`}>{STATUS_LABELS[order.status] || order.status}</span><span>{order.equipment_serial || "Sem série"}</span><span>{dateBR(order.opened_at)}</span></div>)}
        {!latestOrders.length && <p className="customers-muted">Nenhuma OS vinculada a este cliente.</p>}
      </div>
    </section>
  </div>;
}

function Field({ label, value, onChange, type = "text", placeholder }: { label: string; value: string; onChange: (value: string) => void; type?: string; placeholder?: string }) {
  return <label><span>{label}</span><input type={type} value={value} placeholder={placeholder} onChange={(e) => onChange(e.target.value)} /></label>;
}

function CustomerData({ form, setForm, onSubmit, loading }: { form: CustomerForm; setForm: (form: CustomerForm) => void; onSubmit: (event: FormEvent) => void; loading: boolean }) {
  const set = (key: keyof CustomerForm) => (value: string) => setForm({ ...form, [key]: value });
  return <form className="customer-form" onSubmit={onSubmit}>
    <SectionTitle icon={Building2} title="Identificação" subtitle="Dados jurídicos e comerciais do cadastro." />
    <div className="customer-grid three"><Field label="Razão social *" value={form.legal_name} onChange={set("legal_name")} /><Field label="Nome fantasia" value={form.trade_name} onChange={set("trade_name")} /><Field label="CNPJ/CPF" value={form.document} onChange={set("document")} /></div>
    <div className="customer-grid"><Field label="Inscrição estadual" value={form.state_registration} onChange={set("state_registration")} /><Field label="Inscrição municipal" value={form.municipal_registration} onChange={set("municipal_registration")} /></div>
    <SectionTitle icon={Mail} title="Contato corporativo" subtitle="Canais gerais da empresa." />
    <div className="customer-grid three"><Field label="Telefone" value={form.phone} onChange={set("phone")} /><Field label="WhatsApp" value={form.whatsapp} onChange={set("whatsapp")} /><Field label="E-mail" type="email" value={form.email} onChange={set("email")} /></div>
    <Field label="Website" value={form.website} onChange={set("website")} />
    <SectionTitle icon={MapPin} title="Endereço" subtitle="Localização para coleta, entrega e faturamento." />
    <div className="customer-grid three"><Field label="CEP" value={form.postal_code} onChange={set("postal_code")} /><Field label="Endereço" value={form.address} onChange={set("address")} /><Field label="Número" value={form.address_number} onChange={set("address_number")} /></div>
    <div className="customer-grid three"><Field label="Complemento" value={form.complement} onChange={set("complement")} /><Field label="Bairro" value={form.district} onChange={set("district")} /><Field label="Cidade" value={form.city} onChange={set("city")} /></div>
    <Field label="UF" value={form.state} onChange={set("state")} />
    <label><span>Observações gerais</span><textarea rows={4} value={form.notes} onChange={(e) => set("notes")(e.target.value)} /></label>
    <footer><button className="customers-primary" disabled={loading || !form.legal_name.trim()}><Save size={17} />{loading ? "Salvando..." : "Salvar cadastro"}</button></footer>
  </form>;
}

const EMPTY_CONTACT = { department: "", name: "", job_title: "", email: "", phone: "", whatsapp: "", is_primary: false, receives_quotes: false, receives_invoices: false, receives_reports: false, receives_service_updates: false, notes: "" };

function Contacts({ customer, reload }: { customer: CustomerDetail; reload: () => Promise<void> }) {
  const [form, setForm] = useState(EMPTY_CONTACT); const [editing, setEditing] = useState<number | null>(null);
  function edit(item: CustomerContact) { setEditing(item.id); setForm({ department: item.department || "", name: item.name, job_title: item.job_title || "", email: item.email || "", phone: item.phone || "", whatsapp: item.whatsapp || "", is_primary: item.is_primary, receives_quotes: item.receives_quotes, receives_invoices: item.receives_invoices, receives_reports: item.receives_reports, receives_service_updates: item.receives_service_updates, notes: item.notes || "" }); }
  async function save() {
    if (!form.name.trim()) return;
    const payload = { ...form, department: emptyToNull(form.department), job_title: emptyToNull(form.job_title), email: emptyToNull(form.email), phone: emptyToNull(form.phone), whatsapp: emptyToNull(form.whatsapp), notes: emptyToNull(form.notes), is_primary: form.is_primary || (!editing && customer.contacts.length === 0) };
    if (editing) await apiClient.put(`/customers/${customer.id}/contacts/${editing}`, payload); else await apiClient.post(`/customers/${customer.id}/contacts`, payload);
    setForm(EMPTY_CONTACT); setEditing(null); await reload();
  }
  async function remove(id: number) { if (!window.confirm("Desativar este contato?")) return; await apiClient.delete(`/customers/${customer.id}/contacts/${id}`); if (editing === id) { setEditing(null); setForm(EMPTY_CONTACT); } await reload(); }
  const patch = (key: keyof typeof EMPTY_CONTACT, value: string | boolean) => setForm({ ...form, [key]: value });
  return <div className="customer-panel">
    <SectionTitle icon={Users} title="Contatos do cliente" subtitle="Responsáveis e regras de comunicação por tipo de documento." />
    <div className="contact-editor">
      <div className="customer-grid three"><Field label="Pessoa responsável *" value={form.name} onChange={(v) => patch("name", v)} /><Field label="Setor" value={form.department} onChange={(v) => patch("department", v)} /><Field label="Cargo" value={form.job_title} onChange={(v) => patch("job_title", v)} /></div>
      <div className="customer-grid three"><Field label="E-mail" value={form.email} onChange={(v) => patch("email", v)} /><Field label="Telefone" value={form.phone} onChange={(v) => patch("phone", v)} /><Field label="WhatsApp" value={form.whatsapp} onChange={(v) => patch("whatsapp", v)} /></div>
      <div className="contact-flags">{[["is_primary","Contato principal"],["receives_quotes","Recebe orçamentos"],["receives_invoices","Recebe notas"],["receives_reports","Recebe laudos"],["receives_service_updates","Atualizações de OS"]].map(([key,label]) => <label key={key}><input type="checkbox" checked={Boolean(form[key as keyof typeof form])} onChange={(e) => patch(key as keyof typeof EMPTY_CONTACT, e.target.checked)} />{label}</label>)}</div>
      <label><span>Observações do contato</span><textarea rows={2} value={form.notes} onChange={(e) => patch("notes", e.target.value)} /></label>
      <div className="editor-actions"><button className="customers-primary" onClick={() => void save()} disabled={!form.name.trim()}>{editing ? <Save size={16}/> : <Plus size={16}/>} {editing ? "Salvar contato" : "Adicionar contato"}</button>{editing && <button onClick={() => { setEditing(null); setForm(EMPTY_CONTACT); }}><X size={15}/>Cancelar</button>}</div>
    </div>
    <div className="cards-list">{customer.contacts.map((item) => <article key={item.id}><span className="contact-icon"><UserRound size={18}/></span><div className="contact-card-body"><strong>{item.name}{item.is_primary ? " · Principal" : ""}</strong><span>{[item.department,item.job_title].filter(Boolean).join(" · ") || "Sem setor/cargo"}</span><small>{[item.email,item.phone,item.whatsapp].filter(Boolean).join(" · ") || "Sem contato informado"}</small><div className="contact-badges">{item.receives_quotes && <b>Orçamentos</b>}{item.receives_invoices && <b>Notas</b>}{item.receives_reports && <b>Laudos</b>}{item.receives_service_updates && <b>OS</b>}</div></div><div className="card-actions"><button onClick={() => edit(item)} title="Editar"><Pencil size={15}/></button><button onClick={() => void remove(item.id)} title="Desativar"><Trash2 size={15}/></button></div></article>)}</div>
  </div>;
}

function Billing({ customer, reload }: { customer: CustomerDetail; reload: () => Promise<void> }) {
  const billing = customer.billing;
  const [form, setForm] = useState({ billing_cutoff_day: billing?.billing_cutoff_day ?? "", payment_term_days: billing?.payment_term_days ?? "", invoice_email: billing?.invoice_email ?? "", xml_email: billing?.xml_email ?? "", portal_url: billing?.portal_url ?? "", billing_instructions: billing?.billing_instructions ?? "", financial_notes: billing?.financial_notes ?? "", requires_purchase_order: billing?.requires_purchase_order ?? false, requires_customer_order: billing?.requires_customer_order ?? false, requires_measurement: billing?.requires_measurement ?? false, requires_service_report: billing?.requires_service_report ?? false });
  async function save() { await apiClient.put(`/customers/${customer.id}/billing`, { ...form, billing_cutoff_day: form.billing_cutoff_day === "" ? null : Number(form.billing_cutoff_day), payment_term_days: form.payment_term_days === "" ? null : Number(form.payment_term_days) }); await reload(); }
  return <div className="customer-panel"><SectionTitle icon={ReceiptText} title="Política de faturamento" subtitle="Regras reutilizadas por Laboratório, Comercial e Financeiro." />
    <div className="customer-grid"><Field label="Dia limite para faturar" type="number" value={String(form.billing_cutoff_day)} onChange={(v) => setForm({...form,billing_cutoff_day:v})}/><Field label="Prazo padrão (dias)" type="number" value={String(form.payment_term_days)} onChange={(v) => setForm({...form,payment_term_days:v})}/></div>
    <div className="customer-grid"><Field label="E-mail para NF" value={form.invoice_email} onChange={(v) => setForm({...form,invoice_email:v})}/><Field label="E-mail para XML" value={form.xml_email} onChange={(v) => setForm({...form,xml_email:v})}/></div>
    <Field label="Portal do cliente" value={form.portal_url} onChange={(v) => setForm({...form,portal_url:v})}/>
    <div className="billing-checks">{[["requires_purchase_order","Exige pedido de compra"],["requires_customer_order","Exige OS/pedido do cliente"],["requires_measurement","Exige medição"],["requires_service_report","Exige relatório de serviço"]].map(([key,label]) => <label key={key}><input type="checkbox" checked={Boolean(form[key as keyof typeof form])} onChange={(e) => setForm({...form,[key]:e.target.checked})}/>{label}</label>)}</div>
    <label><span>Instruções de faturamento</span><textarea rows={3} value={form.billing_instructions} onChange={(e) => setForm({...form,billing_instructions:e.target.value})}/></label>
    <label><span>Observações financeiras</span><textarea rows={3} value={form.financial_notes} onChange={(e) => setForm({...form,financial_notes:e.target.value})}/></label>
    <div className="panel-actions"><button className="customers-primary" onClick={() => void save()}><Save size={16}/>Salvar faturamento</button></div>
  </div>;
}

function Documents({ customer, reload }: { customer: CustomerDetail; reload: () => Promise<void> }) {
  const [file, setFile] = useState<File | null>(null); const [category, setCategory] = useState("other"); const [reference, setReference] = useState(""); const [issue, setIssue] = useState(""); const [expiration, setExpiration] = useState(""); const [notes, setNotes] = useState("");
  async function upload() { if (!file) return; const body = new FormData(); body.append("file", file); body.append("category", category); if (reference.trim()) body.append("reference_number", reference.trim()); if (issue) body.append("issue_date", issue); if (expiration) body.append("expiration_date", expiration); if (notes.trim()) body.append("notes", notes.trim()); await apiClient.post(`/customers/${customer.id}/documents`, body); setFile(null); setReference(""); setIssue(""); setExpiration(""); setNotes(""); await reload(); }
  async function remove(id: number) { if (!window.confirm("Excluir este documento?")) return; await apiClient.delete(`/customers/${customer.id}/documents/${id}`); await reload(); }
  return <div className="customer-panel"><SectionTitle icon={Paperclip} title="Documentos" subtitle="Arquivos comerciais, fiscais e operacionais vinculados ao cliente." />
    <div className="document-upload expanded"><label><span>Categoria</span><select value={category} onChange={(e) => setCategory(e.target.value)}><option value="nfe">NF-e</option><option value="nfse">NFS-e</option><option value="nfd">NFD</option><option value="quote">Orçamento</option><option value="purchase_order">Pedido de compra</option><option value="contract">Contrato</option><option value="other">Outros</option></select></label><Field label="Número / referência" value={reference} onChange={setReference}/><Field label="Emissão" type="date" value={issue} onChange={setIssue}/><Field label="Validade" type="date" value={expiration} onChange={setExpiration}/><label className="document-file"><span>Arquivo</span><input type="file" accept=".pdf,.jpg,.jpeg,.png,.webp" onChange={(e) => setFile(e.target.files?.[0] ?? null)}/></label><Field label="Observação" value={notes} onChange={setNotes}/><button className="customers-primary" onClick={() => void upload()} disabled={!file}><Upload size={16}/>Anexar</button></div>
    <div className="documents-table"><header><span>Documento</span><span>Referência</span><span>Emissão</span><span>Validade</span><span/></header>{customer.documents.map((doc) => <div key={doc.id}><a href={`/api/customers/${customer.id}/documents/${doc.id}`} target="_blank" rel="noreferrer"><FileText size={15}/><span>{doc.original_name}</span></a><span>{doc.reference_number || "—"}</span><span>{dateBR(doc.issue_date)}</span><span>{dateBR(doc.expiration_date)}</span><button onClick={() => void remove(doc.id)} title="Excluir"><Trash2 size={14}/></button></div>)}</div>
  </div>;
}

function Equipment({ customer }: { customer: CustomerDetail }) { return <div className="customer-panel"><SectionTitle icon={Wrench} title="Equipamentos vinculados" subtitle="Ativos técnicos associados ao cadastro." /><div className="relation-table equipment"><header><span>Série</span><span>Equipamento</span><span>Fabricante</span><span>Potência / tensão</span></header>{customer.equipment.map((item) => <div key={item.id}><strong>{item.serial_number || "Sem série"}</strong><span>{[item.equipment_type,item.model].filter(Boolean).join(" · ") || "Não informado"}</span><span>{item.manufacturer || "—"}</span><span>{[item.power,item.voltage].filter(Boolean).join(" · ") || "—"}</span></div>)}</div>{!customer.equipment.length && <p className="customers-muted">Nenhum equipamento vinculado.</p>}</div>; }

function WorkOrders({ customer }: { customer: CustomerDetail }) { return <div className="customer-panel"><SectionTitle icon={ClipboardList} title="Ordens de serviço" subtitle="Histórico operacional do cliente." /><div className="relation-table workorders"><header><span>OS</span><span>Status</span><span>Série</span><span>Abertura</span><span>Valor</span></header>{customer.work_orders.map((item) => <div key={item.id}><strong>{item.number}</strong><span className={`customers-status-pill customers-status-${item.status}`}>{STATUS_LABELS[item.status] || item.status}</span><span>{item.equipment_serial || "Sem série"}</span><span>{dateBR(item.opened_at)}</span><span>{money(item.approved_value ?? item.quoted_value)}</span></div>)}</div></div>; }

function Quotes({ customer }: { customer: CustomerDetail }) { return <div className="customer-panel"><SectionTitle icon={BadgeDollarSign} title="Orçamentos" subtitle="Revisões e valores comerciais vinculados às OS." /><div className="relation-table quotes"><header><span>OS</span><span>Revisão</span><span>Status</span><span>Emissão</span><span>Total</span></header>{customer.quotes.map((item) => <div key={item.id}><strong>{item.work_order_number}</strong><span>Rev. {item.revision}</span><span className={`customers-status-pill customers-status-${item.status}`}>{STATUS_LABELS[item.status] || item.status}</span><span>{dateBR(item.emitted_at || item.created_at)}</span><span>{money(item.total)}</span></div>)}</div></div>; }

function Notes({ customer, reload }: { customer: CustomerDetail; reload: () => Promise<void> }) {
  const [category, setCategory] = useState("general"); const [text, setText] = useState("");
  async function save() { if (!text.trim()) return; await apiClient.post(`/customers/${customer.id}/notes`, { category, text: text.trim() }); setText(""); await reload(); }
  return <div className="customer-panel"><SectionTitle icon={History} title="Histórico e observações" subtitle="Registro cronológico de informações relevantes do cliente." /><div className="note-editor"><label><span>Categoria</span><select value={category} onChange={(e) => setCategory(e.target.value)}><option value="general">Geral</option><option value="commercial">Comercial</option><option value="financial">Financeiro</option><option value="technical">Técnico</option><option value="administrative">Administrativo</option></select></label><label><span>Nova observação</span><textarea rows={3} value={text} onChange={(e) => setText(e.target.value)}/></label><button className="customers-primary" onClick={() => void save()} disabled={!text.trim()}><Plus size={16}/>Registrar</button></div><div className="notes-list">{customer.notes_history.map((note) => <article key={note.id}><span>{note.category}</span><p>{note.text}</p><small>{new Date(note.created_at).toLocaleString("pt-BR")}</small></article>)}</div></div>;
}

function SectionTitle({ icon: Icon, title, subtitle }: { icon: typeof Building2; title: string; subtitle: string }) { return <div className="section-title"><span><Icon size={17}/></span><div><h3>{title}</h3><p>{subtitle}</p></div></div>; }

export default CustomerMaster;
