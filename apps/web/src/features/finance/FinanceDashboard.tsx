import { useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowDownRight, ArrowLeftRight, ArrowUpRight, Bell, Building2, CalendarRange,
  CheckCircle2, ChevronLeft, ChevronRight, CircleDollarSign, Clock3, Download, Eye, FileSearch,
  Landmark, LayoutDashboard, LogOut, Menu, Paperclip, Pencil, Plus, ReceiptText,
  RotateCcw, Search, ShieldCheck, Trash2, TriangleAlert, UploadCloud, WalletCards, X,
} from "lucide-react";
import { useNavigate } from "react-router-dom";

import { apiClient } from "../../shared/api/apiClient";
import { CashFlowChart, CompositionDonut } from "./components/FinanceCharts";
import type { AuthUser } from "../auth/AuthCard";
import type {
  AuditEvent, BillingConfirmation, BillingReadiness, CompanyCode, CompanyFilter, DateBasis, EntryStatus, EntryType, ExpenseKind,
  FinanceDateBounds, FinanceEvent, FinanceStatus, FinanceSummary, FinanceWorkOrderOption, FinancialEntry, InvoiceType,
} from "./types";
import "./finance.css";

type Props = { user: AuthUser; onLogout: () => void };
type FinanceView = "operations" | "income" | "expense" | "forecast" | "transfers" | "balance" | "audit";
type EntryForm = {
  entry_type: EntryType; company_code: CompanyCode; invoice_type: InvoiceType | ""; series: string;
  nfse_number: string; nfe_number: string;
  counterparty_name: string; description: string; amount: string; issue_date: string;
  posting_date: string; due_date: string; bank_name: string; expense_kind: ExpenseKind;
  document_number: string; payment_code: string; notes: string; work_order_id: string;
};

const now = new Date();
const currentDate = () => new Date().toISOString().slice(0, 10);
const firstDayOfMonth = (year: number, month: number) => `${year}-${String(month).padStart(2, "0")}-01`;
const lastDayOfMonth = (year: number, month: number) => new Date(year, month, 0).toISOString().slice(0, 10);
const companies = [
  { code: "universo_eletronica" as const, name: "Universo Eletrônica", short: "UE", banks: ["Itaú", "Bradesco"] },
  { code: "universo_automacao" as const, name: "Universo Automação", short: "UA", banks: ["Banco do Brasil", "Bradesco"] },
  { code: "solucoes_eletronica" as const, name: "Soluções Eletrônica", short: "SE", banks: ["Bradesco"] },
];
const months = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"];
const views = [
  ["operations", "Painel de operações", LayoutDashboard], ["income", "Receitas", ArrowUpRight],
  ["expense", "Saídas", ArrowDownRight], ["forecast", "Previsão de fluxo", CalendarRange],
  ["transfers", "Remanejamentos", ArrowLeftRight], ["balance", "Balanço financeiro", CircleDollarSign],
  ["audit", "Auditoria", FileSearch],
] as const;
const statusMeta: Record<FinanceStatus, { label: string; icon: typeof Clock3 }> = {
  overdue: { label: "Atrasado", icon: Clock3 }, due_soon: { label: "Próximo vencimento", icon: Bell },
  on_time: { label: "Dentro do prazo", icon: CalendarRange }, settled: { label: "Baixado", icon: CheckCircle2 },
};
const expenseLabels: Record<ExpenseKind, string> = {
  fixed: "Despesa fixa", tax: "Imposto", salary: "Salário", supplier: "Fornecedor", variable: "Despesa variável",
};
const actionLabels: Record<string, string> = {
  created: "Criação", updated: "Edição", deleted: "Exclusão", settled: "Baixa",
  settlement_reversed: "Baixa desfeita", attachment_added: "Anexo incluído",
};

function initialForm(company: CompanyCode, type: EntryType): EntryForm {
  return {
    entry_type: type, company_code: company, invoice_type: "", series: "",
    nfse_number: "", nfe_number: "",
    counterparty_name: "", description: "", amount: "", issue_date: currentDate(), posting_date: currentDate(),
    due_date: currentDate(), bank_name: companies.find((item) => item.code === company)?.banks[0] ?? "",
    expense_kind: "fixed", document_number: "", payment_code: "", notes: "", work_order_id: "",
  };
}
const emptyBillingConfirmation = (): BillingConfirmation => ({
  purchase_order_number: "", customer_order_number: "", measurement_reference: "",
  service_report_confirmed: false, portal_submitted: false, portal_protocol: "",
  invoice_email_confirmed: false, xml_email_confirmed: false, notes: "",
});
function money(value: number) { return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(value); }
function companyName(code: CompanyCode) { return companies.find((item) => item.code === code)?.name ?? code; }
function dateBR(value?: string | null) { return value ? new Intl.DateTimeFormat("pt-BR").format(new Date(`${value}T12:00:00`)) : "—"; }
function parseAmount(value: string) { return Number(value.replace(/\./g, "").replace(",", ".")); }
function queryScope(company: CompanyFilter, startDate: string, endDate: string, dateBasis: DateBasis) {
  const scope = company === "consolidated" ? "consolidated=true" : `company_code=${company}`;
  return `${scope}&start_date=${startDate}&end_date=${endDate}&date_basis=${dateBasis}`;
}
const dateBasisLabels: Record<DateBasis, string> = {
  posting: "Competência / lançamento", issue: "Emissão", due: "Vencimento", settlement: "Baixa",
};


