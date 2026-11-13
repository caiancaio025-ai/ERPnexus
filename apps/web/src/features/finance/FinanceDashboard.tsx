import { useEffect, useRef, useState } from "react";
import {
  ArrowDownRight, ArrowLeftRight, ArrowUpRight, Bell, Building2, CalendarRange,
  CheckCircle2, ChevronLeft, ChevronRight, CircleDollarSign, Clock3, Download, Eye, FileSearch,
  Landmark, LayoutDashboard, LogOut, Menu, Paperclip, Pencil, Plus, ReceiptText,
  RotateCcw, Search, ShieldCheck, Trash2, TriangleAlert, UploadCloud, WalletCards, X,
} from "lucide-react";
import { SenticoSidebar } from "../../shared/ui/SenticoSidebar";
import { useLocation, useNavigate } from "react-router-dom";
import { monthlyInstallmentDates, splitInstallmentAmounts } from "./installmentPlan";

import { apiClient } from "../../shared/api/apiClient";
import { CashFlowChart, CompositionDonut } from "./components/FinanceCharts";
import type { AuthUser } from "../auth/AuthCard";
import type {
  AuditEvent, BillingConfirmation, BillingReadiness, CompanyCode, CompanyFilter, DateBasis, EntryStatus, EntryType, ExpenseKind,
  FinanceDateBounds, FinanceEvent, FinanceStatus, FinanceSummary, FinanceWorkOrderOption, FinancialEntry, FinancialEntryPage, FinancialPeriodClosure, InvoiceType, WorkOrderReceivables,
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
type EntryMode = "single" | "installments";
type ScheduleEditor = { obligationId: number; rows: (InstallmentDraft & { entry_id?: number })[] };
type InstallmentDraft = {
  installment_number: number; due_date: string; amount: string; payment_code: string; notes: string;
};

const dateKey = (value: Date) =>
  `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, "0")}-${String(value.getDate()).padStart(2, "0")}`;
const currentDate = () => dateKey(new Date());
const currentYear = () => new Date().getFullYear();
const currentMonth = () => new Date().getMonth() + 1;
const firstDayOfMonth = (year: number, month: number) => `${year}-${String(month).padStart(2, "0")}-01`;
const lastDayOfMonth = (year: number, month: number) => dateKey(new Date(year, month, 0));
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
function initialInstallments(firstDueDate: string): InstallmentDraft[] {
  return [
    { installment_number: 1, due_date: firstDueDate, amount: "", payment_code: "", notes: "" },
    { installment_number: 2, due_date: "", amount: "", payment_code: "", notes: "" },
  ];
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


function FinancePeriodSummary({ view, summary, periodLabel }: { view: FinanceView; summary: FinanceSummary; periodLabel: string }) {
  const overdueIncome = summary.overdue_income;
  const overdueExpense = summary.overdue_expense;

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

function MonthlyBalanceOverview({ summary }: { summary: FinanceSummary }) {
  const months = summary.monthly_flow;
  const annualIncome = months.reduce((total, month) => total + month.income, 0);
  const annualExpense = months.reduce((total, month) => total + month.expense, 0);
  const annualReceived = months.reduce((total, month) => total + month.settled_income, 0);
  const annualResult = annualIncome - annualExpense;
  const activeMonths = months.filter((month) => month.income > 0 || month.expense > 0);
  const averageIncome = activeMonths.length ? annualIncome / activeMonths.length : 0;
  const realizationRate = annualIncome > 0 ? Math.min(100, (annualReceived / annualIncome) * 100) : 0;
  const bestMonth = months.reduce((best, month) => month.income > best.income ? month : best, months[0]);
  const maxMovement = Math.max(...months.flatMap((month) => [month.income, month.expense]), 1);

  return <section className="finance-annual-overview">
    <header><div><span>DESEMPENHO ANUAL</span><h2>Faturamento mês a mês</h2><p>Comparativo visual de receitas lançadas, saídas e resultado ao longo do ano selecionado.</p></div><div className="finance-annual-legend"><span className="income">Receitas</span><span className="expense">Saídas</span></div></header>
    <div className="finance-annual-kpis">
      <article><span>Faturamento no ano</span><strong className="amount-positive">{money(annualIncome)}</strong><small>{activeMonths.length} mês(es) com movimento</small></article>
      <article><span>Saídas no ano</span><strong className="amount-negative">{money(annualExpense)}</strong><small>Resultado anual {money(annualResult)}</small></article>
      <article><span>Média mensal faturada</span><strong>{money(averageIncome)}</strong><small>Média apenas dos meses com movimento</small></article>
      <article><span>Recebimento do faturado</span><strong>{realizationRate.toFixed(1).replace(".", ",")}%</strong><small>{money(annualReceived)} já recebido</small></article>
      <article className="finance-annual-highlight"><span>Melhor mês em faturamento</span><strong>{bestMonth?.label ?? "—"}</strong><small>{bestMonth ? money(bestMonth.income) : money(0)}</small></article>
    </div>
    <div className="finance-annual-chart" role="img" aria-label="Gráfico mensal de receitas e saídas">
      {months.map((month) => {
        const incomeHeight = month.income > 0 ? Math.max(4, (month.income / maxMovement) * 100) : 0;
        const expenseHeight = month.expense > 0 ? Math.max(4, (month.expense / maxMovement) * 100) : 0;
        return <article key={month.month} className="finance-annual-month">
          <div className="finance-annual-bars">
            <i className="income" style={{ height: `${incomeHeight}%` }} title={`Receitas ${month.label}: ${money(month.income)}`} />
            <i className="expense" style={{ height: `${expenseHeight}%` }} title={`Saídas ${month.label}: ${money(month.expense)}`} />
          </div>
          <strong>{month.label.split("/")[0]}</strong>
          <small className={month.result >= 0 ? "amount-positive" : "amount-negative"}>{money(month.result)}</small>
        </article>;
      })}
    </div>
  </section>;
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
  const route = useLocation();
  const [view, setView] = useState<FinanceView>("operations");
  const [company, setCompany] = useState<CompanyFilter>("universo_eletronica");
  const [year, setYear] = useState(() => currentYear());
  const [shortcut, setShortcut] = useState<string>(() => String(currentMonth()));
  const [startDate, setStartDate] = useState(() => firstDayOfMonth(currentYear(), currentMonth()));
  const [endDate, setEndDate] = useState(() => currentDate());
  const [dateBasis, setDateBasis] = useState<DateBasis>("posting");
  const [dateBounds, setDateBounds] = useState<FinanceDateBounds | null>(null);
  const [summary, setSummary] = useState<FinanceSummary | null>(null);
  const [periodClosures, setPeriodClosures] = useState<FinancialPeriodClosure[]>([]);
  const canManageFinance = ["gestao", "super_admin"].includes(user.role);
  const [entries, setEntries] = useState<FinancialEntry[]>([]); const [audit, setAudit] = useState<AuditEvent[]>([]);
  const [entryPage, setEntryPage] = useState(1);
  const [entryPagination, setEntryPagination] = useState({ total: 0, pages: 0, pageSize: 50 });
  const [search, setSearch] = useState("");
  const [serverSearch, setServerSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<EntryStatus | "overdue" | "all">("all");
  const [eventFilter, setEventFilter] = useState<FinanceStatus | "all">("all");
  const [selected, setSelected] = useState<FinancialEntry | null>(null); const [modalOpen, setModalOpen] = useState(false);
  const [form, setForm] = useState<EntryForm>(initialForm("universo_eletronica", "income"));
  const [entryMode, setEntryMode] = useState<EntryMode>("single");
  const [installments, setInstallments] = useState<InstallmentDraft[]>(() => initialInstallments(currentDate()));
  const [scheduleEditor, setScheduleEditor] = useState<ScheduleEditor | null>(null);
  const [attachment, setAttachment] = useState<File | null>(null); const [saving, setSaving] = useState(false);
  const [createRequestKey, setCreateRequestKey] = useState(() => crypto.randomUUID());
  const [previewOpen, setPreviewOpen] = useState(false);
  const [workOrders, setWorkOrders] = useState<FinanceWorkOrderOption[]>([]);
  const [workOrderSearch, setWorkOrderSearch] = useState("");
  const [billingReadiness, setBillingReadiness] = useState<BillingReadiness | null>(null);
  const [billingConfirmation, setBillingConfirmation] = useState<BillingConfirmation>(emptyBillingConfirmation());
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const requestSequence = useRef(0);
  const [linkedReceivables, setLinkedReceivables] = useState<WorkOrderReceivables | null>(null);
  const [linkedReceivablesLoading, setLinkedReceivablesLoading] = useState(false);
  const [linkedReceivablesRevision, setLinkedReceivablesRevision] = useState(0);
  const openedDeepLink = useRef("");
  const linkedWorkOrderId = Number(new URLSearchParams(route.search).get("os")) || 0;
  function refreshLinkedReceivables() {
    if (linkedWorkOrderId > 0) setLinkedReceivablesRevision((value) => value + 1);
  }

  useEffect(() => {
    if (linkedWorkOrderId <= 0) { setLinkedReceivables(null); setLinkedReceivablesLoading(false); return; }
    let active = true;
    setLinkedReceivablesLoading(true);
    setLinkedReceivables(null);
    setView("income");
    apiClient.get<WorkOrderReceivables>(`/finance/work-orders/${linkedWorkOrderId}/receivables`)
      .then((data) => { if (active) { setLinkedReceivables(data); setCompany(data.company_code); } })
      .catch((reason: Error) => { if (active) { setLinkedReceivables(null); setError(`Não foi possível carregar as receitas da OS: ${reason.message}`); } })
      .finally(() => { if (active) setLinkedReceivablesLoading(false); });
    return () => { active = false; };
  }, [linkedWorkOrderId, linkedReceivablesRevision]);

  useEffect(() => {
    const params = new URLSearchParams(route.search);
    const entryId = Number(params.get("lancamento"));
    if (linkedWorkOrderId <= 0 || !Number.isSafeInteger(entryId) || entryId <= 0 || openedDeepLink.current === route.search) return;
    openedDeepLink.current = route.search;
    apiClient.get<WorkOrderReceivables>(`/finance/work-orders/${linkedWorkOrderId}/receivables`)
      .then((group) => {
        if (group.installments.some((entry) => entry.id === entryId)) return openEntry(entryId);
        setError("Esta receita não pertence à OS informada.");
      })
      .catch((reason: Error) => setError(`Não foi possível localizar a parcela: ${reason.message}`));
  }, [route.search, linkedWorkOrderId]);

  function openNewForWorkOrder(group: WorkOrderReceivables) {
    if (group.remaining_to_issue !== null && Number(group.remaining_to_issue) < 0.01) {
      setError("O valor aprovado desta OS já foi integralmente lançado. Verifique as parcelas existentes.");
      return;
    }
    openNew("income");
    const base = initialForm(group.company_code, "income");
    setForm({
      ...base,
      work_order_id: String(group.work_order_id),
      counterparty_name: group.customer_name,
      description: `Serviço de laboratório — ${group.work_order_number}`,
      amount: group.remaining_to_issue != null && Number(group.remaining_to_issue) > 0
        ? Number(group.remaining_to_issue).toFixed(2).replace(".", ",") : "",
    });
    setWorkOrderSearch(`${group.work_order_number} · ${group.customer_name}`);
  }

  function distributeInstallments() {
    try {
      const amounts = splitInstallmentAmounts(parseAmount(form.amount), installments.length);
      setInstallments((current) => current.map((item, index) => ({ ...item, amount: amounts[index] })));
      setError("");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Não foi possível dividir o valor."); }
  }
  function suggestInstallmentDates() {
    try {
      const dates = monthlyInstallmentDates(installments[0]?.due_date || form.due_date, installments.length);
      setInstallments((current) => current.map((item, index) => ({ ...item, due_date: dates[index] })));
      setError("");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Vencimento inválido."); }
  }

  // A associação usa o ID da OS salvo no lançamento, nunca nome/descrição,
  // evitando abrir o orçamento de outro equipamento com dados semelhantes.
  function openLinkedWorkOrder(workOrderId: number, tab: "quote" | "financial") {
    setModalOpen(false);
    navigate(`/laboratorio?os=${workOrderId}&aba=${tab}`);
  }

  const selectedCompany = company === "consolidated" ? "universo_eletronica" : company;
  const availableBanks = companies.find((item) => item.code === form.company_code)?.banks ?? [];
  const closurePeriod = startDate && endDate && startDate.slice(0, 7) === endDate.slice(0, 7)
    ? { year: Number(startDate.slice(0, 4)), month: Number(startDate.slice(5, 7)) }
    : null;
  const years = Array.from(
    { length: Math.max(1, currentYear() - 2024 + 1) },
    (_, index) => 2024 + index,
  ).reverse();

  async function loadData() {
    const requestId = ++requestSequence.current;
    if (!startDate || !endDate) return;
    if (endDate < startDate) {
      setSummary(null); setEntries([]); setEntryPagination({ total: 0, pages: 0, pageSize: 50 }); setError("A data final não pode ser anterior à data inicial.");
      return;
    }
    setLoading(true); setError("");
    const scope = queryScope(company, startDate, endDate, dateBasis);
    const isLedger = view === "income" || view === "expense";
    const entryQuery = `${scope}&entry_type=${view === "income" ? "income" : "expense"}${statusFilter !== "all" && statusFilter !== "overdue" ? `&status=${statusFilter}` : ""}${statusFilter === "overdue" ? "&overdue=true" : ""}${serverSearch ? `&search=${encodeURIComponent(serverSearch)}` : ""}&page=${entryPage}&page_size=50`;
    try {
      const [nextSummary, nextEntries] = await Promise.all([
        apiClient.request<FinanceSummary>(`/api/finance/summary?${scope}`),
        isLedger
          ? apiClient.request<FinancialEntryPage>(`/api/finance/entries?${entryQuery}`)
          : Promise.resolve<FinancialEntryPage>({ items: [], page: 1, page_size: 50, total: 0, pages: 0 }),
      ]);
      if (requestId !== requestSequence.current) return;
      setSummary(nextSummary);
      setEntries(nextEntries.items);
      setEntryPagination({ total: nextEntries.total, pages: nextEntries.pages, pageSize: nextEntries.page_size });
      if (isLedger && nextEntries.page !== entryPage) setEntryPage(nextEntries.page);
      if (view === "audit") setAudit(await apiClient.request<AuditEvent[]>(`/api/finance/audit?start_date=${startDate}&end_date=${endDate}`));
    } catch (reason) {
      if (requestId !== requestSequence.current) return;
      setSummary(null); setEntries([]); setEntryPagination({ total: 0, pages: 0, pageSize: 50 });
      setError(reason instanceof Error ? reason.message : "Não foi possível concluir a operação.");
    } finally {
      if (requestId === requestSequence.current) setLoading(false);
    }
  }
  useEffect(() => { void loadData(); }, [company, startDate, endDate, dateBasis, view, statusFilter, serverSearch, entryPage]);
  useEffect(() => { setEntryPage(1); }, [company, startDate, endDate, dateBasis, view, statusFilter]);
  useEffect(() => {
    const term = search.trim();
    // Ao apagar a pesquisa, remove o filtro do servidor imediatamente. Isso
    // evita manter em memória somente o subconjunto retornado pela busca anterior.
    if (term.length < 2) { setServerSearch(""); setEntryPage(1); return; }
    const timer = window.setTimeout(() => { setServerSearch(term); setEntryPage(1); }, 250);
    return () => window.clearTimeout(timer);
  }, [search]);
  useEffect(() => { if (!error) return; const timer = window.setTimeout(() => setError(""), 6500); return () => window.clearTimeout(timer); }, [error]);

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
  const visibleEntries = entries;

  function downloadFinanceReport(format: "pdf" | "xlsx") {
    if (!startDate || !endDate) return;
    const scope = queryScope(company, startDate, endDate, dateBasis);
    const link = document.createElement("a");
    link.href = `/api/finance/reports/${format}?${scope}`;
    link.rel = "noopener";
    document.body.appendChild(link);
    link.click();
    link.remove();
  }

  function openNew(type: EntryType) {
    const nextForm = initialForm(selectedCompany, type);
    setSelected(null); setScheduleEditor(null); setCreateRequestKey(crypto.randomUUID()); setForm(nextForm); setEntryMode("single");
    setInstallments(initialInstallments(nextForm.due_date)); setWorkOrderSearch(""); setWorkOrders([]);
    setBillingConfirmation(emptyBillingConfirmation()); setBillingReadiness(null); setAttachment(null); setModalOpen(true);
  }
  async function openEntry(id: number) { const entry = await apiClient.request<FinancialEntry>(`/api/finance/entries/${id}`); setSelected(entry); setForm({
    entry_type: entry.entry_type, company_code: entry.company_code, invoice_type: entry.invoice_type ?? "",
    series: entry.series ?? "", nfse_number: entry.nfse_number ?? "", nfe_number: entry.nfe_number ?? "", counterparty_name: entry.counterparty_name, description: entry.description,
    amount: String(entry.amount).replace(".", ","), issue_date: entry.issue_date, posting_date: entry.posting_date,
    due_date: entry.due_date, bank_name: entry.bank_name, expense_kind: entry.expense_kind ?? "fixed",
    document_number: entry.document_number ?? "", payment_code: entry.payment_code ?? "", notes: entry.notes ?? "", work_order_id: entry.work_order_id ? String(entry.work_order_id) : "",
  });
    const stored = (entry.billing_compliance?.confirmation ?? {}) as Partial<BillingConfirmation>;
    setBillingConfirmation({ ...emptyBillingConfirmation(), ...stored });
    setEntryMode("single"); setScheduleEditor(null); setInstallments(initialInstallments(entry.due_date));
    setWorkOrderSearch(""); setWorkOrders([]); setAttachment(null); setModalOpen(true); }

  async function openScheduleEditor() {
    if (!selected?.obligation_id || selected.entry_type !== "income") return;
    setSaving(true); setError("");
    try {
      const group = await apiClient.get<{ id: number; installments: FinancialEntry[] }>(`/api/finance/obligations/${selected.obligation_id}`);
      if (group.installments.some((item) => item.status !== "pending" || item.settlement_date)) {
        throw new Error("Há parcelas baixadas. Estorne as baixas autorizadas antes de alterar o parcelamento.");
      }
      setScheduleEditor({ obligationId: group.id, rows: group.installments.map((item, index) => ({
        installment_number: index + 1, entry_id: item.id, due_date: item.due_date,
        amount: String(item.amount).replace(".", ","), payment_code: item.payment_code ?? "", notes: item.notes ?? "",
      })) });
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Não foi possível abrir o parcelamento.");
    } finally { setSaving(false); }
  }

  async function saveScheduleEditor() {
    if (!scheduleEditor) return;
    try {
      const rows = scheduleEditor.rows.map((row, index) => {
        const amount = parseAmount(row.amount);
        if (!row.due_date || !Number.isFinite(amount) || amount <= 0) throw new Error(`Confira a data e o valor da parcela ${index + 1}.`);
        return { installment_number: index + 1, entry_id: row.entry_id ?? null, due_date: row.due_date, amount, payment_code: row.payment_code || null, notes: row.notes || null };
      });
      if (!rows.length) throw new Error("O parcelamento deve ter pelo menos uma parcela. Para excluir tudo, use Excluir parcelamento.");
      const total = Number(rows.reduce((sum, row) => sum + row.amount, 0).toFixed(2));
      if (!window.confirm(`Confirmar novo parcelamento de ${rows.length} parcela(s), total ${money(total)}?`)) return;
      setSaving(true); setError("");
      await apiClient.request(`/api/finance/obligations/${scheduleEditor.obligationId}/schedule`, {
        method: "PUT", body: JSON.stringify({ total_amount: total, installments: rows }),
      });
      setScheduleEditor(null); setModalOpen(false); setSelected(null); await loadData(); refreshLinkedReceivables();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Falha ao alterar parcelas.");
    } finally { setSaving(false); }
  }

  async function deleteScheduleEditor() {
    if (!scheduleEditor) return;
    if (!window.confirm("Excluir TODAS as parcelas desta receita? A exclusão será auditada e não será possível recuperar pelo painel.")) return;
    setSaving(true); setError("");
    try {
      await apiClient.request(`/api/finance/obligations/${scheduleEditor.obligationId}`, { method: "DELETE" });
      setScheduleEditor(null); setModalOpen(false); setSelected(null); await loadData(); refreshLinkedReceivables();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Falha ao excluir parcelamento.");
    } finally { setSaving(false); }
  }

  function resizeInstallments(count: number) {
    const safeCount = Math.max(2, Math.min(60, Number.isFinite(count) ? Math.trunc(count) : 2));
    setInstallments((current) => Array.from({ length: safeCount }, (_, index) => current[index] ?? {
      installment_number: index + 1, due_date: "", amount: "", payment_code: "", notes: "",
    }).map((item, index) => ({ ...item, installment_number: index + 1 })));
  }

  function updateInstallment(index: number, patch: Partial<InstallmentDraft>) {
    setInstallments((current) => current.map((item, itemIndex) => itemIndex === index ? { ...item, ...patch } : item));
  }


  async function loadClosures(companyCode: CompanyCode, selectedYear: number) {
    const data = await apiClient.get<FinancialPeriodClosure[]>(`/api/finance/closures?company_code=${companyCode}&year=${selectedYear}`);
    setPeriodClosures(data);
  }

  useEffect(() => {
    if (!canManageFinance || company === "consolidated" || !closurePeriod) {
      setPeriodClosures([]);
      return;
    }
    void loadClosures(company, closurePeriod.year);
  }, [canManageFinance, company, closurePeriod?.year, closurePeriod?.month]);



  async function togglePeriodClosure() {
    if (company === "consolidated") {
      setError("Selecione uma empresa para fechar ou reabrir competência.");
      return;
    }
    if (!closurePeriod) {
      setError("Para fechar ou reabrir uma competência, filtre um único mês.");
      return;
    }
    const current = periodClosures.find(
      (item) => item.year === closurePeriod.year && item.month === closurePeriod.month,
    );
    const endpoint = current?.is_closed ? "/api/finance/closures/reopen" : "/api/finance/closures/close";
    await apiClient.post(endpoint, {
      company_code: company,
      year: closurePeriod.year,
      month: closurePeriod.month,
    });
    await loadClosures(company, closurePeriod.year);
    await loadData();
  }

  async function acknowledgeAlert(entryId: number) {
    await apiClient.post(`/api/finance/alerts/${entryId}/acknowledge`, {});
    await loadData();
  }

  async function saveEntry(event: React.FormEvent) {
    event.preventDefault(); setSaving(true); setError("");
    try {
      const invoiceType = form.nfse_number.trim() && !form.nfe_number.trim()
        ? "nfse"
        : form.nfe_number.trim() && !form.nfse_number.trim()
          ? "nfe"
          : null;
      const totalAmount = parseAmount(form.amount);
      if (!Number.isFinite(totalAmount) || totalAmount <= 0) throw new Error("Informe um valor válido maior que zero.");

      if (!selected && entryMode === "installments") {
        if (installments.length < 2) throw new Error("Informe pelo menos duas parcelas.");
        const normalizedInstallments = installments.map((item, index) => {
          const amount = parseAmount(item.amount);
          if (!item.due_date) throw new Error(`Informe o vencimento da parcela ${index + 1}.`);
          if (!Number.isFinite(amount) || amount <= 0) throw new Error(`Informe um valor válido para a parcela ${index + 1}.`);
          return {
            installment_number: index + 1,
            due_date: item.due_date,
            amount,
            payment_code: item.payment_code.trim() || null,
            notes: item.notes.trim() || null,
          };
        });
        const installmentTotal = normalizedInstallments.reduce((sum, item) => sum + item.amount, 0);
        if (Math.abs(installmentTotal - totalAmount) > 0.009) {
          throw new Error(`A soma das parcelas (${money(installmentTotal)}) deve ser igual ao valor total (${money(totalAmount)}).`);
        }
        if (attachment) throw new Error("No lançamento parcelado, salve primeiro e anexe documentos individualmente em cada parcela quando necessário.");

        const obligationBody = JSON.stringify({
          entry_type: form.entry_type,
          company_code: form.company_code,
          invoice_type: form.entry_type === "income" ? invoiceType : null,
          series: form.series || null,
          nfse_number: form.entry_type === "income" ? form.nfse_number.trim() || null : null,
          nfe_number: form.entry_type === "income" ? form.nfe_number.trim() || null : null,
          counterparty_name: form.counterparty_name,
          description: form.description,
          total_amount: totalAmount,
          issue_date: form.issue_date,
          posting_date: form.issue_date,
          bank_name: form.bank_name,
          expense_kind: form.entry_type === "expense" ? form.expense_kind : null,
          account_id: null,
          category_id: null,
          document_number: form.entry_type === "expense" ? form.document_number || null : null,
          notes: form.notes || null,
          work_order_id: form.entry_type === "income" && form.work_order_id ? Number(form.work_order_id) : null,
          billing_confirmation: form.entry_type === "income" && form.work_order_id ? billingConfirmation : null,
          installments: normalizedInstallments,
        });
        await apiClient.request("/api/finance/obligations", {
          method: "POST",
          headers: { "Content-Type": "application/json", "Idempotency-Key": createRequestKey },
          body: obligationBody,
        });
        setModalOpen(false); await loadData(); refreshLinkedReceivables();
        return;
      }

      const body = JSON.stringify({
        ...form,
        // O Financeiro usa a emissão como competência operacional.
        // posting_date permanece no contrato da API por compatibilidade histórica,
        // mas não é mais um campo manual na interface.
        posting_date: form.issue_date,
        amount: totalAmount,
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
      setModalOpen(false); await loadData(); refreshLinkedReceivables();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Falha ao salvar."); }
    finally { setSaving(false); }
  }
  async function removeEntry() {
    if (!selected || !confirm("Excluir este lançamento? A ação ficará registrada na auditoria.")) return;
    await apiClient.request(`/api/finance/entries/${selected.id}`, { method: "DELETE" }); setModalOpen(false); await loadData(); refreshLinkedReceivables();
  }
  async function toggleSettlement() {
    if (!selected) return;
    if (selected.status === "pending") {
      const settlementDate = prompt("Data da baixa (AAAA-MM-DD):", currentDate()); if (!settlementDate) return;
      await apiClient.request(`/api/finance/entries/${selected.id}/settle`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ settlement_date: settlementDate }) });
    } else await apiClient.request(`/api/finance/entries/${selected.id}/unsettle`, { method: "POST" });
    const refreshed = await apiClient.request<FinancialEntry>(`/api/finance/entries/${selected.id}`); setSelected(refreshed); await loadData(); refreshLinkedReceivables();
  }

  function applyShortcut(nextShortcut: string, nextYear = year) {
    setShortcut(nextShortcut); setYear(nextYear);
    if (nextShortcut === "custom") return;
    if (nextShortcut === "year") {
      setStartDate(`${nextYear}-01-01`);
      setEndDate(nextYear === currentYear() ? currentDate() : `${nextYear}-12-31`);
      return;
    }
    const nextMonth = Number(nextShortcut);
    setStartDate(firstDayOfMonth(nextYear, nextMonth));
    const monthEnd = lastDayOfMonth(nextYear, nextMonth);
    setEndDate(nextYear === currentYear() && nextMonth === currentMonth() && monthEnd > currentDate() ? currentDate() : monthEnd);
  }
  function changeYear(nextYear: number) {
    setYear(nextYear);
    if (shortcut !== "custom") applyShortcut(shortcut, nextYear);
  }
  function manualStart(value: string) { setStartDate(value); setShortcut("custom"); }
  function manualEnd(value: string) { setEndDate(value); setShortcut("custom"); }

  const periodLabel = summary ? `${dateBR(summary.period_start)} até ${dateBR(summary.period_end)}` : `${dateBR(startDate)} até ${dateBR(endDate)}`;
  const title = views.find(([key]) => key === view)?.[1] ?? "Financeiro";
  return <div className="finance-shell sentico-shell">
    <SenticoSidebar
      user={user}
      onLogout={onLogout}
      sectionLabel="Financeiro"
      sectionItems={views.map(([key, label, icon]) => ({
        id: key, label, icon, active: view === key,
        onClick: () => setView(key),
      }))}
    />
    <main className="finance-main sentico-content">
      <header className="finance-header">
        <div className="finance-heading"><span>GESTÃO FINANCEIRA</span><h1>{title}</h1><p>Receitas e saídas separadas, visão por competência, baixas e auditoria completa.</p></div>
        <div className="finance-header__tools"><button className="finance-primary income" onClick={() => linkedReceivables ? openNewForWorkOrder(linkedReceivables) : openNew("income")}><ArrowUpRight size={18}/>Nova receita</button><button className="finance-primary expense" onClick={() => openNew("expense")}><ArrowDownRight size={18}/>Nova saída</button></div>
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

      {summary && !loading && <FinancePeriodSummary view={view} summary={summary} periodLabel={periodLabel} />}
      {linkedWorkOrderId > 0 && <section className="finance-linked-order">
        {linkedReceivablesLoading && <p>Consultando todas as receitas e parcelas desta OS…</p>}
        {linkedReceivables && <>
          <header><div><span>RECEITAS DA ORDEM DE SERVIÇO</span><h2>{linkedReceivables.work_order_number} · {linkedReceivables.customer_name}</h2><p>Vínculo pelo ID da OS. Parcelas de qualquer competência são exibidas aqui, inclusive as já recebidas.</p></div><button type="button" className="finance-linked-back" onClick={() => navigate(`/laboratorio?os=${linkedReceivables.work_order_id}&aba=financial`)}>Voltar para OS</button></header>
          <div className="finance-linked-totals">
            <article><small>Valor aprovado</small><strong>{linkedReceivables.approved_value == null ? "Não informado" : money(Number(linkedReceivables.approved_value))}</strong></article>
            <article><small>Receitas lançadas</small><strong>{money(Number(linkedReceivables.total_registered))}</strong></article>
            <article><small>Já recebido</small><strong>{money(Number(linkedReceivables.total_received))}</strong></article>
            <article><small>A receber</small><strong>{money(Number(linkedReceivables.total_pending))}</strong></article>
            <article><small>Ainda não lançado</small><strong>{linkedReceivables.remaining_to_issue == null ? "Sem referência" : money(Number(linkedReceivables.remaining_to_issue))}</strong></article>
          </div>
          <div className="finance-linked-list">
            {linkedReceivables.installments.map((item) => <button type="button" key={item.id} onClick={() => void openEntry(item.id)}>
              <span><b>{item.obligation_id ? `Parcela ${item.installment_number}` : "Receita avulsa"}</b><small>Vence {dateBR(item.due_date)} · {item.bank_name}</small></span>
              <strong>{money(item.amount)}</strong><em className={item.status === "received" ? "received" : "pending"}>{item.status === "received" ? `Recebido ${dateBR(item.settlement_date)}` : "Pendente"}</em><Eye size={16}/>
            </button>)}
            {!linkedReceivables.installments.length && <p>Nenhuma receita vinculada a esta OS. Cadastre a primeira receita abaixo.</p>}
          </div>
          {linkedReceivables.remaining_to_issue !== null && Number(linkedReceivables.remaining_to_issue) < -0.005 && <p className="finance-linked-warning">O total lançado supera o valor aprovado. Confira os lançamentos antes de registrar novos pagamentos.</p>}
          <div className="finance-linked-actions">
            <button type="button" className="finance-primary income" disabled={linkedReceivables.remaining_to_issue !== null && Number(linkedReceivables.remaining_to_issue) < .01} onClick={() => openNewForWorkOrder(linkedReceivables)}><Plus size={17}/> {linkedReceivables.installments.length ? "Cadastrar saldo restante" : "Cadastrar receita da OS"}</button>
            <small>Uma OS pode ter várias parcelas; cada parcela tem vencimento, baixa e comprovante próprios. Confira o total antes de registrar outra receita.</small>
          </div>
        </>}
      </section>}

      {view === "operations" && summary && <>
        <section className="finance-deadline-radar">
          <header>
            <div><span>ALERTAS FINANCEIROS</span><h2>Vencidos e próximos a vencer</h2><p>Radar independente do filtro de competência. O aviso permanece enquanto o título estiver pendente.</p></div>
            <div className="finance-deadline-counts">
              <b>{summary.urgent_events.filter((event) => event.status === "overdue").length} vencido(s)</b>
              <b>{summary.urgent_events.filter((event) => event.status === "due_soon").length} próximo(s)</b>
            </div>
          </header>
          <div className="finance-deadline-grid">
            <div>
              <h3>Vencidos</h3>
              {summary.urgent_events.filter((event) => event.status === "overdue").slice(0, 8).map((event) => <article key={event.id} className="finance-deadline-item overdue">
                <button type="button" className="finance-deadline-main" onClick={() => openEntry(event.id)}><span><strong>{event.counterparty_name || event.description}</strong><small>{event.description} · {event.due_label}</small></span><b>{money(event.amount)}</b></button>
                <button type="button" className="finance-ack-button" onClick={() => void acknowledgeAlert(event.id)}>Reconhecer</button>
              </article>)}
              {!summary.urgent_events.some((event) => event.status === "overdue") && <p className="finance-empty">Nenhum título vencido.</p>}
            </div>
            <div>
              <h3>Próximos 7 dias</h3>
              {summary.urgent_events.filter((event) => event.status === "due_soon").slice(0, 8).map((event) => <article key={event.id} className="finance-deadline-item due-soon">
                <button type="button" className="finance-deadline-main" onClick={() => openEntry(event.id)}><span><strong>{event.counterparty_name || event.description}</strong><small>{event.description} · {event.due_label}</small></span><b>{money(event.amount)}</b></button>
                <button type="button" className="finance-ack-button" onClick={() => void acknowledgeAlert(event.id)}>Reconhecer</button>
              </article>)}
              {!summary.urgent_events.some((event) => event.status === "due_soon") && <p className="finance-empty">Nenhum título vencendo nos próximos 7 dias.</p>}
            </div>
          </div>
        </section>
        {canManageFinance && company !== "consolidated" && <section className="finance-governance-card"><header><div><span>GOVERNANÇA FINANCEIRA</span><h2>Fechamento de competência</h2><p>O fechamento grava um retrato dos totais e bloqueia criação, edição, exclusão, baixa e estorno até a reabertura.</p></div>{closurePeriod ? <div className={periodClosures.find((item) => item.year === closurePeriod.year && item.month === closurePeriod.month)?.is_closed ? "finance-period-state closed" : "finance-period-state open"}>{periodClosures.find((item) => item.year === closurePeriod.year && item.month === closurePeriod.month)?.is_closed ? "Competência fechada" : "Competência aberta"}</div> : <div className="finance-period-state open">Selecione um único mês</div>}</header><div className="finance-governance-grid finance-governance-grid--single"><div><h3>{closurePeriod ? `${months[closurePeriod.month - 1]} / ${closurePeriod.year}` : "Período personalizado"}</h3><p>{closurePeriod ? "Feche a competência após concluir as conferências. A reabertura fica restrita ao perfil Gestão." : "Use um filtro que comece e termine no mesmo mês para habilitar o fechamento."}</p><button type="button" className="finance-close-period" disabled={!closurePeriod} onClick={() => void togglePeriodClosure()}>{closurePeriod && periodClosures.find((item) => item.year === closurePeriod.year && item.month === closurePeriod.month)?.is_closed ? "Reabrir competência" : "Fechar competência"}</button></div></div></section>}
        <CashFlowChart points={summary.cash_flow} />
        <section className="finance-section-head"><div><span>RADAR FINANCEIRO</span><h2>Movimentações de {periodLabel}</h2><p>Filtro aplicado pela data de {dateBasisLabels[dateBasis].toLowerCase()}.</p></div>
          <div className="status-filter">{(["all", "overdue", "due_soon", "settled"] as const).map((item) => <button key={item} className={eventFilter === item ? "active" : ""} onClick={() => setEventFilter(item)}>{item === "all" ? "Todos" : statusMeta[item].label}</button>)}</div></section>
        <section className="event-columns"><div className="event-column income-column"><header><div><ArrowUpRight/><span>Receitas</span></div><strong>{money(summary.period_income)}</strong></header><div className="finance-events">{filteredEvents(summary.income_events).map((event) => <EventCard key={event.id} event={event} onOpen={openEntry}/>) || null}{!filteredEvents(summary.income_events).length && <p className="finance-empty">Nenhuma receita no período.</p>}</div></div>
          <div className="event-column expense-column"><header><div><ArrowDownRight/><span>Saídas</span></div><strong>{money(summary.period_expense)}</strong></header><div className="finance-events">{filteredEvents(summary.expense_events).map((event) => <EventCard key={event.id} event={event} onOpen={openEntry}/>) || null}{!filteredEvents(summary.expense_events).length && <p className="finance-empty">Nenhuma saída no período.</p>}</div></div></section>
      </>}

      {(view === "income" || view === "expense") && <section className="ledger-panel"><header><div><span>{view === "income" ? "CONTAS A RECEBER" : "CONTAS A PAGAR"}</span><h2>{view === "income" ? "Receitas" : "Saídas"} do período</h2></div><div className="ledger-tools"><label><Search size={16}/><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Buscar cliente, OS, série, NFS-e ou NF-e"/></label><select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value as EntryStatus | "overdue" | "all")}><option value="all">Todos os status</option><option value="pending">Pendente</option><option value="overdue">Atrasado</option><option value={view === "income" ? "received" : "paid"}>Baixado</option></select></div></header>
        <div className="ledger-list ledger-list--detailed"><div className="ledger-row ledger-row--detailed ledger-head"><span>Banco</span><span>Cliente / favorecido</span><span>Série</span><span>NFS-e</span><span>NF-e</span><span>Emissão</span><span>Vencimento</span><span>Valor</span><span>Status</span><span>Ações</span></div>{visibleEntries.map((entry) => { const overdue = entry.status === "pending" && new Date(`${entry.due_date}T00:00:00`) < new Date(new Date().setHours(0, 0, 0, 0)); return <div className="ledger-row ledger-row--detailed" key={entry.id} onClick={(event) => { if (!(event.target as HTMLElement).closest("button, a")) void openEntry(entry.id); }}><span><strong>{entry.bank_name}</strong><small>{companyName(entry.company_code)}</small></span><span><strong>{entry.counterparty_name}</strong><small>{entry.description}{entry.obligation_id ? ` · Parcela ${entry.installment_number ?? "—"}` : ""}</small></span><span>{entry.series || "—"}</span><span>{entry.nfse_number || "—"}</span><span>{entry.nfe_number || "—"}</span><span>{dateBR(entry.issue_date)}</span><span className={overdue ? "date-overdue" : ""}>{dateBR(entry.due_date)}</span><span className={entry.entry_type === "income" ? "amount-positive" : "amount-negative"}>{money(entry.amount)}</span><span><i className={`status-pill ${overdue ? "overdue" : entry.status}`}>{overdue ? "Atrasado" : entry.status === "pending" ? "Pendente" : "Baixado"}</i></span><span className="finance-ledger-actions"><button type="button" className="finance-ledger-detail" onClick={() => void openEntry(entry.id)} title="Abrir detalhes da receita" aria-label={`Abrir detalhes do lançamento ${entry.id}`}><ChevronRight size={17}/></button>{entry.entry_type === "income" && entry.work_order_id ? <button type="button" className="finance-ledger-os" onClick={() => openLinkedWorkOrder(entry.work_order_id!, "financial")} title="Ver orçamento e valor aprovado na OS correspondente"><FileSearch size={15}/> Ver OS</button> : null}</span></div>})}{!visibleEntries.length && <p className="finance-empty">Nenhum lançamento encontrado.</p>}</div><footer className="finance-pagination"><span>{entryPagination.total ? `${(entryPage - 1) * entryPagination.pageSize + 1}–${Math.min(entryPage * entryPagination.pageSize, entryPagination.total)} de ${entryPagination.total} lançamentos` : "0 lançamentos"}</span><div><button type="button" disabled={entryPage <= 1 || loading} onClick={() => setEntryPage((current) => Math.max(1, current - 1))}><ChevronLeft size={16}/>Anterior</button><strong>Página {entryPagination.pages ? entryPage : 0} de {entryPagination.pages}</strong><button type="button" disabled={entryPagination.pages === 0 || entryPage >= entryPagination.pages || loading} onClick={() => setEntryPage((current) => current + 1)}>Próxima<ChevronRight size={16}/></button></div></footer></section>}

      {view === "forecast" && summary && <>
        <section className="finance-executive-grid">
          <article><span>Saldo atual</span><strong>{money(summary.current_balance)}</strong><small>Saldo inicial das contas + baixas realizadas</small></article>
          <article><span>A receber em aberto</span><strong className="amount-positive">{money(summary.pending_income)}</strong><small>No período filtrado</small></article>
          <article><span>A pagar em aberto</span><strong className="amount-negative">{money(summary.pending_expense)}</strong><small>No período filtrado</small></article>
          <article className={summary.projected_balance >= 0 ? "is-positive" : "is-negative"}><span>Saldo projetado global</span><strong>{money(summary.projected_balance)}</strong><small>Saldo atual + todas as pendências conhecidas</small></article>
        </section>
        <section className="ledger-panel finance-forecast-13w">
          <header><div><span>FLUXO DE CAIXA · 13 SEMANAS</span><h2>Projeção semanal acumulada</h2><p>Parte do saldo atual, carrega vencidos na primeira semana e considera títulos pendentes por vencimento.</p></div></header>
          <div className="forecast-week-list">
            <div className="forecast-week-row forecast-week-head"><span>Semana</span><span>Saldo inicial</span><span>Entradas</span><span>Saídas</span><span>Vencidos carregados</span><span>Resultado</span><span>Saldo final</span></div>
            {summary.weekly_forecast_13w.map((week) => <article key={week.week_number} className="forecast-week-row">
              <span><b>S{String(week.week_number).padStart(2, "0")}</b><small>{dateBR(week.start_date)}–{dateBR(week.end_date)}</small></span>
              <span>{money(week.opening_balance)}</span>
              <span className="amount-positive">{money(week.income)}</span>
              <span className="amount-negative">{money(week.expense)}</span>
              <span>{week.overdue_income || week.overdue_expense ? <><small>+ {money(week.overdue_income)}</small><small>− {money(week.overdue_expense)}</small></> : "—"}</span>
              <span className={week.net >= 0 ? "amount-positive" : "amount-negative"}>{money(week.net)}</span>
              <span className={week.closing_balance >= 0 ? "amount-positive" : "amount-negative"}><b>{money(week.closing_balance)}</b><small>{week.entry_count} título(s)</small></span>
            </article>)}
          </div>
        </section>
        <section className="ledger-panel finance-aging">
          <header><div><span>AGING</span><h2>Vencidos e próximos vencimentos</h2><p>Faixas calculadas sobre todos os títulos pendentes da empresa selecionada.</p></div></header>
          <div className="finance-aging-grid">
            {summary.aging.map((bucket) => <article key={bucket.key}><span>{bucket.label}</span><strong>{bucket.count} título(s)</strong><small className="amount-positive">A receber {money(bucket.income)}</small><small className="amount-negative">A pagar {money(bucket.expense)}</small></article>)}
          </div>
        </section>
        <section className="ledger-panel finance-forecast-direct">
          <header><div><span>PREVISÃO POR VENCIMENTO</span><h2>Datas previstas de entrada e saída</h2><p>Valores pendentes agrupados exatamente pelo dia de vencimento dentro do período selecionado.</p></div></header>
          <div className="forecast-direct-list">
            {summary.forecast_flow.map((point) => <article key={point.date} className="forecast-direct-day forecast-direct-day--detailed">
              <strong>{dateBR(point.date)}</strong>
              <div className="forecast-direct-items">
                {point.items.map((item) => <button type="button" key={item.id} onClick={() => openEntry(item.id)} className={item.entry_type === "income" ? "forecast-direct-income" : "forecast-direct-expense"}>
                  <span><b>{item.counterparty_name}</b><small>{item.description}</small></span>
                  <strong>{money(item.amount)} {item.entry_type === "income" ? "a receber" : "a pagar"}</strong>
                </button>)}
              </div>
              <small className="forecast-direct-total">Total do dia: <b className={point.net >= 0 ? "amount-positive" : "amount-negative"}>{money(point.net)}</b></small>
            </article>)}
            {!summary.forecast_flow.length && <p className="finance-empty">Nenhum valor pendente com vencimento no período selecionado.</p>}
          </div>
        </section>
        <CashFlowChart
          points={summary.weekly_forecast_13w.map((week) => ({ label: `S${week.week_number}`, income: week.income + week.overdue_income, expense: week.expense + week.overdue_expense, balance: week.closing_balance }))}
          title="Saldo projetado em 13 semanas"
          subtitle="Entradas, saídas e saldo acumulado por semana."
        />
      </>}
      {view === "transfers" && <section className="finance-placeholder"><ArrowLeftRight size={42}/><h2>Remanejamentos</h2><p>Estrutura preservada para transferências entre contas. A próxima etapa liga contas bancárias por empresa e conciliação.</p></section>}
      {view === "balance" && summary && <section className="balance-lab">
        <article className="balance-hero"><div><span>BALANÇO FINANCEIRO</span><h2>{company === "consolidated" ? "Grupo consolidado" : companyName(company)}</h2><p>{periodLabel} · base {dateBasisLabels[dateBasis].toLowerCase()}</p></div><div className="balance-hero-actions"><CircleDollarSign size={50}/><div><button type="button" onClick={() => downloadFinanceReport("pdf")}><Download size={16}/>Relatório PDF</button><button type="button" onClick={() => downloadFinanceReport("xlsx")}><Download size={16}/>Excel</button></div></div></article>
        <div className="balance-cards balance-cards--executive">
          <article><span>Saldo atual</span><strong className={summary.current_balance >= 0 ? "amount-positive" : "amount-negative"}>{money(summary.current_balance)}</strong><small>Saldo inicial + receitas recebidas − despesas pagas</small></article>
          <article><span>Realizado no período</span><strong>{money(summary.settled_income - summary.settled_expense)}</strong><small>{money(summary.settled_income)} recebido · {money(summary.settled_expense)} pago</small></article>
          <article><span>Em aberto no período</span><strong>{money(summary.pending_income - summary.pending_expense)}</strong><small>{money(summary.pending_income)} a receber · {money(summary.pending_expense)} a pagar</small></article>
          <article><span>Saldo projetado</span><strong className={summary.projected_balance >= 0 ? "amount-positive" : "amount-negative"}>{money(summary.projected_balance)}</strong><small>Saldo atual + todas as pendências conhecidas</small></article>
        </div>
        <section className="finance-closing-snapshot">
          <header><div><span>RESUMO PARA FECHAMENTO</span><h3>Conferência gerencial do período</h3><p>Visão consultiva para conferência antes do fechamento formal. Este bloco ainda não trava nem reabre competências.</p></div><strong>{summary.period_entry_count} lançamento(s)</strong></header>
          <div>
            <article><span>Recebido</span><b className="amount-positive">{money(summary.settled_income)}</b></article>
            <article><span>Pago</span><b className="amount-negative">{money(summary.settled_expense)}</b></article>
            <article><span>A receber</span><b>{money(summary.pending_income)}</b></article>
            <article><span>A pagar</span><b>{money(summary.pending_expense)}</b></article>
            <article><span>Vencidos</span><b className={summary.overdue_count > 0 ? "amount-negative" : ""}>{summary.overdue_count}</b></article>
            <article><span>Próx. 7 dias</span><b>{summary.due_soon_count}</b></article>
          </div>
        </section>
        <div className="balance-cards">
          <article><span>Receitas lançadas</span><strong className="amount-positive">{money(summary.period_income)}</strong><small>{summary.period_income_count} lançamento(s)</small></article>
          <article><span>Saídas lançadas</span><strong className="amount-negative">{money(summary.period_expense)}</strong><small>{summary.period_expense_count} lançamento(s)</small></article>
          <article><span>Resultado de competência</span><strong className={summary.period_result >= 0 ? "amount-positive" : "amount-negative"}>{money(summary.period_result)}</strong><small>Receitas menos saídas do filtro</small></article>
          <article><span>Atrasado líquido</span><strong className={(summary.overdue_income - summary.overdue_expense) >= 0 ? "amount-positive" : "amount-negative"}>{money(summary.overdue_income - summary.overdue_expense)}</strong><small>{money(summary.overdue_income)} a receber · {money(summary.overdue_expense)} a pagar</small></article>
        </div>
        <MonthlyBalanceOverview summary={summary} />
        <article className="balance-visual"><h3>Composição do período</h3><CompositionDonut income={summary.period_income} expense={summary.period_expense}/><div className="balance-bars"><div><span>Receitas</span><i style={{ width: `${Math.min(100, summary.period_income / Math.max(summary.period_income, summary.period_expense, 1) * 100)}%` }}/><strong>{money(summary.period_income)}</strong></div><div className="expense-bar"><span>Saídas</span><i style={{ width: `${Math.min(100, summary.period_expense / Math.max(summary.period_income, summary.period_expense, 1) * 100)}%` }}/><strong>{money(summary.period_expense)}</strong></div></div></article>
        <section className="ledger-panel finance-monthly-balance">
          <header><div><span>VISÃO MENSAL DETALHADA</span><h2>Fechamento mês a mês</h2><p>Receitas, saídas, realizado e pendências por mês na base de data selecionada.</p></div></header>
          <div className="finance-monthly-table">
            <div className="finance-monthly-row finance-monthly-head"><span>Mês</span><span>Receitas</span><span>Saídas</span><span>Resultado</span><span>Recebido</span><span>Pago</span><span>A receber</span><span>A pagar</span></div>
            {summary.monthly_flow.map((month) => <article key={month.month} className="finance-monthly-row"><strong>{month.label}</strong><span className="amount-positive">{money(month.income)}</span><span className="amount-negative">{money(month.expense)}</span><span className={month.result >= 0 ? "amount-positive" : "amount-negative"}>{money(month.result)}</span><span>{money(month.settled_income)}</span><span>{money(month.settled_expense)}</span><span>{money(month.pending_income)}</span><span>{money(month.pending_expense)}</span></article>)}
          </div>
        </section>
      </section>}
      {view === "audit" && <section className="ledger-panel"><header><div><span>RASTREABILIDADE</span><h2>Auditoria financeira</h2><p>Usuário, data, hora e alteração executada.</p></div></header><div className="audit-list">{audit.map((item) => <article key={item.id}><span className={`audit-action ${item.action}`}>{actionLabels[item.action] ?? item.action}</span><div><strong>{item.description}</strong><small>{item.user_name} · {new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "medium" }).format(new Date(item.created_at))}</small></div><span>#{item.entity_id}</span></article>)}{!audit.length && <p className="finance-empty">Nenhum evento de auditoria no período.</p>}</div></section>}
    </main>

    {modalOpen && <div className="finance-modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && setModalOpen(false)}><section className="finance-modal"><header><div><span>{selected ? "DETALHES DO LANÇAMENTO" : "NOVO REGISTRO"}</span><h2>{form.entry_type === "income" ? "Receita financeira" : "Saída financeira"}</h2></div><button onClick={() => setModalOpen(false)}><X/></button></header>
      {selected && <div className="entry-actions"><button className={selected.status === "pending" ? "settle" : "reverse"} onClick={toggleSettlement}>{selected.status === "pending" ? <><CheckCircle2 size={17}/>Dar baixa</> : <><RotateCcw size={17}/>Desfazer baixa</>}</button>{selected.attachment_name && <button type="button" onClick={() => setPreviewOpen(true)}><Eye size={17}/>Visualizar anexo</button>}{selected.entry_type === "income" && selected.work_order_id && <><button type="button" className="finance-entry-os-link" onClick={() => openLinkedWorkOrder(selected.work_order_id!, "quote")} title="Abrir orçamento técnico do equipamento desta OS"><FileSearch size={17}/> Ver orçamento da OS</button><button type="button" className="finance-entry-os-link" onClick={() => openLinkedWorkOrder(selected.work_order_id!, "financial")} title="Ver valor orçado e valor aprovado da OS"><CircleDollarSign size={17}/> Ver valor aprovado</button></>}{!selected.obligation_id && <button className="delete" onClick={removeEntry}><Trash2 size={17}/>Excluir</button>}</div>}
      <form onSubmit={saveEntry}><div className="entry-type-toggle"><button type="button" className={form.entry_type === "income" ? "income active" : "income"} onClick={() => { if (!selected) { const next = initialForm(form.company_code, "income"); setForm(next); setInstallments(initialInstallments(next.due_date)); } }}>Entrada · Receita</button><button type="button" className={form.entry_type === "expense" ? "expense active" : "expense"} onClick={() => { if (!selected) { const next = initialForm(form.company_code, "expense"); setForm(next); setInstallments(initialInstallments(next.due_date)); } }}>Saída · Despesa</button></div>
        {!selected && <div className="finance-entry-mode" role="group" aria-label="Forma de lançamento"><button type="button" className={entryMode === "single" ? "active" : ""} onClick={() => { setEntryMode("single"); setAttachment(null); }}>Lançamento único</button><button type="button" className={entryMode === "installments" ? "active" : ""} onClick={() => { setEntryMode("installments"); setAttachment(null); setInstallments((current) => current.length >= 2 ? current : initialInstallments(form.due_date)); }}>Parcelado</button></div>}
        {selected?.obligation_id && <div className="finance-installment-lock"><ShieldCheck size={18}/><span><strong>Parcela vinculada a uma obrigação financeira</strong><small>Parcela {selected.installment_number ?? "—"}. Você pode corrigir os dados financeiros e também cliente/fornecedor, descrição, emissão/competência e documento fiscal. Dados compartilhados são atualizados em todas as parcelas da obrigação. Empresa, tipo, vínculo da O.S., número da parcela e exclusão permanecem protegidos.</small></span></div>}
        {selected?.obligation_id && selected.entry_type === "income" && <div className="finance-schedule-actions">
          <button type="button" disabled={saving} onClick={() => scheduleEditor ? setScheduleEditor(null) : void openScheduleEditor()}><Pencil size={16}/> {scheduleEditor ? "Fechar editor de parcelas" : "Editar / remover parcelamento"}</button>
        </div>}
        {scheduleEditor && <section className="finance-schedule-editor">
          <header><div><strong>Reorganizar parcelas da receita</strong><small>Modifique vencimentos e valores. Remova ou acrescente parcelas pendentes; a exclusão preserva auditoria.</small></div><strong>{money(scheduleEditor.rows.reduce((sum,row) => { const v=parseAmount(row.amount); return sum+(Number.isFinite(v)?v:0); },0))}</strong></header>
          <div className="finance-schedule-rows">{scheduleEditor.rows.map((row,index) => <div key={index} className="finance-schedule-row">
            <strong>{index+1}ª</strong><label>Vencimento<input type="date" value={row.due_date} onChange={(e) => setScheduleEditor((prev) => prev && ({...prev,rows:prev.rows.map((item,i) => i===index?{...item,due_date:e.target.value}:item)}))}/></label>
            <label>Valor (R$)<input inputMode="decimal" value={row.amount} onChange={(e) => setScheduleEditor((prev) => prev && ({...prev,rows:prev.rows.map((item,i) => i===index?{...item,amount:e.target.value}:item)}))}/></label>
            <button type="button" disabled={saving || scheduleEditor.rows.length === 1} onClick={() => setScheduleEditor((prev) => prev && ({...prev,rows:prev.rows.filter((_,i) => i!==index)}))}><Trash2 size={15}/> Remover</button>
          </div>)}</div>
          <div className="finance-schedule-footer"><button type="button" disabled={saving || scheduleEditor.rows.length>=120} onClick={() => setScheduleEditor((prev) => prev && ({...prev,rows:[...prev.rows,{installment_number:prev.rows.length+1,due_date:"",amount:"",payment_code:"",notes:""}]}))}><Plus size={16}/> Adicionar parcela</button>
          <button type="button" disabled={saving} className="finance-primary" onClick={() => void saveScheduleEditor()}>Salvar parcelamento</button>
          <button type="button" disabled={saving} className="finance-schedule-delete" onClick={() => void deleteScheduleEditor()}><Trash2 size={15}/> Excluir parcelamento inteiro</button></div>
        </section>}
        <fieldset className="finance-entry-fields">
        <div className="form-row"><label>Empresa<select disabled={Boolean(selected?.obligation_id)} value={form.company_code} onChange={(e) => { const code = e.target.value as CompanyCode; setForm((old) => ({ ...old, company_code: code, bank_name: companies.find((item) => item.code === code)?.banks[0] ?? "" })); }}>{companies.map((item) => <option key={item.code} value={item.code}>{item.name}</option>)}</select></label><label>Banco<select value={form.bank_name} onChange={(e) => setForm({ ...form, bank_name: e.target.value })}>{availableBanks.map((bank) => <option key={bank}>{bank}</option>)}</select></label></div>
        {form.entry_type === "income" && <section className="billing-workflow-card">
          <header><div><span>INTEGRAÇÃO COM A OS</span><strong>Conformidade de faturamento</strong></div><ShieldCheck size={22}/></header>
          <div className="finance-os-search"><label>Buscar Ordem de Serviço<div className="finance-os-searchbox"><Search size={17}/><input disabled={Boolean(selected?.obligation_id)} value={workOrderSearch} onChange={(e) => setWorkOrderSearch(e.target.value)} placeholder="Digite OS, cliente ou série..." /></div></label>
            {form.work_order_id && billingReadiness && <div className="finance-os-selected"><div><small>OS SELECIONADA</small><strong>{billingReadiness.work_order_number} · {billingReadiness.customer_name}</strong></div><button type="button" disabled={Boolean(selected?.obligation_id)} onClick={() => { setForm({ ...form, work_order_id: "" }); setBillingReadiness(null); setBillingConfirmation(emptyBillingConfirmation()); setWorkOrderSearch(""); setWorkOrders([]); }}>Trocar OS</button></div>}
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
        <div className="form-row"><label>Descrição<input required value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })}/></label><label>{!selected && entryMode === "installments" ? "Valor total" : "Valor"}<input required inputMode="decimal" placeholder="0,00" value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })}/></label></div>
        {form.entry_type === "income" && <><div className="form-row"><label>NFS-e<input value={form.nfse_number} onChange={(e) => setForm({ ...form, nfse_number: e.target.value })} placeholder="Número da NFS-e"/></label><label>NF-e<input value={form.nfe_number} onChange={(e) => setForm({ ...form, nfe_number: e.target.value })} placeholder="Número da NF-e"/></label></div><label>Série<input value={form.series} onChange={(e) => setForm({ ...form, series: e.target.value })} placeholder="Ex.: 1"/></label><small className="invoice-hint">{selected && !form.nfse_number && !form.nfe_number ? "Registro histórico sem NF: pode ser editado e salvo normalmente." : "Preencha pelo menos uma das caixas: NFS-e ou NF-e."}</small></>}
        {form.entry_type === "expense" && <label>Documento / referência<input value={form.document_number} onChange={(e) => setForm({ ...form, document_number: e.target.value })}/></label>}
        <div className="form-row"><label>Data de emissão<input type="date" required value={form.issue_date} onChange={(e) => setForm({ ...form, issue_date: e.target.value, posting_date: e.target.value })}/></label>{(selected || entryMode === "single") && <label>Vencimento<input type="date" required value={form.due_date} onChange={(e) => setForm({ ...form, due_date: e.target.value })}/></label>}</div>
        {!selected && entryMode === "installments" && <section className="finance-installments-card">
          <header><div><span>PARCELAMENTO NATIVO</span><strong>Vencimentos e valores por parcela</strong><small>Você pode preencher manualmente ou usar as sugestões abaixo e depois ajustar cada parcela.</small></div><label>Quantidade<input type="number" min={2} max={60} value={installments.length} onChange={(e) => resizeInstallments(Number(e.target.value))}/></label></header>
          <div className="finance-installment-shortcuts"><button type="button" onClick={distributeInstallments}>Dividir valor igualmente</button><button type="button" onClick={suggestInstallmentDates}>Sugerir vencimentos mensais</button><small>Sugestões editáveis. A divisão distribui os centavos sem divergência no total.</small></div>
          <div className="finance-installment-summary"><span>Total informado: <b>{Number.isFinite(parseAmount(form.amount)) ? money(parseAmount(form.amount)) : money(0)}</b></span><span>Soma das parcelas: <b>{money(installments.reduce((sum, item) => { const value = parseAmount(item.amount); return sum + (Number.isFinite(value) ? value : 0); }, 0))}</b></span></div>
          <div className="finance-installment-list">{installments.map((item, index) => <article key={item.installment_number}>
            <strong>{index + 1}ª parcela</strong>
            <label>Vencimento<input type="date" required value={item.due_date} onChange={(e) => updateInstallment(index, { due_date: e.target.value })}/></label>
            <label>Valor<input required inputMode="decimal" placeholder="0,00" value={item.amount} onChange={(e) => updateInstallment(index, { amount: e.target.value })}/></label>
            {form.entry_type === "expense" && <label className="finance-installment-wide">PIX / boleto da parcela<textarea rows={2} value={item.payment_code} onChange={(e) => updateInstallment(index, { payment_code: e.target.value })}/></label>}
            <label className="finance-installment-wide">Observação da parcela<textarea rows={2} value={item.notes} onChange={(e) => updateInstallment(index, { notes: e.target.value })}/></label>
          </article>)}</div>
        </section>}
        {form.entry_type === "expense" && (selected || entryMode === "single") && <label>Chave PIX ou código do boleto<textarea rows={2} value={form.payment_code} onChange={(e) => setForm({ ...form, payment_code: e.target.value })}/></label>}
        <label>Observações<textarea rows={3} value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })}/></label>
        {(selected || entryMode === "single") && <label className="attachment-field"><UploadCloud/><span><strong>{attachment?.name || selected?.attachment_name || "Anexar comprovante, boleto ou PDF"}</strong><small>PDF, JPG, PNG ou WEBP · até 10 MB</small></span><input type="file" accept="application/pdf,image/jpeg,image/png,image/webp,.pdf,.jpg,.jpeg,.png,.webp" onChange={(e) => setAttachment(e.target.files?.[0] ?? null)}/></label>}
        {!selected && entryMode === "installments" && <div className="finance-installment-attachment-note"><Paperclip size={17}/><span>O parcelamento cria lançamentos independentes para baixa. Anexos devem ser incluídos depois na parcela correspondente.</span></div>}
        {selected && <div className="entry-meta"><span>Status: <b>{selected.status === "pending" ? "Pendente" : "Baixado"}</b></span>{selected.obligation_id && <span>Parcela: <b>{selected.installment_number ?? "—"}</b></span>}<span>Baixa: <b>{dateBR(selected.settlement_date)}</b></span><span>Atualizado: <b>{new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "short" }).format(new Date(selected.updated_at))}</b></span></div>}
        </fieldset>
        <footer><button type="button" onClick={() => setModalOpen(false)}>Cancelar</button><button className="finance-primary" disabled={saving}>{selected ? <Pencil size={17}/> : <Plus size={17}/>} {saving ? "Salvando..." : selected ? "Salvar alterações" : entryMode === "installments" ? `Salvar ${installments.length} parcelas` : "Salvar lançamento"}</button></footer>
      </form></section></div>}
    {previewOpen && selected?.attachment_name && <div className="attachment-preview-backdrop" onMouseDown={(e) => e.target === e.currentTarget && setPreviewOpen(false)}><section className="attachment-preview attachment-preview--fullscreen"><header><div><span>ANEXO DO LANÇAMENTO</span><strong>{selected.attachment_name}</strong></div><div className="attachment-preview-actions"><a href={`/api/finance/entries/${selected.id}/attachment/preview`} target="_blank" rel="noreferrer">Abrir em nova aba</a><button type="button" onClick={() => setPreviewOpen(false)} aria-label="Fechar visualização"><X/></button></div></header><div className="attachment-preview-body">{selected.attachment_mime?.startsWith("image/") ? <img src={`/api/finance/entries/${selected.id}/attachment/preview`} alt={selected.attachment_name}/> : <iframe src={`/api/finance/entries/${selected.id}/attachment/preview`} title={selected.attachment_name}/>}</div></section></div>}
  </div>;
}