function FinancePeriodSummary({ view, summary, entries, periodLabel }: { view: FinanceView; summary: FinanceSummary; entries: FinancialEntry[]; periodLabel: string }) {
  const today = new Date(); today.setHours(0, 0, 0, 0);
  const overdueIncome = entries.filter((item) => item.entry_type === "income" && item.status === "pending" && new Date(`${item.due_date}T00:00:00`) < today).reduce((total, item) => total + Number(item.amount), 0);
  const overdueExpense = entries.filter((item) => item.entry_type === "expense" && item.status === "pending" && new Date(`${item.due_date}T00:00:00`) < today).reduce((total, item) => total + Number(item.amount), 0);

  if (view === "income") return <>
    <section className="finance-kpis finance-kpis--classic">
      <article className="finance-kpi finance-kpi--neutral"><span>Total filtrado</span><strong>{money(summary.period_income)}</strong><small>{summary.period_income_count} receitas · {periodLabel}</small></article>
      <article className="finance-kpi finance-kpi--positive"><span>Efetivado</span><strong>{money(summary.settled_income)}</strong><small>Receitas já baixadas</small></article>
      <article className="finance-kpi finance-kpi--warning"><span>Em aberto</span><strong>{money(summary.pending_income)}</strong><small>A receber no período</small></article>
      <article className="finance-kpi finance-kpi--negative"><span>Atrasado</span><strong>{money(overdueIncome)}</strong><small>Receitas vencidas e pendentes</small></article>
    </section>
  </>;

  if (view === "expense") return <>
    <section className="finance-kpis finance-kpis--classic">
      <article className="finance-kpi finance-kpi--neutral"><span>Total filtrado</span><strong>{money(summary.period_expense)}</strong><small>{summary.period_expense_count} saídas · {periodLabel}</small></article>
      <article className="finance-kpi finance-kpi--positive"><span>Efetivado</span><strong>{money(summary.settled_expense)}</strong><small>Saídas já pagas</small></article>
      <article className="finance-kpi finance-kpi--warning"><span>Em aberto</span><strong>{money(summary.pending_expense)}</strong><small>A pagar no período</small></article>
      <article className="finance-kpi finance-kpi--negative"><span>Atrasado</span><strong>{money(overdueExpense)}</strong><small>Saídas vencidas e pendentes</small></article>
    </section>
  </>;

  if (view !== "operations") return <div className="finance-reconciliation-strip finance-reconciliation-strip--compact"><span><b>{summary.period_entry_count}</b> lançamentos</span><span>Receitas: <b>{money(summary.period_income)}</b></span><span>Saídas: <b>{money(summary.period_expense)}</b></span><span>Resultado: <b>{money(summary.period_result)}</b></span></div>;

  return <>
    <section className="finance-kpis finance-kpis--classic">
      <article className="finance-kpi finance-kpi--neutral"><span>Total faturado</span><strong>{money(summary.period_income)}</strong><small>{summary.period_income_count} receitas · {periodLabel}</small></article>
      <article className="finance-kpi finance-kpi--positive"><span>Efetivado</span><strong>{money(summary.settled_income)}</strong><small>Receitas já baixadas</small></article>
      <article className="finance-kpi finance-kpi--warning"><span>Em aberto</span><strong>{money(summary.pending_income)}</strong><small>Contas a receber</small></article>
      <article className="finance-kpi finance-kpi--negative"><span>Atrasado</span><strong>{money(overdueIncome)}</strong><small>Receitas vencidas</small></article>
    </section>
    <section className="finance-secondary-metrics">
      <article><span>Saídas filtradas</span><strong>{money(summary.period_expense)}</strong><small>{summary.period_expense_count} lançamentos</small></article>
      <article><span>Pago no período</span><strong>{money(summary.settled_expense)}</strong><small>Saídas efetivadas</small></article>
      <article><span>A pagar</span><strong>{money(summary.pending_expense)}</strong><small>{overdueExpense > 0 ? `${money(overdueExpense)} atrasado` : "Sem atraso no período"}</small></article>
      <article className={summary.period_result >= 0 ? "is-positive" : "is-negative"}><span>Resultado do período</span><strong>{money(summary.period_result)}</strong><small>Receitas menos saídas</small></article>
    </section>
  </>;
}

function EventCard({ event, onOpen }: { event: FinanceEvent; onOpen: (id: number) => void }) {
  const meta = statusMeta[event.status]; const Icon = meta.icon;
  return <button className={`finance-event finance-event--${event.status}`} onClick={() => onOpen(event.id)}>
    <span className="finance-event__rail" /><span className="finance-event__body">
      <span className="finance-event__top"><span className="finance-event__status"><Icon size={14} />{meta.label}</span>
        <strong className={event.entry_type === "income" ? "amount-positive" : "amount-negative"}>{event.entry_type === "income" ? "+" : "−"}{money(event.amount)}</strong></span>
      <strong className="finance-event__title">{event.description}</strong><span className="finance-event__counterparty">{event.counterparty_name}</span>
      <span className="finance-event__footer"><span>{event.due_label}</span><span>{event.bank_name}</span></span>
    </span>
  </button>;
}

export function FinanceDashboard({ user, onLogout }: Props) {
  const navigate = useNavigate();
  const [view, setView] = useState<FinanceView>("operations");
  const [company, setCompany] = useState<CompanyFilter>("universo_eletronica");
  const [year, setYear] = useState(now.getFullYear());
  const [shortcut, setShortcut] = useState<string>(String(now.getMonth() + 1));
  const [startDate, setStartDate] = useState(firstDayOfMonth(now.getFullYear(), now.getMonth() + 1));
  const [endDate, setEndDate] = useState(currentDate());
  const [dateBasis, setDateBasis] = useState<DateBasis>("posting");
  const [dateBounds, setDateBounds] = useState<FinanceDateBounds | null>(null);
  const [summary, setSummary] = useState<FinanceSummary | null>(null);
  const [entries, setEntries] = useState<FinancialEntry[]>([]); const [audit, setAudit] = useState<AuditEvent[]>([]);
  const [search, setSearch] = useState("");
  const [serverSearch, setServerSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<EntryStatus | "overdue" | "all">("all");
  const [eventFilter, setEventFilter] = useState<FinanceStatus | "all">("all");
  const [selected, setSelected] = useState<FinancialEntry | null>(null); const [modalOpen, setModalOpen] = useState(false);
  const [form, setForm] = useState<EntryForm>(initialForm("universo_eletronica", "income"));
  const [attachment, setAttachment] = useState<File | null>(null); const [saving, setSaving] = useState(false);
  const [createRequestKey, setCreateRequestKey] = useState(() => crypto.randomUUID());
  const [previewOpen, setPreviewOpen] = useState(false);
  const [workOrders, setWorkOrders] = useState<FinanceWorkOrderOption[]>([]);
  const [workOrderSearch, setWorkOrderSearch] = useState("");
  const [billingReadiness, setBillingReadiness] = useState<BillingReadiness | null>(null);
  const [billingConfirmation, setBillingConfirmation] = useState<BillingConfirmation>(emptyBillingConfirmation());
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [mobileMenu, setMobileMenu] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => localStorage.getItem("nexus.finance.sidebar") === "collapsed");
  const requestSequence = useRef(0);

  const selectedCompany = company === "consolidated" ? "universo_eletronica" : company;
  const availableBanks = companies.find((item) => item.code === form.company_code)?.banks ?? [];
  const years = Array.from({ length: Math.max(1, now.getFullYear() - 2024 + 1) }, (_, index) => 2024 + index).reverse();

  async function loadData() {
    const requestId = ++requestSequence.current;
    if (!startDate || !endDate) return;
    if (endDate < startDate) {
      setSummary(null); setEntries([]); setError("A data final não pode ser anterior à data inicial.");
      return;
    }
    setLoading(true); setError("");
    const scope = queryScope(company, startDate, endDate, dateBasis);
    try {
      const [nextSummary, nextEntries] = await Promise.all([
        apiClient.request<FinanceSummary>(`/api/finance/summary?${scope}`),
        apiClient.request<FinancialEntry[]>(`/api/finance/entries?${scope}${view === "income" ? "&entry_type=income" : view === "expense" ? "&entry_type=expense" : ""}${statusFilter !== "all" && statusFilter !== "overdue" ? `&status=${statusFilter}` : ""}${serverSearch ? `&search=${encodeURIComponent(serverSearch)}` : ""}`),
      ]);
      if (requestId !== requestSequence.current) return;
      setSummary(nextSummary); setEntries(nextEntries);
      if (view === "audit") setAudit(await apiClient.request<AuditEvent[]>(`/api/finance/audit?start_date=${startDate}&end_date=${endDate}`));
    } catch (reason) {
      if (requestId !== requestSequence.current) return;
      setSummary(null); setEntries([]);
      setError(reason instanceof Error ? reason.message : "Não foi possível concluir a operação.");
    } finally {
      if (requestId === requestSequence.current) setLoading(false);
    }
  }
  useEffect(() => { void loadData(); }, [company, startDate, endDate, dateBasis, view, statusFilter, serverSearch]);
  useEffect(() => {
    const term = search.trim();
    // Ao apagar a pesquisa, remove o filtro do servidor imediatamente. Isso
    // evita manter em memória somente o subconjunto retornado pela busca anterior.
    if (term.length < 2) { setServerSearch(""); return; }
    const timer = window.setTimeout(() => setServerSearch(term), 250);
    return () => window.clearTimeout(timer);
  }, [search]);
  useEffect(() => { if (!error) return; const timer = window.setTimeout(() => setError(""), 6500); return () => window.clearTimeout(timer); }, [error]);
  useEffect(() => { localStorage.setItem("nexus.finance.sidebar", sidebarCollapsed ? "collapsed" : "expanded"); }, [sidebarCollapsed]);

  useEffect(() => {
    const companyScope = company === "consolidated" ? "consolidated=true" : `company_code=${company}`;
    apiClient.request<FinanceDateBounds>(`/api/finance/date-bounds?${companyScope}&date_basis=${dateBasis}`)
      .then(setDateBounds)
      .catch((reason: Error) => setError(reason.message));
  }, [company, dateBasis]);

  useEffect(() => {
    if (!modalOpen || form.entry_type !== "income") return;
    const term = workOrderSearch.trim();
    if (term.length < 2) { setWorkOrders([]); return; }
    const timer = window.setTimeout(() => {
      apiClient.request<FinanceWorkOrderOption[]>(`/api/finance/work-orders?company_code=${form.company_code}&search=${encodeURIComponent(term)}`)
        .then(setWorkOrders)
        .catch((reason: Error) => setError(reason.message));
    }, 250);
    return () => window.clearTimeout(timer);
  }, [modalOpen, form.entry_type, form.company_code, workOrderSearch]);

  useEffect(() => {
    if (!modalOpen || form.entry_type !== "income" || !form.work_order_id) { setBillingReadiness(null); return; }
    apiClient.request<BillingReadiness>(`/api/finance/work-orders/${form.work_order_id}/billing-readiness`)
      .then((readiness) => {
        setBillingReadiness(readiness);
        const order = workOrders.find((item) => item.id === Number(form.work_order_id));
        if (order) setForm((current) => ({
          ...current,
          counterparty_name: current.counterparty_name || order.customer_name,
          description: current.description || `Serviço de laboratório — ${order.number}`,
          amount: current.amount || (order.approved_value ? String(order.approved_value).replace(".", ",") : ""),
        }));
      })
      .catch((reason: Error) => setError(reason.message));
  }, [modalOpen, form.entry_type, form.work_order_id, workOrders]);

  const filteredEvents = (events: FinanceEvent[]) => eventFilter === "all" ? events : events.filter((item) => item.status === eventFilter);
  const visibleEntries = useMemo(() => {
    const term = search.trim().toLowerCase();
    const today = new Date();
    today.setHours(0, 0, 0, 0);

    return entries.filter((item) => {
      const matchesSearch = !term || [
        item.description,
        item.counterparty_name,
        item.series,
        item.nfse_number,
        item.nfe_number,
        item.document_number,
        item.bank_name,
      ].some((value) => value?.toLowerCase().includes(term));

      const dueDate = new Date(`${item.due_date}T00:00:00`);
      const isOverdue = item.status === "pending" && dueDate < today;
      const matchesStatus = statusFilter !== "overdue" || isOverdue;

      return matchesSearch && matchesStatus;
    });
  }, [entries, search, statusFilter]);

  function openNew(type: EntryType) { setSelected(null); setCreateRequestKey(crypto.randomUUID()); setForm(initialForm(selectedCompany, type)); setWorkOrderSearch(""); setWorkOrders([]); setBillingConfirmation(emptyBillingConfirmation()); setBillingReadiness(null); setAttachment(null); setModalOpen(true); }
  async function openEntry(id: number) { const entry = await apiClient.request<FinancialEntry>(`/api/finance/entries/${id}`); setSelected(entry); setForm({
    entry_type: entry.entry_type, company_code: entry.company_code, invoice_type: entry.invoice_type ?? "",
    series: entry.series ?? "", nfse_number: entry.nfse_number ?? "", nfe_number: entry.nfe_number ?? "", counterparty_name: entry.counterparty_name, description: entry.description,
    amount: String(entry.amount).replace(".", ","), issue_date: entry.issue_date, posting_date: entry.posting_date,
    due_date: entry.due_date, bank_name: entry.bank_name, expense_kind: entry.expense_kind ?? "fixed",
    document_number: entry.document_number ?? "", payment_code: entry.payment_code ?? "", notes: entry.notes ?? "", work_order_id: entry.work_order_id ? String(entry.work_order_id) : "",
  });
    const stored = (entry.billing_compliance?.confirmation ?? {}) as Partial<BillingConfirmation>;
    setBillingConfirmation({ ...emptyBillingConfirmation(), ...stored });
    setWorkOrderSearch(""); setWorkOrders([]); setAttachment(null); setModalOpen(true); }

  async function saveEntry(event: React.FormEvent) {
    event.preventDefault(); setSaving(true); setError("");
    try {
      const invoiceType = form.nfse_number.trim() && !form.nfe_number.trim()
        ? "nfse"
        : form.nfe_number.trim() && !form.nfse_number.trim()
          ? "nfe"
          : null;
      const body = JSON.stringify({
        ...form,
        // O Financeiro usa a emissão como competência operacional.
        // posting_date permanece no contrato da API por compatibilidade histórica,
        // mas não é mais um campo manual na interface.
        posting_date: form.issue_date,
        amount: parseAmount(form.amount),
        invoice_type: form.entry_type === "income" ? invoiceType : null,
        nfse_number: form.entry_type === "income" ? form.nfse_number.trim() || null : null,
        nfe_number: form.entry_type === "income" ? form.nfe_number.trim() || null : null,
        series: form.series || null,
        expense_kind: form.entry_type === "expense" ? form.expense_kind : null,
        document_number: form.entry_type === "expense" ? form.document_number || null : null,
        payment_code: form.payment_code || null,
        notes: form.notes || null,
        work_order_id: form.entry_type === "income" && form.work_order_id ? Number(form.work_order_id) : null,
        billing_confirmation: form.entry_type === "income" && form.work_order_id ? billingConfirmation : null,
      });
      const entry = await apiClient.request<FinancialEntry>(selected ? `/api/finance/entries/${selected.id}` : "/api/finance/entries", {
        method: selected ? "PUT" : "POST",
        headers: {
          "Content-Type": "application/json",
          ...(!selected ? { "Idempotency-Key": createRequestKey } : {}),
        },
        body,
      });
      if (attachment) {
        const upload = new FormData();
        upload.append("file", attachment);
        try {
          await apiClient.request<FinancialEntry>(`/api/finance/entries/${entry.id}/attachment`, { method: "POST", body: upload });
        } catch (uploadReason) {
          // O lançamento já foi persistido antes do envio do arquivo. Mantemos o
          // usuário fora do risco de clicar em Salvar novamente e duplicar a receita/despesa.
          setSelected(await apiClient.request<FinancialEntry>(`/api/finance/entries/${entry.id}`));
          setAttachment(null);
          setError(uploadReason instanceof Error
            ? `Lançamento salvo, mas o anexo não foi enviado: ${uploadReason.message}`
            : "Lançamento salvo, mas o anexo não foi enviado.");
          await loadData();
          return;
        }
      }
      setModalOpen(false); await loadData();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Falha ao salvar."); }
    finally { setSaving(false); }
  }
  async function removeEntry() {
    if (!selected || !confirm("Excluir este lançamento? A ação ficará registrada na auditoria.")) return;
    await apiClient.request(`/api/finance/entries/${selected.id}`, { method: "DELETE" }); setModalOpen(false); await loadData();
  }
  async function toggleSettlement() {
    if (!selected) return;
    if (selected.status === "pending") {
      const settlementDate = prompt("Data da baixa (AAAA-MM-DD):", currentDate()); if (!settlementDate) return;
      await apiClient.request(`/api/finance/entries/${selected.id}/settle`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ settlement_date: settlementDate }) });
    } else await apiClient.request(`/api/finance/entries/${selected.id}/unsettle`, { method: "POST" });
    const refreshed = await apiClient.request<FinancialEntry>(`/api/finance/entries/${selected.id}`); setSelected(refreshed); await loadData();
  }

  function applyShortcut(nextShortcut: string, nextYear = year) {
    setShortcut(nextShortcut); setYear(nextYear);
    if (nextShortcut === "custom") return;
    if (nextShortcut === "year") {
      setStartDate(`${nextYear}-01-01`);
      setEndDate(nextYear === now.getFullYear() ? currentDate() : `${nextYear}-12-31`);
      return;
    }
    const nextMonth = Number(nextShortcut);
    setStartDate(firstDayOfMonth(nextYear, nextMonth));
    const monthEnd = lastDayOfMonth(nextYear, nextMonth);
    setEndDate(nextYear === now.getFullYear() && nextMonth === now.getMonth() + 1 && monthEnd > currentDate() ? currentDate() : monthEnd);
  }
  function changeYear(nextYear: number) {
    setYear(nextYear);
    if (shortcut !== "custom") applyShortcut(shortcut, nextYear);
  }
  function manualStart(value: string) { setStartDate(value); setShortcut("custom"); }
  function manualEnd(value: string) { setEndDate(value); setShortcut("custom"); }

  const periodLabel = summary ? `${dateBR(summary.period_start)} até ${dateBR(summary.period_end)}` : `${dateBR(startDate)} até ${dateBR(endDate)}`;
  const title = views.find(([key]) => key === view)?.[1] ?? "Financeiro";
  return <div className={`finance-shell ${sidebarCollapsed ? "finance-shell--collapsed" : ""}`}>
    <aside className={`finance-sidebar ${mobileMenu ? "is-open" : ""} ${sidebarCollapsed ? "is-collapsed" : ""}`}>
      <button className="finance-sidebar-toggle" type="button" onClick={() => setSidebarCollapsed((value) => !value)} title={sidebarCollapsed ? "Expandir menu" : "Recolher menu"}>{sidebarCollapsed ? <ChevronRight size={18}/> : <ChevronLeft size={18}/>}</button>
      <div><button className="finance-brand" onClick={() => navigate("/painel")}><span>N</span><strong>NEXUS</strong></button>
        <div className="finance-module-title"><WalletCards size={19}/><div><small>MÓDULO</small><strong>Financeiro</strong></div></div>
        <nav>{views.map(([key, label, Icon]) => <button key={key} className={view === key ? "active" : ""} onClick={() => { setView(key); setMobileMenu(false); }}><Icon size={18}/><span>{label}</span></button>)}</nav>
        <button className="finance-back" onClick={() => navigate("/painel")}><LayoutDashboard size={18}/>Voltar ao painel geral</button></div>
      <div className="finance-user"><span>{user.name.slice(0, 2).toUpperCase()}</span><div><strong>{user.name}</strong><small>{user.role}</small></div><button onClick={onLogout}><LogOut size={18}/></button></div>
    </aside>
    <main className="finance-main">
      <header className="finance-header"><button className="mobile-menu-button" onClick={() => setMobileMenu(!mobileMenu)}><Menu/></button>
        <div className="finance-heading"><span>GESTÃO FINANCEIRA PREMIUM</span><h1>{title}</h1><p>Receitas e saídas separadas, visão por competência, baixas e auditoria completa.</p></div>
        <div className="finance-header__tools"><button className="finance-primary income" onClick={() => openNew("income")}><ArrowUpRight size={18}/>Nova receita</button><button className="finance-primary expense" onClick={() => openNew("expense")}><ArrowDownRight size={18}/>Nova saída</button></div>
      </header>

      <section className="finance-toolbar">
        <div className="finance-company-grid" aria-label="Empresa">{companies.map((item) => <button key={item.code} className={company === item.code ? "active" : ""} onClick={() => setCompany(item.code)}><b>{item.short}</b><span>{item.name}</span></button>)}<button className={company === "consolidated" ? "active" : ""} onClick={() => setCompany("consolidated")}><b>GR</b><span>Consolidado</span></button></div>
        <div className="finance-date-grid">
          <label className="filter-shortcut"><small>Atalho</small><select value={shortcut} onChange={(e) => applyShortcut(e.target.value)}><option value="custom">Personalizado</option><option value="year">Ano inteiro</option>{months.map((name, index) => <option key={name} value={String(index + 1)}>{name}</option>)}</select></label>
          <label className="filter-year"><small>Ano</small><select value={year} onChange={(e) => changeYear(Number(e.target.value))}>{years.map((item) => <option key={item}>{item}</option>)}</select></label>
          <label className="filter-start"><small>Data inicial</small><input type="date" value={startDate} onChange={(e) => manualStart(e.target.value)} /></label>
          <label className="filter-end"><small>Data final</small><input type="date" value={endDate} min={startDate || undefined} onChange={(e) => manualEnd(e.target.value)} /></label>
          <label className="filter-basis"><small>Base da data</small><select value={dateBasis} onChange={(e) => setDateBasis(e.target.value as DateBasis)}><option value="posting">Competência / lançamento</option><option value="issue">Emissão</option><option value="due">Vencimento</option><option value="settlement">Baixa</option></select></label>
        </div>
      </section>
      <section className="finance-period-audit">
        <div><strong>{periodLabel}</strong><span>•</span>{dateBasisLabels[dateBasis]}</div>
        <div>{dateBounds?.min_date && dateBounds?.max_date ? <>Base: <b>{dateBR(dateBounds.min_date)}</b>–<b>{dateBR(dateBounds.max_date)}</b> · {dateBounds.count} lançamentos</> : "Consultando base..."}</div>
      </section>
      {error && <div className="finance-toast" role="alert"><TriangleAlert size={18}/><span>{error}</span><button onClick={() => setError("")} aria-label="Fechar"><X size={16}/></button></div>}
      {loading && <div className="finance-filter-loading">Atualizando período…</div>}

      {summary && !loading && <FinancePeriodSummary view={view} summary={summary} entries={entries} periodLabel={periodLabel} />}

      {view === "operations" && summary && <>
        <CashFlowChart points={summary.cash_flow} />
        <section className="finance-section-head"><div><span>RADAR FINANCEIRO</span><h2>Movimentações de {periodLabel}</h2><p>Filtro aplicado pela data de {dateBasisLabels[dateBasis].toLowerCase()}.</p></div>
          <div className="status-filter">{(["all", "overdue", "due_soon", "settled"] as const).map((item) => <button key={item} className={eventFilter === item ? "active" : ""} onClick={() => setEventFilter(item)}>{item === "all" ? "Todos" : statusMeta[item].label}</button>)}</div></section>
        <section className="event-columns"><div className="event-column income-column"><header><div><ArrowUpRight/><span>Receitas</span></div><strong>{money(summary.period_income)}</strong></header><div className="finance-events">{filteredEvents(summary.income_events).map((event) => <EventCard key={event.id} event={event} onOpen={openEntry}/>) || null}{!filteredEvents(summary.income_events).length && <p className="finance-empty">Nenhuma receita no período.</p>}</div></div>
          <div className="event-column expense-column"><header><div><ArrowDownRight/><span>Saídas</span></div><strong>{money(summary.period_expense)}</strong></header><div className="finance-events">{filteredEvents(summary.expense_events).map((event) => <EventCard key={event.id} event={event} onOpen={openEntry}/>) || null}{!filteredEvents(summary.expense_events).length && <p className="finance-empty">Nenhuma saída no período.</p>}</div></div></section>
      </>}

      {(view === "income" || view === "expense") && <section className="ledger-panel"><header><div><span>{view === "income" ? "CONTAS A RECEBER" : "CONTAS A PAGAR"}</span><h2>{view === "income" ? "Receitas" : "Saídas"} do período</h2></div><div className="ledger-tools"><label><Search size={16}/><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Buscar cliente, série, NFS-e ou NF-e"/></label><select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value as EntryStatus | "overdue" | "all")}><option value="all">Todos os status</option><option value="pending">Pendente</option><option value="overdue">Atrasado</option><option value={view === "income" ? "received" : "paid"}>Baixado</option></select></div></header>
        <div className="ledger-list ledger-list--detailed"><div className="ledger-row ledger-row--detailed ledger-head"><span>Banco</span><span>Cliente / favorecido</span><span>Série</span><span>NFS-e</span><span>NF-e</span><span>Emissão</span><span>Vencimento</span><span>Valor</span><span>Status</span><span/></div>{visibleEntries.map((entry) => { const overdue = entry.status === "pending" && new Date(`${entry.due_date}T00:00:00`) < new Date(new Date().setHours(0, 0, 0, 0)); return <button className="ledger-row ledger-row--detailed" key={entry.id} onClick={() => openEntry(entry.id)}><span><strong>{entry.bank_name}</strong><small>{companyName(entry.company_code)}</small></span><span><strong>{entry.counterparty_name}</strong><small>{entry.description}</small></span><span>{entry.series || "—"}</span><span>{entry.nfse_number || "—"}</span><span>{entry.nfe_number || "—"}</span><span>{dateBR(entry.issue_date)}</span><span className={overdue ? "date-overdue" : ""}>{dateBR(entry.due_date)}</span><span className={entry.entry_type === "income" ? "amount-positive" : "amount-negative"}>{money(entry.amount)}</span><span><i className={`status-pill ${overdue ? "overdue" : entry.status}`}>{overdue ? "Atrasado" : entry.status === "pending" ? "Pendente" : "Baixado"}</i></span><ChevronRight size={17}/></button>})}{!visibleEntries.length && <p className="finance-empty">Nenhum lançamento encontrado.</p>}</div></section>}

      {view === "forecast" && summary && <>
        <CashFlowChart
          points={summary.cash_flow}
          title="Projeção do fluxo de caixa"
          subtitle="Leitura visual das receitas, saídas e do saldo projetado por semana."
        />
        <section className="ledger-panel"><header><div><span>PREVISÃO</span><h2>Fluxo por semana</h2></div></header><div className="flow-table"><div className="flow-row flow-head"><span>Período</span><span>Receitas</span><span>Saídas</span><span>Saldo projetado</span></div>{summary.cash_flow.map((point) => <div className="flow-row" key={point.label}><span>{point.label}</span><strong className="amount-positive">{money(point.income)}</strong><strong className="amount-negative">{money(point.expense)}</strong><strong>{money(point.balance)}</strong></div>)}</div></section>
      </>}
      {view === "transfers" && <section className="finance-placeholder"><ArrowLeftRight size={42}/><h2>Remanejamentos</h2><p>Estrutura preservada para transferências entre contas. A próxima etapa liga contas bancárias por empresa e conciliação.</p></section>}
      {view === "balance" && summary && <section className="balance-lab"><article className="balance-hero"><div><span>RESULTADO EXECUTIVO</span><h2>{company === "consolidated" ? "Grupo consolidado" : companyName(company)}</h2><p>{periodLabel}</p></div><CircleDollarSign size={54}/></article><div className="balance-cards"><article><span>Receitas</span><strong className="amount-positive">{money(summary.period_income)}</strong><small>Faturamento lançado</small></article><article><span>Saídas</span><strong className="amount-negative">{money(summary.period_expense)}</strong><small>Despesas lançadas</small></article><article><span>Resultado</span><strong>{money(summary.period_income - summary.period_expense)}</strong><small>Receitas menos saídas</small></article></div><article className="balance-visual"><h3>Composição do período</h3><CompositionDonut income={summary.period_income} expense={summary.period_expense}/><div className="balance-bars"><div><span>Receitas</span><i style={{ width: `${Math.min(100, summary.period_income / Math.max(summary.period_income, summary.period_expense, 1) * 100)}%` }}/><strong>{money(summary.period_income)}</strong></div><div className="expense-bar"><span>Saídas</span><i style={{ width: `${Math.min(100, summary.period_expense / Math.max(summary.period_income, summary.period_expense, 1) * 100)}%` }}/><strong>{money(summary.period_expense)}</strong></div></div></article></section>}
      {view === "audit" && <section className="ledger-panel"><header><div><span>RASTREABILIDADE</span><h2>Auditoria financeira</h2><p>Usuário, data, hora e alteração executada.</p></div></header><div className="audit-list">{audit.map((item) => <article key={item.id}><span className={`audit-action ${item.action}`}>{actionLabels[item.action] ?? item.action}</span><div><strong>{item.description}</strong><small>{item.user_name} · {new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "medium" }).format(new Date(item.created_at))}</small></div><span>#{item.entity_id}</span></article>)}{!audit.length && <p className="finance-empty">Nenhum evento de auditoria no período.</p>}</div></section>}
    </main>

    {modalOpen && <div className="finance-modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && setModalOpen(false)}><section className="finance-modal"><header><div><span>{selected ? "DETALHES DO LANÇAMENTO" : "NOVO REGISTRO"}</span><h2>{form.entry_type === "income" ? "Receita financeira" : "Saída financeira"}</h2></div><button onClick={() => setModalOpen(false)}><X/></button></header>
      {selected && <div className="entry-actions"><button className={selected.status === "pending" ? "settle" : "reverse"} onClick={toggleSettlement}>{selected.status === "pending" ? <><CheckCircle2 size={17}/>Dar baixa</> : <><RotateCcw size={17}/>Desfazer baixa</>}</button>{selected.attachment_name && <button type="button" onClick={() => setPreviewOpen(true)}><Eye size={17}/>Visualizar anexo</button>}<button className="delete" onClick={removeEntry}><Trash2 size={17}/>Excluir</button></div>}
      <form onSubmit={saveEntry}><div className="entry-type-toggle"><button type="button" className={form.entry_type === "income" ? "income active" : "income"} onClick={() => !selected && setForm(initialForm(form.company_code, "income"))}>Entrada · Receita</button><button type="button" className={form.entry_type === "expense" ? "expense active" : "expense"} onClick={() => !selected && setForm(initialForm(form.company_code, "expense"))}>Saída · Despesa</button></div>
        <div className="form-row"><label>Empresa<select value={form.company_code} onChange={(e) => { const code = e.target.value as CompanyCode; setForm((old) => ({ ...old, company_code: code, bank_name: companies.find((item) => item.code === code)?.banks[0] ?? "" })); }}>{companies.map((item) => <option key={item.code} value={item.code}>{item.name}</option>)}</select></label><label>Banco<select value={form.bank_name} onChange={(e) => setForm({ ...form, bank_name: e.target.value })}>{availableBanks.map((bank) => <option key={bank}>{bank}</option>)}</select></label></div>
        {form.entry_type === "income" && <section className="billing-workflow-card">
          <header><div><span>INTEGRAÇÃO COM A OS</span><strong>Conformidade de faturamento</strong></div><ShieldCheck size={22}/></header>
          <div className="finance-os-search"><label>Buscar Ordem de Serviço<div className="finance-os-searchbox"><Search size={17}/><input value={workOrderSearch} onChange={(e) => setWorkOrderSearch(e.target.value)} placeholder="Digite OS, cliente ou série..." /></div></label>
            {form.work_order_id && billingReadiness && <div className="finance-os-selected"><div><small>OS SELECIONADA</small><strong>{billingReadiness.work_order_number} · {billingReadiness.customer_name}</strong></div><button type="button" onClick={() => { setForm({ ...form, work_order_id: "" }); setBillingReadiness(null); setBillingConfirmation(emptyBillingConfirmation()); setWorkOrderSearch(""); setWorkOrders([]); }}>Trocar OS</button></div>}
            {!form.work_order_id && workOrderSearch.trim().length >= 2 && <div className="finance-os-results">{workOrders.map((order) => <button type="button" key={order.id} onClick={() => { setForm({ ...form, work_order_id: String(order.id) }); setWorkOrderSearch(`${order.number} · ${order.customer_name}`); setBillingConfirmation(emptyBillingConfirmation()); }}><strong>{order.number}</strong><span>{order.customer_name} · {order.equipment_label}</span>{order.approved_value != null && <small>{money(Number(order.approved_value))}</small>}</button>)}{!workOrders.length && <div>Nenhuma OS encontrada.</div>}</div>}
            {!form.work_order_id && workOrderSearch.trim().length < 2 && <small className="finance-os-hint">Digite pelo menos 2 caracteres para localizar a OS. Deixe em branco para receita sem vínculo.</small>}
          </div>
          {billingReadiness && <div className="billing-readiness">
            <div className="billing-readiness__summary"><span><b>{billingReadiness.work_order_number}</b><small>{billingReadiness.customer_name}</small></span>{billingReadiness.approved_value != null && <strong>{money(Number(billingReadiness.approved_value))}</strong>}</div>
            {(billingReadiness.billing_instructions || billingReadiness.financial_notes) && <div className="billing-guidance"><TriangleAlert size={16}/><span>{billingReadiness.billing_instructions || billingReadiness.financial_notes}</span></div>}
            <div className="billing-checklist">
              {billingReadiness.items.some((item) => item.key === "purchase_order") && <label><span>PO / pedido de compra {billingReadiness.items.find((item) => item.key === "purchase_order")?.required ? "*" : ""}</span><input value={billingConfirmation.purchase_order_number} onChange={(e) => setBillingConfirmation({ ...billingConfirmation, purchase_order_number: e.target.value })} placeholder="Número da PO"/></label>}
              {billingReadiness.items.some((item) => item.key === "customer_order") && <label><span>OS / pedido do cliente {billingReadiness.items.find((item) => item.key === "customer_order")?.required ? "*" : ""}</span><input value={billingConfirmation.customer_order_number} onChange={(e) => setBillingConfirmation({ ...billingConfirmation, customer_order_number: e.target.value })} placeholder="Referência do cliente"/></label>}
              {billingReadiness.items.some((item) => item.key === "measurement") && <label><span>Medição {billingReadiness.items.find((item) => item.key === "measurement")?.required ? "*" : ""}</span><input value={billingConfirmation.measurement_reference} onChange={(e) => setBillingConfirmation({ ...billingConfirmation, measurement_reference: e.target.value })} placeholder="Número / referência"/></label>}
              {billingReadiness.items.filter((item) => ["service_report","portal","invoice_email","xml_email"].includes(item.key)).map((item) => { const field = item.key === "service_report" ? "service_report_confirmed" : item.key === "portal" ? "portal_submitted" : item.key === "invoice_email" ? "invoice_email_confirmed" : "xml_email_confirmed"; return <label className="billing-check" key={item.key}><input type="checkbox" checked={Boolean(billingConfirmation[field as keyof BillingConfirmation])} onChange={(e) => setBillingConfirmation({ ...billingConfirmation, [field]: e.target.checked })}/><span><strong>{item.label}{item.required ? " *" : ""}</strong>{item.configured_value && <small>{item.configured_value}</small>}</span></label>; })}
            </div>
            {billingReadiness.portal_url && <label>Protocolo / comprovante do portal<input value={billingConfirmation.portal_protocol} onChange={(e) => setBillingConfirmation({ ...billingConfirmation, portal_protocol: e.target.value })} placeholder="Opcional: protocolo, chamado ou referência"/></label>}
            <label>Observação do checklist<textarea rows={2} value={billingConfirmation.notes} onChange={(e) => setBillingConfirmation({ ...billingConfirmation, notes: e.target.value })} placeholder="Exceções, observações e evidências do faturamento"/></label>
          </div>}
        </section>}
        <div className="form-row"><label>{form.entry_type === "income" ? "Cliente" : "Cliente / fornecedor"}<input required value={form.counterparty_name} onChange={(e) => setForm({ ...form, counterparty_name: e.target.value })}/></label>{form.entry_type === "expense" && <label>Classificação<select value={form.expense_kind} onChange={(e) => setForm({ ...form, expense_kind: e.target.value as ExpenseKind })}>{Object.entries(expenseLabels).map(([key, value]) => <option key={key} value={key}>{value}</option>)}</select></label>}</div>
        <div className="form-row"><label>Descrição<input required value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })}/></label><label>Valor<input required inputMode="decimal" placeholder="0,00" value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })}/></label></div>
        {form.entry_type === "income" && <><div className="form-row"><label>NFS-e<input value={form.nfse_number} onChange={(e) => setForm({ ...form, nfse_number: e.target.value })} placeholder="Número da NFS-e"/></label><label>NF-e<input value={form.nfe_number} onChange={(e) => setForm({ ...form, nfe_number: e.target.value })} placeholder="Número da NF-e"/></label></div><label>Série<input value={form.series} onChange={(e) => setForm({ ...form, series: e.target.value })} placeholder="Ex.: 1"/></label><small className="invoice-hint">{selected && !form.nfse_number && !form.nfe_number ? "Registro histórico sem NF: pode ser editado e salvo normalmente." : "Preencha pelo menos uma das caixas: NFS-e ou NF-e."}</small></>}
        {form.entry_type === "expense" && <label>Documento / referência<input value={form.document_number} onChange={(e) => setForm({ ...form, document_number: e.target.value })}/></label>}
        <div className="form-row"><label>Data de emissão<input type="date" required value={form.issue_date} onChange={(e) => setForm({ ...form, issue_date: e.target.value, posting_date: e.target.value })}/></label><label>Vencimento<input type="date" required value={form.due_date} onChange={(e) => setForm({ ...form, due_date: e.target.value })}/></label></div>
        {form.entry_type === "expense" && <label>Chave PIX ou código do boleto<textarea rows={2} value={form.payment_code} onChange={(e) => setForm({ ...form, payment_code: e.target.value })}/></label>}
        <label>Observações<textarea rows={3} value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })}/></label>
        <label className="attachment-field"><UploadCloud/><span><strong>{attachment?.name || selected?.attachment_name || "Anexar comprovante, boleto ou PDF"}</strong><small>PDF, JPG, PNG ou WEBP · até 10 MB</small></span><input type="file" accept=".pdf,.jpg,.jpeg,.png,.webp" onChange={(e) => setAttachment(e.target.files?.[0] ?? null)}/></label>
        {selected && <div className="entry-meta"><span>Status: <b>{selected.status === "pending" ? "Pendente" : "Baixado"}</b></span><span>Baixa: <b>{dateBR(selected.settlement_date)}</b></span><span>Atualizado: <b>{new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "short" }).format(new Date(selected.updated_at))}</b></span></div>}
        <footer><button type="button" onClick={() => setModalOpen(false)}>Cancelar</button><button className="finance-primary" disabled={saving}>{selected ? <Pencil size={17}/> : <Plus size={17}/>} {saving ? "Salvando..." : selected ? "Salvar alterações" : "Salvar lançamento"}</button></footer>
      </form></section></div>}
    {previewOpen && selected?.attachment_name && <div className="attachment-preview-backdrop" onMouseDown={(e) => e.target === e.currentTarget && setPreviewOpen(false)}><section className="attachment-preview"><header><div><span>ANEXO DO LANÇAMENTO</span><strong>{selected.attachment_name}</strong></div><button type="button" onClick={() => setPreviewOpen(false)}><X/></button></header>{selected.attachment_mime?.startsWith("image/") ? <img src={`/api/finance/entries/${selected.id}/attachment/preview`} alt={selected.attachment_name}/> : <iframe src={`/api/finance/entries/${selected.id}/attachment/preview`} title={selected.attachment_name}/>}</section></div>}
  </div>;
}
