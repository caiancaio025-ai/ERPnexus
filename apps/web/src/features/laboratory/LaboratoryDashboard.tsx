import { useEffect, useId, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  ArrowLeft, BadgeDollarSign, BarChart3, CheckCircle2, ClipboardList, FileText, FlaskConical,
  Camera, History, Image, Layers3, LogOut, MapPin, Pencil, Plus, Printer, RefreshCw, Save, Search, Settings, ShieldCheck,
  Trash2, UploadCloud, UserRoundCog, Users, Wrench, X,
} from "lucide-react";

import { apiClient } from "../../shared/api/apiClient";
import type { WorkOrderReceivables } from "../finance/types";
import { SenticoSidebar } from "../../shared/ui/SenticoSidebar";
import type { AuthUser } from "../auth/AuthCard";
import { ActionButton } from "./components/ActionButton";
import { QuoteEditor } from "./components/QuoteEditor";
import { MaterialsPanel } from "./components/MaterialsPanel";
import { EquipmentDocumentsPanel } from "./components/EquipmentDocumentsPanel";
import { CameraCapture } from "./components/CameraCapture";
import { ConfigMasterPanel } from "./components/ConfigMasterPanel";
import { MechanicsPanel } from "./components/MechanicsPanel";
import { TechnicianProductionReport } from "./components/TechnicianProductionReport";
import type {
  CompanyCode, CompanyProfile, Customer, LocationHistory, Priority, StatusHistory, Technician, WorkOrder,
  WorkflowOption, WorkOrderPage, WorkOrderStatus, WorkOrderSummary, LaboratoryLocationMap,
  LaboratoryLocationConfig,
} from "./types";
import "./laboratory.css";

type Props = { user: AuthUser; onLogout: () => void };
type View = "orders" | "locations" | "technician_report" | "invoiced" | "no_repair" | "warranty";
type SettingsTab = "customers" | "technicians" | "workflow" | "companies" | "locations";
type DetailTab = "general" | "technical" | "financial" | "materials" | "status" | "documents" | "quote" | "mechanics" | "history";

type FormState = {
  company_code: CompanyCode; customer_id: string; customer_name: string; serial_number: string;
  manufacturer: string; model: string; equipment_type: string; power: string; voltage: string;
  entry_invoice: string; entry_invoice_2: string; entry_invoice_3: string; entry_invoice_access_key: string; exit_invoice: string; exit_invoice_2: string; exit_invoice_3: string; exit_invoice_access_key: string; warranty_invoice: string; warranty_invoice_2: string; warranty_invoice_3: string; warranty_entry_invoice_1: string; warranty_entry_invoice_2: string; warranty_entry_invoice_3: string; warranty_exit_invoice_1: string; warranty_exit_invoice_2: string; warranty_exit_invoice_3: string;
  storage_location: string; assigned_technician_id: string; priority: Priority;
  reported_defect: string; entry_condition: string; accessories_received: string; parts_cost: string;
  quoted_value: string; approved_value: string; internal_notes: string; customer_notes: string;
};

type DetailState = FormState & { id: number; number: string; status: WorkOrderStatus; substatuses: string[]; version: number; is_inactive: boolean };
type LaboratoryPeriods = { latest_month: number; latest_year: number; years: number[] };

const priorityLabels: Record<Priority, string> = { low: "Baixa", normal: "Normal", high: "Alta", urgent: "Urgente" };
const monthLabels = [
  "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
  "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
];
const statusLabels: Record<string, string> = {
  received: "Entrada",
  awaiting_analysis: "Aguardando análise",
  in_analysis: "Em análise",
  awaiting_quote: "Em análise • preparando orçamento",
  quote_sent: "Orçamento enviado",
  awaiting_approval: "Ag. Aprovação",
  approved: "Aprovado",
  rejected: "Reprovado",
  awaiting_parts: "Aprovado • ag. peças",
  in_repair: "Aprovado • em reparo",
  in_testing: "Aprovado • em testes",
  completed: "Concluído",
  awaiting_pickup: "Liberado",
  delivered: "Entregue",
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
  { value: "in_analysis", label: "Em análise" },
  { value: "awaiting_approval", label: "Ag. Aprovação" },
  { value: "approved", label: "Aprovado" },
  { value: "no_repair", label: "Sem conserto" },
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
  { value: "completed", label: "Concluído" },
  { value: "delivered", label: "Entregue" },
  { value: "rejected", label: "Reprovado" },
  { value: "cancelled", label: "Cancelado" },
];


function statusLabel(status: WorkOrderStatus, workflowOptions: WorkflowOption[] = []) {
  return workflowOptions.find((item) => item.kind === "status" && item.code === status)?.label
    ?? statusLabels[status]
    ?? status;
}

function substatusLabel(code: string, workflowOptions: WorkflowOption[] = []) {
  return workflowOptions.find((item) => item.kind === "substatus" && item.code === code)?.label ?? code;
}

function detailTabFromQuery(value: string | null): DetailTab {
  const allowed: DetailTab[] = ["general", "technical", "financial", "materials", "status", "documents", "quote", "mechanics", "history"];
  return allowed.includes(value as DetailTab) ? value as DetailTab : "general";
}

const emptyForm = (): FormState => ({
  company_code: "universo_eletronica", customer_id: "", customer_name: "", serial_number: "",
  manufacturer: "", model: "", equipment_type: "", power: "", voltage: "", entry_invoice: "", entry_invoice_2: "", entry_invoice_3: "",
  entry_invoice_access_key: "", exit_invoice: "", exit_invoice_2: "", exit_invoice_3: "", exit_invoice_access_key: "", warranty_invoice: "", warranty_invoice_2: "", warranty_invoice_3: "", warranty_entry_invoice_1: "", warranty_entry_invoice_2: "", warranty_entry_invoice_3: "", warranty_exit_invoice_1: "", warranty_exit_invoice_2: "", warranty_exit_invoice_3: "", storage_location: "",
  assigned_technician_id: "", priority: "normal", reported_defect: "",
  entry_condition: "", accessories_received: "", parts_cost: "", quoted_value: "",
  approved_value: "", internal_notes: "", customer_notes: "",
});

function toDetail(order: WorkOrder): DetailState {
  return {
    id: order.id, number: order.number, status: order.status, substatuses: order.substatuses ?? [], version: order.version, is_inactive: order.is_inactive ?? false,
    company_code: order.company_code, customer_id: String(order.customer_id ?? ""),
    customer_name: order.customer_name, serial_number: order.equipment_serial ?? "",
    manufacturer: order.manufacturer ?? "", model: order.model ?? "",
    equipment_type: order.equipment_type ?? "", power: order.power ?? "", voltage: order.voltage ?? "",
    entry_invoice: order.entry_invoice ?? "", entry_invoice_2: order.entry_invoice_2 ?? "", entry_invoice_3: order.entry_invoice_3 ?? "", entry_invoice_access_key: order.entry_invoice_access_key ?? "",
    exit_invoice: order.exit_invoice ?? "", exit_invoice_2: order.exit_invoice_2 ?? "", exit_invoice_3: order.exit_invoice_3 ?? "", exit_invoice_access_key: order.exit_invoice_access_key ?? "", warranty_invoice: order.warranty_invoice ?? "", warranty_invoice_2: order.warranty_invoice_2 ?? "", warranty_invoice_3: order.warranty_invoice_3 ?? "", warranty_entry_invoice_1: order.warranty_entry_invoice_1 ?? "", warranty_entry_invoice_2: order.warranty_entry_invoice_2 ?? "", warranty_entry_invoice_3: order.warranty_entry_invoice_3 ?? "", warranty_exit_invoice_1: order.warranty_exit_invoice_1 ?? "", warranty_exit_invoice_2: order.warranty_exit_invoice_2 ?? "", warranty_exit_invoice_3: order.warranty_exit_invoice_3 ?? "",
    storage_location: order.storage_location ?? "",
    assigned_technician_id: String(order.assigned_technician_id ?? ""), priority: order.priority,
    reported_defect: order.reported_defect, entry_condition: order.entry_condition ?? "",
    accessories_received: order.accessories_received ?? "", parts_cost: order.parts_cost ?? "",
    quoted_value: order.quoted_value ?? "", approved_value: order.approved_value ?? "",
    internal_notes: order.internal_notes ?? "", customer_notes: order.customer_notes ?? "",
  };
}

export function LaboratoryDashboard({ user, onLogout }: Props) {
  const navigate = useNavigate();
  const canViewValues = ["gestao", "super_admin"].includes(user.role);
  const canManageQuote = ["admin", "gestao", "super_admin"].includes(user.role);
  const canManageTechnicians = ["super_admin", "admin", "gestao"].includes(user.role);
  const [summary, setSummary] = useState<WorkOrderSummary | null>(null);
  const [pageData, setPageData] = useState<WorkOrderPage>({ items: [], page: 1, page_size: 25, total: 0, pages: 0 });
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [technicians, setTechnicians] = useState<Technician[]>([]);
  const [workflowOptions, setWorkflowOptions] = useState<WorkflowOption[]>([]);
  const [companies, setCompanies] = useState<CompanyProfile[]>([]);
  const [locationConfig, setLocationConfig] = useState<LaboratoryLocationConfig>({ areas: [], racks: [], locations: [] });
  const [company, setCompany] = useState<CompanyCode | "all">("all");
  const [statusFilter, setStatusFilter] = useState<WorkOrderStatus | "all">("all");
  const now = new Date();
  const [monthFilter, setMonthFilter] = useState<number | "all">(now.getMonth() + 1);
  const [yearFilter, setYearFilter] = useState(now.getFullYear());
  const [availableYears, setAvailableYears] = useState<number[]>([now.getFullYear()]);
  const [periodReady, setPeriodReady] = useState(false);
  const [search, setSearch] = useState("");
  const [showInactive, setShowInactive] = useState(false);
  const [page, setPage] = useState(1);
  const [view, setView] = useState<View>("orders");
  const [locationMap, setLocationMap] = useState<LaboratoryLocationMap | null>(null);
  const [locationMapUpdatedAt, setLocationMapUpdatedAt] = useState<Date | null>(null);
  const [locationFilter, setLocationFilter] = useState<"all" | "occupied" | "free" | "urgent" | "attention" | "critical">("all");
  const [locationPreview, setLocationPreview] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [settingsTab, setSettingsTab] = useState<SettingsTab>("customers");
  const [form, setForm] = useState<FormState>(emptyForm);
  const [detail, setDetail] = useState<DetailState | null>(null);
  const [detailTab, setDetailTab] = useState<DetailTab>("general");
  const [history, setHistory] = useState<StatusHistory[]>([]);
  const [locationHistory, setLocationHistory] = useState<LocationHistory[]>([]);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const [saved, setSaved] = useState(false);
  const detailSavedFingerprintRef = useRef<string | null>(null);
  const detailSavePromiseRef = useRef<Promise<DetailState | null> | null>(null);

  const query = useMemo(() => {
    const normalizedSearch = search.trim();
    const params = new URLSearchParams({ page: String(page), page_size: "25" });
    if (company !== "all") params.set("company_code", company);
    if (showInactive && canManageQuote) params.set("include_inactive", "true");
    // Pesquisa e filtros devem atuar juntos (AND); a API já aceita essa combinação.
    if (normalizedSearch) params.set("search", normalizedSearch);
    params.set("year", String(yearFilter));
    if (monthFilter !== "all") params.set("month", String(monthFilter));
    const effectiveStatus =
      view === "no_repair" ? "no_repair" :
      view === "invoiced" ? "invoiced" :
      view === "warranty" ? "warranty" :
      statusFilter;
    if (effectiveStatus !== "all") params.set("status", effectiveStatus);
    return params.toString();
  }, [company, monthFilter, page, search, statusFilter, view, yearFilter, showInactive, canManageQuote]);

  async function loadMasterData() {
    try {
      const [companyRows, locationRows] = await Promise.all([
        apiClient.get<CompanyProfile[]>("/laboratory/settings/companies?include_inactive=true"),
        apiClient.get<LaboratoryLocationConfig>("/laboratory/settings/locations"),
      ]);
      setCompanies(companyRows);
      setLocationConfig(locationRows);
      const firstActiveCompany = companyRows.find((item) => item.is_active);
      if (firstActiveCompany && !companyRows.some((item) => item.company_code === form.company_code && item.is_active)) {
        setForm((current) => ({ ...current, company_code: firstActiveCompany.company_code }));
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Falha ao carregar Config Master.");
    }
  }

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
      const summaryParams = new URLSearchParams({ year: String(yearFilter) });
      if (monthFilter !== "all") summaryParams.set("month", String(monthFilter));
      if (company !== "all") summaryParams.set("company_code", company);
      const [summaryData, orders, customerData, technicianData, workflowData] = await Promise.all([
        apiClient.get<WorkOrderSummary>(`/laboratory/summary?${summaryParams.toString()}`),
        apiClient.get<WorkOrderPage>(`/laboratory/work-orders?${query}`),
        apiClient.get<Customer[]>(`/laboratory/customers${companyQuery}`),
        apiClient.get<Technician[]>(`/laboratory/technicians${companyQuery}`),
        apiClient.get<WorkflowOption[]>("/laboratory/workflow-options?include_inactive=true"),
      ]);
      setSummary(summaryData); setPageData(orders); setCustomers(customerData); setTechnicians(technicianData); setWorkflowOptions(workflowData);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Falha ao carregar o Laboratório."); }
    finally { setLoading(false); }
  }

  useEffect(() => { void loadMasterData(); }, []);
  useEffect(() => {
    setPeriodReady(false);
    void loadPeriods();
  }, [company]);
  useEffect(() => { if (periodReady) void load(); }, [query, periodReady]);
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("acao") === "nova-os") setShowForm(true);
    const workOrderId = Number(params.get("os"));
    const requestedTab = params.get("aba");
    const initialTab = detailTabFromQuery(requestedTab);
    if (Number.isInteger(workOrderId) && workOrderId > 0) void openOrder(workOrderId, initialTab);
  }, []);

  function filterByPriorityStatus(status: WorkOrderStatus) {
    setView("orders"); setStatusFilter(status); setPage(1);
  }

  async function openOrder(orderId: number, initialTab: DetailTab = "general") {
    setLoading(true); setError("");
    try {
      const order = await apiClient.get<WorkOrder>(`/laboratory/work-orders/${orderId}`);
      const openedDetail = toDetail(order);
      setDetail(openedDetail);
      detailSavedFingerprintRef.current = detailFingerprint(openedDetail, canViewValues);
      setDetailTab(initialTab);
      const [statusRows, locationRows] = await Promise.all([
        apiClient.get<StatusHistory[]>(`/laboratory/work-orders/${orderId}/history`),
        apiClient.get<LocationHistory[]>(`/laboratory/work-orders/${orderId}/location-history`),
      ]);
      setHistory(statusRows);
      setLocationHistory(locationRows);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Falha ao abrir a O.S."); }
    finally { setLoading(false); }
  }

  async function inactivateSelected() {
    if (!detail || !canManageQuote || detail.is_inactive) return;
    if (hasDetailChanges(detail)) {
      setError("Salve ou descarte as alterações pendentes antes de inativar a O.S.");
      return;
    }
    const reason = window.prompt(`Informe o motivo para inativar a O.S. ${detail.number} (mínimo 10 caracteres):`);
    if (reason === null) return;
    if (reason.trim().length < 10) {
      setError("Descreva o motivo da inativação com pelo menos 10 caracteres.");
      return;
    }
    if (!window.confirm(`Confirma inativar ${detail.number}? Ela sairá dos indicadores, mas permanecerá no histórico.`)) return;
    setLoading(true); setError("");
    try {
      await apiClient.post(`/laboratory/work-orders/${detail.id}/inactivate`, { version: detail.version, reason: reason.trim() });
      setDetail(null); detailSavedFingerprintRef.current = null;
      setMessage(`O.S. ${detail.number} inativada. Histórico preservado.`);
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Não foi possível inativar a O.S.");
    } finally { setLoading(false); }
  }

  async function createWorkOrder(event: React.FormEvent, entryFiles: File[]) {
    event.preventDefault(); setLoading(true); setError(""); setMessage("");
    try {
      const created = await apiClient.post<WorkOrder>("/laboratory/work-orders", payloadFromForm(form, canViewValues));
      let uploaded = 0;
      let failedUploads = 0;
      for (const file of entryFiles) {
        const body = new FormData();
        body.append("file", file);
        try {
          await apiClient.post(`/laboratory/work-orders/${created.id}/documents?category=entrada`, body);
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
      if (locationMap !== null || view === "locations") await loadLocationMap({ silent: true });
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Falha ao criar a O.S."); }
    finally { setLoading(false); }
  }

  function hasDetailChanges(currentDetail: DetailState | null) {
    if (!currentDetail || detailSavedFingerprintRef.current === null) return false;
    return detailFingerprint(currentDetail, canViewValues) !== detailSavedFingerprintRef.current;
  }

  async function persistDetail(currentDetail: DetailState, announce = true): Promise<DetailState | null> {
    const currentFingerprint = detailFingerprint(currentDetail, canViewValues);
    if (detailSavedFingerprintRef.current === currentFingerprint) {
      if (announce) {
        setSaved(true);
        setMessage(`O.S. ${currentDetail.number} sem alterações pendentes.`);
        window.setTimeout(() => setSaved(false), 1800);
      }
      return currentDetail;
    }

    if (detailSavePromiseRef.current) return detailSavePromiseRef.current;

    const savePromise = (async (): Promise<DetailState | null> => {
      setLoading(true); setSaved(false); setError("");
      try {
        const updated = await apiClient.patch<WorkOrder>(`/laboratory/work-orders/${currentDetail.id}`, {
          ...payloadFromForm(currentDetail, canViewValues), version: currentDetail.version,
        });
        const savedDetail = toDetail(updated);
        detailSavedFingerprintRef.current = detailFingerprint(savedDetail, canViewValues);
        setDetail(savedDetail);
        setSaved(true);
        if (announce) setMessage(`O.S. ${updated.number} atualizada.`);
        await load();
        setLocationHistory(await apiClient.get<LocationHistory[]>(`/laboratory/work-orders/${updated.id}/location-history`));
        if (locationMap !== null || view === "locations") await loadLocationMap({ silent: true });
        window.setTimeout(() => setSaved(false), 1800);
        return savedDetail;
      } catch (reason) {
        setError(reason instanceof Error ? reason.message : "Falha ao salvar a O.S.");
        return null;
      } finally {
        setLoading(false);
      }
    })();

    detailSavePromiseRef.current = savePromise;
    try {
      return await savePromise;
    } finally {
      detailSavePromiseRef.current = null;
    }
  }

  async function saveDetail() {
    if (!detail) return;
    await persistDetail(detail, true);
  }

  async function openFinanceFromDetail(entryId?: number) {
    if (!detail) return;
    // O orçamento/valor aprovado da OS precisa ser persistido antes de abrir
    // os recebíveis, para evitar sugestão financeira baseada em valor antigo.
    if (hasDetailChanges(detail)) {
      const savedDetail = await persistDetail(detail, false);
      if (!savedDetail) return;
    }
    navigate(`/financeiro?os=${detail.id}${entryId ? `&lancamento=${entryId}` : ""}`);
  }

  async function switchDetailTab(nextTab: DetailTab) {
    if (!detail || nextTab === detailTab) return;
    const hadPendingChanges = hasDetailChanges(detail);
    if (hadPendingChanges) {
      const savedDetail = await persistDetail(detail, false);
      if (!savedDetail) return;
      setMessage(`Alterações da ${savedDetail.number} salvas automaticamente.`);
    }
    setDetailTab(nextTab);
    if (nextTab === "history") {
      const [statusRows, locationRows] = await Promise.all([
        apiClient.get<StatusHistory[]>(`/laboratory/work-orders/${detail.id}/history`),
        apiClient.get<LocationHistory[]>(`/laboratory/work-orders/${detail.id}/location-history`),
      ]);
      setHistory(statusRows);
      setLocationHistory(locationRows);
    }
  }

  async function closeDetail() {
    if (!detail) return;
    if (hasDetailChanges(detail)) {
      const savedDetail = await persistDetail(detail, false);
      if (!savedDetail) return;
    }
    detailSavedFingerprintRef.current = null;
    setDetail(null);
  }

  async function changeStatus(targetStatus: WorkOrderStatus, override = false, overrideNote = "") {
    if (!detail || targetStatus === detail.status) return;
    let currentDetail = detail;
    if (hasDetailChanges(currentDetail)) {
      const savedDetail = await persistDetail(currentDetail, false);
      if (!savedDetail) return;
      currentDetail = savedDetail;
    }

    setLoading(true); setError(""); setMessage("");
    try {
      const currentStatus = currentDetail.status;
      const updated = await apiClient.post<WorkOrder>(`/laboratory/work-orders/${currentDetail.id}/status`, {
        status: targetStatus, version: currentDetail.version,
        note: override ? overrideNote : `Status alterado de ${statusLabel(currentStatus, workflowOptions)} para ${statusLabel(targetStatus, workflowOptions)} pela tela de detalhes.`,
        override,
      });
      const updatedDetail = toDetail(updated);
      detailSavedFingerprintRef.current = detailFingerprint(updatedDetail, canViewValues);
      setDetail(updatedDetail);
      setHistory(await apiClient.get<StatusHistory[]>(`/laboratory/work-orders/${currentDetail.id}/history`));
      setMessage(`Status da ${updated.number} alterado para ${statusLabel(updated.status, workflowOptions)}.`);
      await load();
      if (locationMap !== null || view === "locations") await loadLocationMap({ silent: true });
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Não foi possível alterar o status."); }
    finally { setLoading(false); }
  }

  async function toggleSubstatus(code: string, active: boolean) {
    if (!detail) return;
    let currentDetail = detail;
    if (hasDetailChanges(currentDetail)) {
      const savedDetail = await persistDetail(currentDetail, false);
      if (!savedDetail) return;
      currentDetail = savedDetail;
    }

    setLoading(true); setError(""); setMessage("");
    try {
      const updated = await apiClient.post<WorkOrder>(`/laboratory/work-orders/${currentDetail.id}/substatuses/${code}`, {
        active, version: currentDetail.version,
      });
      const updatedDetail = toDetail(updated);
      detailSavedFingerprintRef.current = detailFingerprint(updatedDetail, canViewValues);
      setDetail(updatedDetail);
      const option = workflowOptions.find((item) => item.kind === "substatus" && item.code === code);
      setMessage(`${option?.label ?? "Substatus"} ${active ? "marcado" : "desmarcado"} na ${updated.number}.`);
      await load();
      if (locationMap !== null || view === "locations") await loadLocationMap({ silent: true });
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Não foi possível alterar o substatus."); }
    finally { setLoading(false); }
  }

  const primaryStatusOptions = useMemo(() => {
    const configured = workflowOptions
      .filter((item) => item.kind === "status" && item.is_active)
      .sort((a, b) => a.sort_order - b.sort_order || a.id - b.id)
      .map((item) => ({ value: item.code, label: item.label }));
    return configured.length ? configured : businessStatusOptions;
  }, [workflowOptions]);

  async function loadLocationMap(options?: { silent?: boolean }) {
    const silent = options?.silent ?? false;
    if (!silent) setLoading(true);
    setError("");
    try {
      const data = await apiClient.get<LaboratoryLocationMap>(`/laboratory/locations/map?ts=${Date.now()}`);
      setLocationMap(data);
      setLocationMapUpdatedAt(new Date());
      return data;
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Não foi possível carregar o mapa de localizações.");
      return null;
    } finally {
      if (!silent) setLoading(false);
    }
  }

  async function openLocationPreview(location: string) {
    setError("");
    const data = await loadLocationMap({ silent: true });
    if (data) setLocationPreview(location);
  }

  useEffect(() => {
    if (view !== "locations") return;
    void loadLocationMap();
    const timer = window.setInterval(() => {
      if (document.visibilityState === "visible") void loadLocationMap({ silent: true });
    }, 10000);
    return () => window.clearInterval(timer);
  }, [view]);

  const filteredItems = pageData.items;

  return (
    <main className="lab-layout sentico-shell">
      <SenticoSidebar
        user={user}
        onLogout={onLogout}
        sectionLabel="Laboratório"
        sectionItems={[
          { id: "orders", label: "Ordens de serviço", icon: Wrench, active: view === "orders", onClick: () => setView("orders") },
          { id: "locations", label: "Mapa de localizações", icon: Layers3, active: view === "locations", onClick: () => setView("locations") },
          { id: "technician_report", label: "Produção por técnico", icon: BarChart3, active: view === "technician_report", onClick: () => setView("technician_report") },
          { id: "invoiced", label: "Faturados", icon: BadgeDollarSign, active: view === "invoiced", onClick: () => setView("invoiced") },
          { id: "no_repair", label: "Sem conserto", icon: CheckCircle2, active: view === "no_repair", onClick: () => setView("no_repair") },
          { id: "warranty", label: "Garantias", icon: ShieldCheck, active: view === "warranty", onClick: () => setView("warranty") },
          { id: "settings", label: "Configurações", icon: Settings, onClick: () => setShowSettings(true) },
        ]}
      />

      <section className="lab-shell sentico-content">
        <header className="lab-header">
          <div><p className="lab-eyebrow">SÊNTICO ERP</p><h1>Operação técnica e rastreabilidade</h1><span>Controle completo de entrada, execução, orçamento e saída.</span></div>
          <div className="lab-user"><span>{user.name}</span><ActionButton variant="secondary" icon={<LogOut size={17} />} onClick={onLogout}>Sair</ActionButton></div>
        </header>
        {error && <div className="lab-alert error">{error}</div>}{message && <div className="lab-alert success">{message}</div>}

        {view !== "locations" && view !== "technician_report" && <>
        <section className="lab-priority-kpis" aria-label="Prioridades comerciais do laboratório">
          <button className={statusFilter === "in_analysis" ? "active" : ""} onClick={() => filterByPriorityStatus("in_analysis")}>
            <span>EM ANÁLISE</span><strong>{summary?.analyzed ?? 0}</strong><small>Diagnóstico em andamento</small>
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
          {canViewValues && <article><span>Total aprovado</span><strong>{currency(summary?.approved_total ?? "")}</strong></article>}
          {canViewValues && <article><span>Aguardando aprovação</span><strong>{currency(summary?.awaiting_approval_total ?? "")}</strong></article>}
        </section>

        <section className="lab-toolbar">
          <div className="lab-search"><Search size={18} /><input value={search} onChange={(e) => { setSearch(e.target.value); setPage(1); }} placeholder="Buscar O.S., cliente, equipamento/modelo, NF, chave ou localização" /></div>
          <select aria-label="Mês de entrada" value={monthFilter} onChange={(e) => {
            setMonthFilter(e.target.value === "all" ? "all" : Number(e.target.value));
            setPage(1);
          }}>
            <option value="all">Todos os meses</option>
            {monthLabels.map((label, index) => <option key={label} value={index + 1}>{label}</option>)}
          </select>
          <select aria-label="Ano de entrada" value={yearFilter} onChange={(e) => { setYearFilter(Number(e.target.value)); setPage(1); }}>
            {availableYears.map((year) => <option key={year} value={year}>{year}</option>)}
          </select>
          <select value={company} onChange={(e) => { setCompany(e.target.value as CompanyCode | "all"); setPage(1); }}><option value="all">Todas as empresas</option>{companies.map((item) => <option key={item.id} value={item.company_code}>{item.trade_name || item.legal_name}{!item.is_active ? " (inativa)" : ""}</option>)}</select>
          <select value={statusFilter} onChange={(e) => { setStatusFilter(e.target.value as WorkOrderStatus | "all"); setPage(1); }}>
            <option value="all">Todos os status</option>
            <optgroup label="Status principais">{primaryStatusOptions.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</optgroup>
            <optgroup label="Etapas operacionais">{operationalStatusOptions.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</optgroup>
          </select>
          {canManageQuote && <label className="lab-include-inactive"><input type="checkbox" checked={showInactive} onChange={(e) => { setShowInactive(e.target.checked); setPage(1); }}/> Mostrar OS inativas</label>}
          <ActionButton variant="secondary" icon={<RefreshCw size={17} />} loading={loading} onClick={() => void load()}>Atualizar</ActionButton>
          <ActionButton icon={<Plus size={18} />} onClick={() => setShowForm(true)}>Nova O.S.</ActionButton>
        </section>

        <section className="lab-table-card">
          <table><thead><tr><th>O.S.</th><th>Cliente</th><th>Equipamento/série</th><th>Localização</th><th>NF entrada</th><th>NF saída</th><th>Garantia (1–3)</th><th>Status</th><th>Prioridade</th><th>Entrada</th>{canViewValues && <th>Valor cobrado</th>}</tr></thead>
            <tbody>{filteredItems.map((order) => <tr key={order.id} className={`lab-order-row priority-${order.priority}${order.is_inactive ? " lab-order-inactive" : ""}`} onClick={() => void openOrder(order.id)} tabIndex={0} onKeyDown={(event) => { if (event.key === "Enter") void openOrder(order.id); }}>
              <td><button className="lab-order-link">{order.number}</button></td><td>{order.customer_name}</td><td>{order.equipment_type || order.model || order.equipment_serial || "Sem identificação"}</td><td>{order.storage_location ? <button type="button" className="lab-location-badge lab-location-badge-button" onClick={(event) => { event.stopPropagation(); void openLocationPreview(order.storage_location!); }} title={`Mostrar ${order.storage_location} no mapa`}><MapPin size={14} />{order.storage_location}</button> : <span className="lab-location-empty">Sem posição</span>}</td><td>{order.entry_invoice || "—"}</td><td>{order.exit_invoice || "—"}</td><td>{warrantyCycles.some(({ entry, exit }) => Boolean(order[entry] || order[exit])) ? <div className="lab-warranty-nfs-list">{warrantyCycles.map(({ round, entry, exit }) => (order[entry] || order[exit]) ? <span key={round} title={`Garantia ${round}`}>G{round}: {order[entry] ? `E ${order[entry]}` : ""}{order[entry] && order[exit] ? " · " : ""}{order[exit] ? `S ${order[exit]}` : ""}</span> : null)}</div> : "—"}</td><td><div className="lab-status-stack"><span className={`lab-status ${order.status}`}>{statusLabel(order.status, workflowOptions)}</span>{order.is_inactive && <span className="lab-inactive-label">INATIVA</span>}{(order.substatuses ?? []).map((code) => <span key={code} className="lab-substatus-mini">{substatusLabel(code, workflowOptions)}</span>)}</div></td><td><span className={`lab-priority ${order.priority}`}>{priorityLabels[order.priority]}</span></td><td>{new Date(`${order.opened_at}T12:00:00`).toLocaleDateString("pt-BR")}</td>{canViewValues && <td>{currency(order.approved_value ?? order.quoted_value ?? "")}</td>}
            </tr>)}</tbody></table>
          {!filteredItems.length && <div className="lab-empty">Nenhuma ordem encontrada.</div>}
          <footer className="lab-pagination"><strong>{pageData.total} registro(s)</strong><div><button disabled={page <= 1} onClick={() => setPage(page - 1)}>Anterior</button><span>Página {page} de {pageData.pages || 1}</span><button disabled={page >= pageData.pages} onClick={() => setPage(page + 1)}>Próxima</button></div></footer>
        </section>
        </>}

        {view === "locations" && <LaboratoryLocationMapView
          data={locationMap}
          updatedAt={locationMapUpdatedAt}
          filter={locationFilter}
          setFilter={setLocationFilter}
          loading={loading}
          workflowOptions={workflowOptions}
          onRefresh={() => void loadLocationMap()}
          onOpenOrder={(id) => void openOrder(id)}
          onOpenLocation={(location) => void openLocationPreview(location)}
        />}

        {view === "technician_report" && (
          <TechnicianProductionReport onOpenOrder={(id) => void openOrder(id)} />
        )}
      </section>

      {locationPreview && locationMap && <LocationPreviewModal
        location={locationPreview}
        data={locationMap}
        workflowOptions={workflowOptions}
        onClose={() => setLocationPreview(null)}
        onOpenOrder={(id) => { setLocationPreview(null); void openOrder(id); }}
        onOpenFullMap={() => { setLocationPreview(null); setView("locations"); }}
      />}

      {showForm && <OrderForm form={form} setForm={setForm} companies={companies} locations={locationConfig.locations.filter((item) => item.is_active)} customers={customers} technicians={technicians} loading={loading} onSubmit={createWorkOrder} onClose={() => setShowForm(false)} />}
      {detail && <OrderDetail detail={detail} setDetail={setDetail} tab={detailTab} onTab={(nextTab) => void switchDetailTab(nextTab)} companies={companies} locations={locationConfig.locations.filter((item) => item.is_active)} customers={customers} technicians={technicians} history={history} locationHistory={locationHistory} workflowOptions={workflowOptions} loading={loading} saved={saved} canManageQuote={canManageQuote} canViewValues={canViewValues} onOpenReceivables={() => void openFinanceFromDetail()} onOpenReceivableEntry={(entryId) => void openFinanceFromDetail(entryId)} onLocationPreview={(location) => void openLocationPreview(location)} onSave={() => void saveDetail()} onInactivate={() => void inactivateSelected()} canInactivate={canManageQuote} onStatus={(status, note) => void changeStatus(status, false, note ?? "")} onSubstatus={(code, active) => void toggleSubstatus(code, active)} onClose={() => void closeDetail()} onInventoryChange={async () => {
        const updated = await apiClient.get<WorkOrder>(`/laboratory/work-orders/${detail.id}`);
        const refreshed = toDetail(updated);
        detailSavedFingerprintRef.current = detailFingerprint(refreshed, canViewValues);
        setDetail(refreshed);
        await load();
      }} />}
      {showSettings && <SettingsModal company={company === "all" ? (companies[0]?.company_code || "universo_eletronica") : company} companies={companies} locationConfig={locationConfig} customers={customers} technicians={technicians} workflowOptions={workflowOptions} tab={settingsTab} setTab={setSettingsTab} onClose={() => setShowSettings(false)} onSaved={async () => { await Promise.all([load(), loadMasterData()]); }} canManageTechnicians={canManageTechnicians} />}
    </main>
  );
}


function LocationPreviewModal({ location, data, workflowOptions, onClose, onOpenOrder, onOpenFullMap }: {
  location: string;
  data: LaboratoryLocationMap;
  workflowOptions: WorkflowOption[];
  onClose: () => void;
  onOpenOrder: (id: number) => void;
  onOpenFullMap: () => void;
}) {
  const slot = data.slots.find((item) => item.location === location);
  const siblings = slot?.rack_code
    ? data.slots.filter((item) => item.rack_code === slot.rack_code).sort((a, b) => a.slot_number - b.slot_number)
    : slot ? [slot] : [];
  return <div className="lab-location-preview-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
    <section className="lab-location-preview-modal" role="dialog" aria-modal="true" aria-label={`Localização ${location}`}>
      <header><div><p className="lab-eyebrow">LOCALIZAÇÃO FÍSICA</p><h3><MapPin size={21} /> {location}</h3></div><button type="button" className="lab-location-preview-close" onClick={onClose}>×</button></header>
      {slot ? <>
        <div className="lab-location-preview-summary">
          <div><span>Ala</span><strong>{slot.area_name}</strong></div>
          <div><span>Estante / área</span><strong>{slot.rack_name || "Área geral"}</strong></div>
          <div><span>Equipamentos</span><strong>{slot.occupancy_count}</strong></div>
          <div><span>Maior permanência</span><strong>{slot.occupancy_count ? formatLocationDwell(slot.max_location_duration_seconds) : "—"}</strong></div>
        </div>
        {siblings.length > 1 && <div className="lab-location-preview-rack"><div className="lab-rack-frame" style={{ gridTemplateColumns: `repeat(${slot.rack_columns || 1}, minmax(0,1fr))`, gridTemplateRows: `repeat(${slot.rack_rows || 1}, minmax(118px,1fr))` }}>{siblings.map((item) => <div key={item.location} className={`lab-rack-slot ${item.occupancy_count ? "occupied" : "free"} ${item.has_urgent ? "urgent" : ""} ${item.has_critical ? "dwell-critical" : item.has_attention ? "dwell-attention" : ""} ${item.location === location ? "focused" : ""}`}><span className="lab-rack-slot-code">{item.location}</span>{item.occupancy_count ? <><strong>{item.occupancy_count} equipamento(s)</strong><small>{item.occupants[0]?.work_order_number}</small>{item.occupancy_count > 1 && <em>+{item.occupancy_count - 1} nesta posição</em>}</> : <strong className="lab-rack-free-label">VAZIA</strong>}</div>)}</div></div>}
        <div className={`lab-location-preview-detail ${slot.occupancy_count ? "occupied" : "free"}`}>
          {slot.occupancy_count ? <><span>Equipamentos nesta localização</span><div className="lab-location-occupants">{slot.occupants.map((occupant) => <article key={occupant.work_order_id} className={`${occupant.priority === "urgent" ? "urgent" : ""} dwell-${occupant.dwell_level}`}><div><strong>{occupant.work_order_number}</strong><small>{occupant.equipment_label}</small><em>{occupant.customer_name} · {statusLabel(occupant.status as WorkOrderStatus, workflowOptions)}</em><span className={`lab-dwell-badge ${occupant.dwell_level}`}>{dwellLabel(occupant.dwell_level)} · {formatLocationDwell(occupant.location_duration_seconds)}</span></div><button type="button" onClick={() => onOpenOrder(occupant.work_order_id)}>Abrir O.S.</button></article>)}</div></> : <><span>Localização disponível</span><strong>{location} está sem equipamentos</strong></>}
        </div>
      </> : <div className="lab-empty">Localização não encontrada na estrutura física ativa.</div>}
      <footer><button type="button" className="lab-location-preview-full" onClick={onOpenFullMap}>Abrir mapa completo</button><button type="button" className="lab-location-preview-dismiss" onClick={onClose}>Fechar</button></footer>
    </section>
  </div>;
}

function formatLocationDwell(seconds: number) {
  const safe = Math.max(0, Math.floor(seconds || 0));
  const days = Math.floor(safe / 86400);
  const hours = Math.floor((safe % 86400) / 3600);
  if (days > 0) return `${days}d ${hours}h`;
  const minutes = Math.floor((safe % 3600) / 60);
  if (hours > 0) return `${hours}h ${minutes}min`;
  return `${minutes}min`;
}

function dwellLabel(level: "normal" | "attention" | "critical") {
  if (level === "critical") return "Crítico";
  if (level === "attention") return "Atenção";
  return "Normal";
}

function LaboratoryLocationMapView({ data, updatedAt, filter, setFilter, loading, workflowOptions, onRefresh, onOpenOrder, onOpenLocation }: {
  data: LaboratoryLocationMap | null;
  updatedAt: Date | null;
  filter: "all" | "occupied" | "free" | "urgent" | "attention" | "critical";
  setFilter: (value: "all" | "occupied" | "free" | "urgent" | "attention" | "critical") => void;
  loading: boolean;
  workflowOptions: WorkflowOption[];
  onRefresh: () => void;
  onOpenOrder: (id: number) => void;
  onOpenLocation: (location: string) => void;
}) {
  const [areaCode, setAreaCode] = useState<string>("");
  const matchesFilter = (slot: LaboratoryLocationMap["slots"][number]) => {
    if (filter === "occupied") return slot.occupancy_count > 0;
    if (filter === "free") return slot.occupancy_count === 0;
    if (filter === "urgent") return slot.has_urgent;
    if (filter === "attention") return slot.has_attention;
    if (filter === "critical") return slot.has_critical;
    return true;
  };
  const areas = data
    ? Array.from(new Map(
        [...data.slots]
          .sort((a,b) => a.area_sort_order - b.area_sort_order || a.area_name.localeCompare(b.area_name))
          .map((slot) => [slot.area_code, { code: slot.area_code, name: slot.area_name, sort: slot.area_sort_order }])
      ).values())
    : [];
  const selectedArea = areaCode && areas.some((item) => item.code === areaCode) ? areaCode : areas[0]?.code || "";
  const areaSlots = data?.slots.filter((slot) => slot.area_code === selectedArea) ?? [];
  const rackKeys = Array.from(new Set(areaSlots.filter((slot) => slot.rack_code).map((slot) => slot.rack_code as string)));
  const directSlots = areaSlots.filter((slot) => !slot.rack_code);

  return <section className="lab-location-map-page">
    <div className="lab-location-map-header"><div><p className="lab-eyebrow">RASTREABILIDADE FÍSICA</p><h2>Mapa de alas, estantes e equipamentos</h2><span>Estrutura configurável · múltiplos equipamentos podem compartilhar a mesma localização · permanência: normal até 3 dias, atenção de 4 a 7 dias e crítico a partir de 8 dias.</span><small className="lab-location-map-sync">{updatedAt ? `Atualizado às ${updatedAt.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit", second: "2-digit" })}` : "Aguardando sincronização"} · atualização automática a cada 10s</small></div><ActionButton variant="secondary" icon={<RefreshCw size={17} />} loading={loading} onClick={onRefresh}>Atualizar mapa</ActionButton></div>
    <div className="lab-location-map-kpis">
      <button className={filter === "all" ? "active" : ""} onClick={() => setFilter("all")}><span>Localizações</span><strong>{data?.total_positions ?? 0}</strong></button>
      <button className={filter === "occupied" ? "active" : ""} onClick={() => setFilter("occupied")}><span>Ocupadas</span><strong>{data?.occupied_positions ?? 0}</strong><small>{data?.located_work_orders ?? 0} equipamento(s)</small></button>
      <button className={filter === "free" ? "active" : ""} onClick={() => setFilter("free")}><span>Vazias</span><strong>{data?.free_positions ?? 0}</strong></button>
      <button className={filter === "urgent" ? "active" : ""} onClick={() => setFilter("urgent")}><span>Urgentes</span><strong>{data?.urgent_work_orders ?? 0}</strong></button>
      <button className={`attention ${filter === "attention" ? "active" : ""}`} onClick={() => setFilter("attention")}><span>Atenção 4–7 dias</span><strong>{data?.attention_work_orders ?? 0}</strong><small>{data?.attention_positions ?? 0} posição(ões)</small></button>
      <button className={`critical ${filter === "critical" ? "active" : ""}`} onClick={() => setFilter("critical")}><span>Críticos 8+ dias</span><strong>{data?.critical_work_orders ?? 0}</strong><small>{data?.critical_positions ?? 0} posição(ões)</small></button>
      <article><span>Sem localização</span><strong>{data?.work_orders_without_location ?? 0}</strong></article>
    </div>

    {areas.length > 0 && <div className="lab-area-tabs">{areas.map((area) => <button key={area.code} className={selectedArea === area.code ? "active" : ""} onClick={() => setAreaCode(area.code)}>{area.name}<small>{data?.slots.filter((slot) => slot.area_code === area.code).reduce((sum, slot) => sum + slot.occupancy_count, 0) ?? 0} equip.</small></button>)}</div>}

    {!data && <div className="lab-empty">{loading ? "Carregando mapa..." : "Mapa não carregado."}</div>}
    {data && <div className="lab-configurable-map">
      {directSlots.map((slot) => <button key={slot.location} className={`lab-area-location-card ${slot.occupancy_count ? "occupied" : "free"} ${slot.has_urgent ? "urgent" : ""} ${slot.has_critical ? "dwell-critical" : slot.has_attention ? "dwell-attention" : ""} ${!matchesFilter(slot) ? "filtered-out" : ""}`} onClick={() => onOpenLocation(slot.location)}>
        <span>{slot.location}</span><strong>{slot.area_name}</strong><small>{slot.occupancy_count} equipamento(s)</small>
        {slot.occupancy_count > 0 && <em>{slot.occupants.slice(0,3).map((item) => item.work_order_number).join(" · ")}{slot.occupancy_count > 3 ? ` · +${slot.occupancy_count - 3}` : ""}</em>}
      </button>)}
      {rackKeys.length > 0 && <div
        className="lab-configurable-racks lab-configurable-racks-layout"
        style={{ gridTemplateColumns: `repeat(${Math.max(2, ...areaSlots.filter((slot) => slot.rack_code).map((slot) => slot.rack_layout_column + slot.rack_layout_span - 1))}, minmax(280px, 1fr))` }}
      >
        {rackKeys.map((rackCode) => {
          const slots = areaSlots.filter((slot) => slot.rack_code === rackCode).sort((a,b) => a.slot_number - b.slot_number);
          const first = slots[0];
          const equipmentCount = slots.reduce((sum, slot) => sum + slot.occupancy_count, 0);
          if (!first) return null;
          return <article
            key={rackCode}
            className="lab-rack lab-rack-dynamic lab-rack-visual"
            style={{
              gridRow: first.rack_layout_row,
              gridColumn: `${first.rack_layout_column} / span ${first.rack_layout_span}`,
            }}
          >
            <header><div><span>{rackCode}</span><strong>{first.rack_name || rackCode}</strong></div><small>{equipmentCount} equipamento(s) · {slots.length} posições</small></header>
            <div className="lab-rack-visual-shell">
              <div className="lab-rack-top-beam" />
              <div className="lab-rack-frame" style={{ gridTemplateColumns: `repeat(${first.rack_columns || 2}, minmax(0,1fr))`, gridTemplateRows: `repeat(${first.rack_rows || 3}, minmax(112px,1fr))` }}>
                {slots.map((slot) => <button key={slot.location} type="button" className={`lab-rack-slot ${slot.occupancy_count ? "occupied" : "free"} ${slot.has_urgent ? "urgent" : ""} ${slot.has_critical ? "dwell-critical" : slot.has_attention ? "dwell-attention" : ""} ${!matchesFilter(slot) ? "filtered-out" : ""}`} onClick={() => onOpenLocation(slot.location)} title={`${slot.location} · ${slot.occupancy_count} equipamento(s)${slot.occupancy_count ? ` · maior permanência ${formatLocationDwell(slot.max_location_duration_seconds)}` : ""}`}><span className="lab-rack-slot-code">{slot.location}</span>{slot.occupancy_count ? <><strong>{slot.occupancy_count} equipamento(s)</strong><small>{slot.occupants[0]?.work_order_number}</small>{slot.occupancy_count > 1 && <em>+{slot.occupancy_count - 1} O.S.</em>}<span className="lab-rack-slot-status">{slot.has_urgent ? "Há urgente" : statusLabel(slot.occupants[0]?.status as WorkOrderStatus, workflowOptions)}</span></> : <strong className="lab-rack-free-label">LIVRE</strong>}</button>)}
              </div>
            </div>
          </article>;
        })}
      </div>}
    </div>}
  </section>;
}

function payloadFromForm(form: FormState, includeSensitiveValues: boolean) {
  const { parts_cost, quoted_value, approved_value, ...safeForm } = form;
  return {
    ...safeForm, customer_id: form.customer_id ? Number(form.customer_id) : null,
    assigned_technician_id: form.assigned_technician_id ? Number(form.assigned_technician_id) : null,
    serial_number: form.serial_number || null, manufacturer: form.manufacturer || null,
    model: form.model || null, equipment_type: form.equipment_type || null, power: form.power || null,
    voltage: form.voltage || null, entry_invoice: form.entry_invoice || null,
    entry_invoice_2: form.entry_invoice_2 || null, entry_invoice_3: form.entry_invoice_3 || null,
    entry_invoice_access_key: form.entry_invoice_access_key || null, exit_invoice: form.exit_invoice || null,
    exit_invoice_2: form.exit_invoice_2 || null, exit_invoice_3: form.exit_invoice_3 || null,
    exit_invoice_access_key: form.exit_invoice_access_key || null, warranty_invoice: form.warranty_invoice || null,
    warranty_invoice_2: form.warranty_invoice_2 || null, warranty_invoice_3: form.warranty_invoice_3 || null, warranty_entry_invoice_1: form.warranty_entry_invoice_1 || null, warranty_entry_invoice_2: form.warranty_entry_invoice_2 || null, warranty_entry_invoice_3: form.warranty_entry_invoice_3 || null, warranty_exit_invoice_1: form.warranty_exit_invoice_1 || null, warranty_exit_invoice_2: form.warranty_exit_invoice_2 || null, warranty_exit_invoice_3: form.warranty_exit_invoice_3 || null, storage_location: form.storage_location || null,
    entry_condition: form.entry_condition || null, accessories_received: form.accessories_received || null,
    internal_notes: form.internal_notes || null, customer_notes: form.customer_notes || null,
    ...(includeSensitiveValues ? {
      parts_cost: parts_cost || null, quoted_value: quoted_value || null, approved_value: approved_value || null,
    } : {}),
  };
}

function SidebarButton({ active, icon, children, onClick }: { active?: boolean; icon: React.ReactNode; children: React.ReactNode; onClick: () => void }) {
  return <button className={`lab-sidebar-button ${active ? "active" : ""}`} onClick={onClick}><span>{icon}</span><strong>{children}</strong></button>;
}

function detailFingerprint(detail: DetailState, includeSensitiveValues: boolean) {
  return JSON.stringify(payloadFromForm(detail, includeSensitiveValues));
}

type InvoiceField = "entry_invoice" | "exit_invoice";
type WarrantyInvoiceField = "warranty_entry_invoice_1" | "warranty_exit_invoice_1" | "warranty_entry_invoice_2" | "warranty_exit_invoice_2" | "warranty_entry_invoice_3" | "warranty_exit_invoice_3";

function StandardInvoices({ values, onChange }: { values: FormState; onChange: (field: InvoiceField, value: string) => void }) {
  return <section className="lab-standard-invoices" aria-label="Notas fiscais normais da ordem de serviço">
    <div className="lab-warranty-nfs-heading">
      <strong>Notas fiscais da OS</strong>
      <small>Entrada e saída do atendimento normal, independentes das notas de garantia.</small>
    </div>
    <div className="lab-grid">
      <Input label="NF de entrada" value={values.entry_invoice} onChange={(value) => onChange("entry_invoice", value)} />
      <Input label="NF de saída" value={values.exit_invoice} onChange={(value) => onChange("exit_invoice", value)} />
    </div>
  </section>;
}

const warrantyCycles: { round: number; entry: WarrantyInvoiceField; exit: WarrantyInvoiceField }[] = [
  { round: 1, entry: "warranty_entry_invoice_1", exit: "warranty_exit_invoice_1" },
  { round: 2, entry: "warranty_entry_invoice_2", exit: "warranty_exit_invoice_2" },
  { round: 3, entry: "warranty_entry_invoice_3", exit: "warranty_exit_invoice_3" },
];

function WarrantyInvoices({ values, onChange }: { values: FormState; onChange: (field: WarrantyInvoiceField, value: string) => void }) {
  return <section className="lab-invoice-cycles" aria-label="Garantia — três entradas e três saídas">
    <div className="lab-warranty-nfs-heading">
      <strong>Garantia — retornos do equipamento</strong>
      <small>Registre até três retornos de garantia. Cada entrada e saída pode ser preenchida separadamente, em qualquer data.</small>
    </div>
    <div className="lab-invoice-cycles-grid">
      {warrantyCycles.map(({ round, entry, exit }) => <div key={round} className="lab-invoice-cycle">
        <strong>Garantia {round}</strong>
        <div className="lab-grid">
          <Input label={`NF de entrada ${round}`} value={values[entry]} onChange={(value) => onChange(entry, value)} />
          <Input label={`NF de saída ${round}`} value={values[exit]} onChange={(value) => onChange(exit, value)} />
        </div>
      </div>)}
    </div>
  </section>;
}

// Dados já gravados nas versões 9/10 continuam visíveis, sem classificação automática como garantia.
function HistoricalInvoiceNotes({ values }: { values: FormState }) {
  const oldNotes = [
    { label: "NF adicional de entrada 2 (V10)", value: values.entry_invoice_2 },
    { label: "NF adicional de saída 2 (V10)", value: values.exit_invoice_2 },
    { label: "NF adicional de entrada 3 (V10)", value: values.entry_invoice_3 },
    { label: "NF adicional de saída 3 (V10)", value: values.exit_invoice_3 },
    { label: "NF de garantia 1 (V9)", value: values.warranty_invoice },
    { label: "NF de garantia 2 (V9)", value: values.warranty_invoice_2 },
    { label: "NF de garantia 3 (V9)", value: values.warranty_invoice_3 },
  ].filter(({ value }) => Boolean(value.trim()));
  if (!oldNotes.length) return null;
  return <details className="lab-invoice-history">
    <summary>Histórico de NFs cadastradas nas versões anteriores ({oldNotes.length})</summary>
    <p>Os dados abaixo foram preservados, mas não são classificados automaticamente como notas de garantia.</p>
    <dl>{oldNotes.map(({ label, value }) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>
  </details>;
}

function OrderForm({ form, setForm, companies, locations, customers, technicians, loading, onSubmit, onClose }: { form: FormState; setForm: (value: FormState) => void; companies: CompanyProfile[]; locations: LaboratoryLocationConfig["locations"]; customers: Customer[]; technicians: Technician[]; loading: boolean; onSubmit: (event: React.FormEvent, files: File[]) => void; onClose: () => void }) {
  const [entryFiles, setEntryFiles] = useState<File[]>([]);
  const [showCamera, setShowCamera] = useState(false);
  return <><div className="lab-modal"><form className="lab-form lab-form-wide" onSubmit={(event) => onSubmit(event, entryFiles)}>
    <header><div><p>ABERTURA CONTROLADA</p><h2><Plus size={24} /> Nova Ordem de Serviço</h2><small>O número será gerado automaticamente no formato OS-0001.</small></div><button type="button" onClick={onClose}><X /></button></header>
    <SectionTitle title="Identificação" />
    <div className="lab-grid three"><SelectCompany companies={companies} value={form.company_code} onChange={(value) => setForm({ ...form, company_code: value, customer_id: "", customer_name: "" })} /><label>Cliente *<select required value={form.customer_id} onChange={(e) => { const customer = customers.find((item) => item.id === Number(e.target.value)); setForm({ ...form, customer_id: e.target.value, customer_name: customer?.legal_name ?? "" }); }}><option value="">Selecione...</option>{customers.filter((item) => item.company_code === form.company_code).map((item) => <option key={item.id} value={item.id}>{item.legal_name}</option>)}</select></label><label>Técnico responsável<select value={form.assigned_technician_id} onChange={(e) => setForm({ ...form, assigned_technician_id: e.target.value })}><option value="">Não atribuído</option>{technicians.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label></div>
    <SectionTitle title="Equipamento" />
    <div className="lab-grid three"><Input label="Equipamento *" value={form.equipment_type} onChange={(value) => setForm({ ...form, equipment_type: value })} required /><Input label="Fabricante" value={form.manufacturer} onChange={(value) => setForm({ ...form, manufacturer: value })} /><Input label="Modelo" value={form.model} onChange={(value) => setForm({ ...form, model: value })} /><Input label="Número de série" value={form.serial_number} onChange={(value) => setForm({ ...form, serial_number: value })} /><Input label="Potência" value={form.power} onChange={(value) => setForm({ ...form, power: value })} /><Input label="Tensão" value={form.voltage} onChange={(value) => setForm({ ...form, voltage: value })} /></div>
    <SectionTitle title="Entrada e operação" />
    <StandardInvoices values={form} onChange={(field, value) => setForm({ ...form, [field]: value })} />
    <WarrantyInvoices values={form} onChange={(field, value) => setForm({ ...form, [field]: value })} />
    <div className="lab-grid three"><Input label="Chave NF entrada (44 dígitos)" value={form.entry_invoice_access_key} onChange={(value) => setForm({ ...form, entry_invoice_access_key: value })} /><Input label="Chave NF saída (44 dígitos)" value={form.exit_invoice_access_key} onChange={(value) => setForm({ ...form, exit_invoice_access_key: value })} /><Input label="Localização física (A1...F6)" value={form.storage_location} onChange={(value) => setForm({ ...form, storage_location: value.toUpperCase() })} /><label>Prioridade<select value={form.priority} onChange={(e) => setForm({ ...form, priority: e.target.value as Priority })}>{Object.entries(priorityLabels).map(([value,label]) => <option key={value} value={value}>{label}</option>)}</select></label></div>
    <label>Defeito informado *<textarea required rows={3} value={form.reported_defect} onChange={(e) => setForm({ ...form, reported_defect: e.target.value })} /></label>
    <div className="lab-grid"><label>Condição de entrada<textarea rows={3} value={form.entry_condition} onChange={(e) => setForm({ ...form, entry_condition: e.target.value })} /></label><label>Acessórios recebidos<textarea rows={3} value={form.accessories_received} onChange={(e) => setForm({ ...form, accessories_received: e.target.value })} /></label></div>
    <div className="lab-entry-upload-actions">
      <label className="lab-entry-upload">
        <UploadCloud size={24} />
        <div><strong>Adicionar fotos ou PDFs</strong><span>JPG, PNG, WEBP ou PDF · até 15 MB por arquivo</span></div>
        <input type="file" accept="image/jpeg,image/png,image/webp,application/pdf" multiple onChange={(event) => {
          const files = Array.from(event.target.files ?? []);
          setEntryFiles((current) => [...current, ...files]);
          event.currentTarget.value = "";
        }} />
      </label>
      <button type="button" className="lab-entry-upload lab-entry-camera" onClick={() => setShowCamera(true)}>
        <Camera size={24} />
        <div><strong>Tirar foto</strong><span>Abre a câmera do dispositivo e captura a imagem no próprio SÊNTICO.</span></div>
      </button>
    </div>
    {entryFiles.length > 0 && <div className="lab-entry-files">{entryFiles.map((file, index) => <span key={`${file.name}-${file.size}-${index}`}>{file.name}</span>)}</div>}
    <footer><ActionButton type="button" variant="secondary" icon={<X size={17} />} onClick={onClose}>Cancelar</ActionButton><ActionButton type="submit" loading={loading} icon={<Save size={17} />}>Cadastrar e gerar O.S.</ActionButton></footer>
  </form></div>
  {showCamera && <CameraCapture title="Foto de entrada" onClose={() => setShowCamera(false)} onCapture={(file) => { setEntryFiles((current) => [...current, file]); setShowCamera(false); }} />}
  </>;
}

/** Saldo e parcelas são consultados no Financeiro pelo ID da OS, sem filtro de período. */
function OrderReceivablesPanel({ workOrderId, onOpenReceivables, onOpenEntry }: {
  workOrderId: number;
  onOpenReceivables: () => void;
  onOpenEntry: (entryId: number) => void;
}) {
  const [data, setData] = useState<WorkOrderReceivables | null>(null);
  const [message, setMessage] = useState("");
  useEffect(() => {
    let active = true;
    setData(null); setMessage("");
    apiClient.get<WorkOrderReceivables>(`/finance/work-orders/${workOrderId}/receivables`)
      .then((response) => { if (active) setData(response); })
      .catch((reason: Error) => { if (active) setMessage(`Não foi possível consultar as receitas: ${reason.message}`); });
    return () => { active = false; };
  }, [workOrderId]);
  return <section className="lab-order-receivables">
    <header><div><span>CONTAS A RECEBER</span><h3>Receitas e pagamentos vinculados à OS</h3><p>Parcelas de todos os meses, com recebimentos e valores ainda pendentes.</p></div><button type="button" onClick={onOpenReceivables}>Abrir em Receitas</button></header>
    {message && <p className="lab-order-receivables-error">{message}</p>}
    {!data && !message && <p>Consultando receitas vinculadas…</p>}
    {data && <>
      <div className="lab-order-receivables-totals"><span>Lançado<strong>{currency(String(data.total_registered))}</strong></span><span>Recebido<strong>{currency(String(data.total_received))}</strong></span><span>A receber<strong>{currency(String(data.total_pending))}</strong></span><span>Falta lançar<strong>{data.remaining_to_issue == null ? "Sem valor aprovado" : currency(String(data.remaining_to_issue))}</strong></span></div>
      <div className="lab-order-receivables-items">
        {data.installments.map((item) => <button key={item.id} type="button" onClick={() => onOpenEntry(item.id)}><b>{item.obligation_id ? `Parcela ${item.installment_number}` : "Receita avulsa"}</b><span>Vence {new Date(`${item.due_date}T12:00:00`).toLocaleDateString("pt-BR")}</span><strong>{currency(String(item.amount))}</strong><em className={item.status === "received" ? "received" : "pending"}>{item.status === "received" ? "Recebido" : "Pendente"}</em></button>)}
        {!data.installments.length && <p>Nenhuma receita cadastrada para esta OS.</p>}
      </div>
      {data.remaining_to_issue !== null && Number(data.remaining_to_issue) < 0 && <p className="lab-order-receivables-error">O total lançado supera o valor aprovado. Confira os títulos vinculados antes de criar novos.</p>}
    </>}
  </section>;
}

function OrderDetail({ detail, setDetail, tab, onTab, companies, locations, customers, technicians, history, locationHistory, workflowOptions, loading, saved, canManageQuote, canViewValues, onLocationPreview, onSave, onInactivate, canInactivate, onStatus, onSubstatus, onClose, onInventoryChange, onOpenReceivables, onOpenReceivableEntry }: { detail: DetailState; setDetail: (value: DetailState) => void; tab: DetailTab; onTab: (value: DetailTab) => void; companies: CompanyProfile[]; locations: LaboratoryLocationConfig["locations"]; customers: Customer[]; technicians: Technician[]; history: StatusHistory[]; locationHistory: LocationHistory[]; workflowOptions: WorkflowOption[]; loading: boolean; saved: boolean; canManageQuote: boolean; canViewValues: boolean; onLocationPreview: (location: string) => void; onSave: () => void; onInactivate: () => void; canInactivate: boolean; onStatus: (status: WorkOrderStatus, note?: string) => void; onSubstatus: (code: string, active: boolean) => void; onClose: () => void; onInventoryChange:()=>Promise<void>; onOpenReceivables: () => void; onOpenReceivableEntry: (entryId: number) => void }) {
  const [targetStatus, setTargetStatus] = useState<WorkOrderStatus | "">("");
  const configuredBusinessStatuses = workflowOptions
    .filter((item) => item.kind === "status" && item.is_active)
    .sort((a, b) => a.sort_order - b.sort_order || a.id - b.id)
    .map((item) => ({ value: item.code, label: item.label }));
  const visibleBusinessStatuses = businessStatusOptions.filter((item) => item.value !== detail.status);
  const visibleOperationalStatuses = operationalStatusOptions.filter((item) => item.value !== detail.status);
  const substatusOptions = workflowOptions
    .filter((item) => item.kind === "substatus" && item.is_active)
    .sort((a, b) => a.sort_order - b.sort_order || a.id - b.id);

  useEffect(() => {
    setTargetStatus("");
  }, [detail.id, detail.status]);

  return <div className="lab-modal lab-modal-top"><section className="lab-detail">
    <header className="lab-detail-header"><div><p className="lab-eyebrow">DETALHE DA O.S.</p><h2>{detail.number}</h2><span>{detail.customer_name} · {detail.equipment_type || detail.model || "Equipamento"}</span><div className="lab-detail-badges"><span className={`lab-status ${detail.status}`}>{statusLabel(detail.status, workflowOptions)}</span>{detail.substatuses.map((code) => <span key={code} className="lab-substatus-mini">{substatusLabel(code, workflowOptions)}</span>)}<span className={`lab-priority ${detail.priority}`}>{priorityLabels[detail.priority]}</span></div></div><div className="lab-detail-header-actions">{canViewValues && <button type="button" className="lab-receipts-link" disabled={loading} onClick={onOpenReceivables}><BadgeDollarSign size={16}/> Ver receitas / parcelas</button>}{canInactivate && !detail.is_inactive && <button type="button" className="lab-inactivate-action" disabled={loading} onClick={onInactivate}><Trash2 size={16}/> Inativar OS</button>}{detail.is_inactive && <span className="lab-inactive-label">OS INATIVADA</span>}<ActionButton variant="secondary" icon={<Printer size={17}/>} onClick={() => window.open(`/api/laboratory/work-orders/${detail.id}/label.pdf`, "_blank", "noopener,noreferrer")}>Emitir etiqueta</ActionButton><button className="lab-close-button" disabled={loading} onClick={onClose}><X /></button></div></header>
    <nav className="lab-detail-tabs">
      <TabButton active={tab === "general"} disabled={loading} icon={<Pencil size={16} />} onClick={() => onTab("general")}>Edição completa</TabButton>
      <TabButton active={tab === "technical"} disabled={loading} icon={<Wrench size={16} />} onClick={() => onTab("technical")}>Dados técnicos</TabButton>
      {canViewValues && <TabButton active={tab === "financial"} disabled={loading} icon={<BadgeDollarSign size={16} />} onClick={() => onTab("financial")}>Valores</TabButton>}
      <TabButton active={tab === "materials"} disabled={loading} icon={<Wrench size={16} />} onClick={() => onTab("materials")}>Materiais</TabButton>
      <TabButton active={tab === "status"} disabled={loading} icon={<ClipboardList size={16} />} onClick={() => onTab("status")}>Status</TabButton>
      <TabButton active={tab === "documents"} disabled={loading} icon={<Image size={16} />} onClick={() => onTab("documents")}>Fotos</TabButton>
      <TabButton active={tab === "quote"} disabled={loading} icon={<FileText size={16} />} onClick={() => onTab("quote")}>Orçamento</TabButton>
      <TabButton active={tab === "mechanics"} disabled={loading} icon={<Wrench size={16} />} onClick={() => onTab("mechanics")}>Mecânica</TabButton>
      <TabButton active={tab === "history"} disabled={loading} icon={<History size={16} />} onClick={() => onTab("history")}>Histórico</TabButton>
    </nav>
    <fieldset disabled={loading || detail.is_inactive} style={{ border: 0, margin: 0, padding: 0, minWidth: 0 }}>
    <div className="lab-detail-content">
      {tab === "general" && <><SectionTitle title="Cliente e documentos" /><div className="lab-grid"><label>Cliente<select value={detail.customer_id} onChange={(e) => { const customer = customers.find((item) => item.id === Number(e.target.value)); setDetail({ ...detail, customer_id: e.target.value, customer_name: customer?.legal_name ?? detail.customer_name }); }}><option value="">Selecione...</option>{customers.filter((item) => item.company_code === detail.company_code).map((item) => <option key={item.id} value={item.id}>{item.legal_name}</option>)}</select></label><SelectCompany companies={companies} value={detail.company_code} onChange={(value) => setDetail({ ...detail, company_code: value, customer_id: "", customer_name: "" })} /></div><StandardInvoices values={detail} onChange={(field, value) => setDetail({ ...detail, [field]: value })} /><WarrantyInvoices values={detail} onChange={(field, value) => setDetail({ ...detail, [field]: value })} /><HistoricalInvoiceNotes values={detail} /><div className="lab-grid"><Input label="Chave NF entrada (44 dígitos)" value={detail.entry_invoice_access_key} onChange={(value) => setDetail({ ...detail, entry_invoice_access_key: value })} /><Input label="Chave NF saída (44 dígitos)" value={detail.exit_invoice_access_key} onChange={(value) => setDetail({ ...detail, exit_invoice_access_key: value })} /></div><div className="lab-location-editor"><div className="lab-location-field"><SelectLocation locations={locations} value={detail.storage_location} onChange={(value) => setDetail({ ...detail, storage_location: value })} />{detail.storage_location && <button type="button" className="lab-location-current lab-location-current-button" onClick={() => onLocationPreview(detail.storage_location)} title="Mostrar esta posição no mapa"><MapPin size={15} /> Posição atual: <strong>{detail.storage_location}</strong><span>Ver no mapa</span></button>}</div><div className="lab-location-actions"><button type="button" className="lab-location-suggest" onClick={async()=>{const result=await apiClient.get<{location:string}>("/laboratory/locations/next");setDetail({...detail,storage_location:result.location});}}>Sugerir melhor posição</button><button type="button" className="lab-location-release" disabled={!detail.storage_location} onClick={()=>setDetail({...detail,storage_location:""})}>Liberar posição</button></div><small className="lab-location-help">A localização é física e independente do status. Mais de uma O.S. pode compartilhar a mesma posição; a sugestão prioriza os espaços menos carregados.</small></div><label>Defeito informado<textarea rows={4} value={detail.reported_defect} onChange={(e) => setDetail({ ...detail, reported_defect: e.target.value })} /></label><div className="lab-grid"><label>Condição de entrada<textarea rows={4} value={detail.entry_condition} onChange={(e) => setDetail({ ...detail, entry_condition: e.target.value })} /></label><label>Acessórios recebidos<textarea rows={4} value={detail.accessories_received} onChange={(e) => setDetail({ ...detail, accessories_received: e.target.value })} /></label></div></>}
      {tab === "technical" && <><SectionTitle title="Informações do equipamento" /><div className="lab-grid three"><Input label="Equipamento" value={detail.equipment_type} onChange={(value) => setDetail({ ...detail, equipment_type: value })} /><Input label="Fabricante" value={detail.manufacturer} onChange={(value) => setDetail({ ...detail, manufacturer: value })} /><Input label="Modelo" value={detail.model} onChange={(value) => setDetail({ ...detail, model: value })} /><Input label="Número de série" value={detail.serial_number} onChange={(value) => setDetail({ ...detail, serial_number: value })} /><Input label="Potência" value={detail.power} onChange={(value) => setDetail({ ...detail, power: value })} /><Input label="Tensão" value={detail.voltage} onChange={(value) => setDetail({ ...detail, voltage: value })} /></div><label>Observações internas<textarea rows={6} value={detail.internal_notes} onChange={(e) => setDetail({ ...detail, internal_notes: e.target.value })} /></label></>}
      {canViewValues && tab === "financial" && <><SectionTitle title="Custos e valores" /><div className="lab-grid three"><Input label="Valor de peças (R$)" value={detail.parts_cost} onChange={(value) => setDetail({ ...detail, parts_cost: value })} /><Input label="Valor orçado (R$)" value={detail.quoted_value} onChange={(value) => setDetail({ ...detail, quoted_value: value })} /><Input label="Valor aprovado (R$)" value={detail.approved_value} onChange={(value) => setDetail({ ...detail, approved_value: value })} /></div><div className="lab-financial-summary"><span>Custo de peças<strong>{currency(detail.parts_cost)}</strong></span><span>Orçamento<strong>{currency(detail.quoted_value)}</strong></span><span>Valor aprovado<strong>{currency(detail.approved_value)}</strong></span></div><OrderReceivablesPanel workOrderId={detail.id} onOpenReceivables={onOpenReceivables} onOpenEntry={onOpenReceivableEntry} /></>}
      {tab === "materials" && <MaterialsPanel workOrderId={detail.id} onInventoryChange={onInventoryChange} />}
      {tab === "status" && <><SectionTitle title="Execução e responsabilidade" /><div className="lab-grid"><label>Técnico responsável<select value={detail.assigned_technician_id} onChange={(e) => setDetail({ ...detail, assigned_technician_id: e.target.value })}><option value="">Não atribuído</option>{technicians.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label>Prioridade<select value={detail.priority} onChange={(e) => setDetail({ ...detail, priority: e.target.value as Priority })}>{Object.entries(priorityLabels).map(([value,label]) => <option key={value} value={value}>{label}</option>)}</select></label></div><div className="lab-status-panel lab-status-workflow"><div className="lab-status-current"><span>Status atual</span><strong>{statusLabel(detail.status, workflowOptions)}</strong></div><label>Novo status<select value={targetStatus} disabled={loading} onChange={(e) => setTargetStatus(e.target.value as WorkOrderStatus | "")}><option value="">Selecione o status...</option>{visibleBusinessStatuses.length > 0 && <optgroup label="Status principais">{visibleBusinessStatuses.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</optgroup>}{visibleOperationalStatuses.length > 0 && <optgroup label="Etapas operacionais">{visibleOperationalStatuses.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</optgroup>}</select><small>Status livre para a operação: qualquer usuário do Laboratório pode alterar para qualquer status ativo. Toda mudança continua registrada no histórico.</small></label><ActionButton loading={loading} disabled={!targetStatus} icon={<RefreshCw size={17} />} onClick={() => { if (targetStatus) onStatus(targetStatus, `Status alterado manualmente de ${statusLabel(detail.status, workflowOptions)} para ${statusLabel(targetStatus, workflowOptions)}.`); }}>Aplicar status</ActionButton></div>{substatusOptions.length > 0 && <div className="lab-substatus-box"><div><strong>Sinalizadores / substatus</strong><span>Marque informações complementares sem criar novos status principais.</span></div><div className="lab-substatus-grid">{substatusOptions.map((item) => { const checked = detail.substatuses.includes(item.code); return <label key={item.id} className={checked ? "active" : ""}><input type="checkbox" checked={checked} disabled={loading} onChange={(event) => onSubstatus(item.code, event.target.checked)} /><span>{item.label}</span></label>; })}</div></div>}</>}
      {tab === "documents" && <EquipmentDocumentsPanel workOrderId={detail.id} />}
      {tab === "quote" && <QuoteEditor
        workOrderId={detail.id} workOrderNumber={detail.number} customerName={detail.customer_name}
        equipmentType={detail.equipment_type} manufacturer={detail.manufacturer} model={detail.model}
        serialNumber={detail.serial_number} power={detail.power} voltage={detail.voltage}
        defect={detail.reported_defect} quotedValue={canViewValues ? detail.quoted_value : ""} readOnly={!canManageQuote}
      />}
      {tab === "mechanics" && <MechanicsPanel workOrderId={detail.id} />}
      {tab === "history" && <div className="lab-history-grid">
        <section className="lab-history-card">
          <SectionTitle title="Movimentação física" />
          <div className="lab-timeline lab-location-timeline">
            {locationHistory.map((item) => <article key={item.id} className={item.is_current ? "current" : ""}><span className="lab-timeline-dot" /><div><strong>{item.location}{item.is_current ? " · atual" : ""}</strong><p>{item.is_current ? "Equipamento permanece nesta localização." : "Permanência concluída nesta localização."}</p><small>{item.changed_by_name} · entrada em {new Date(item.assigned_at).toLocaleString("pt-BR")} · permanência {formatDuration(item.duration_seconds)}</small></div></article>)}
            {!locationHistory.length && <div className="lab-empty">Nenhuma movimentação física registrada.</div>}
          </div>
        </section>
        <section className="lab-history-card">
          <SectionTitle title="Histórico de status" />
          <div className="lab-timeline">{history.map((item) => <article key={item.id}><span className="lab-timeline-dot" /><div><strong>{statusLabel(item.new_status, workflowOptions)}</strong><p>{item.note || "Alteração de status."}</p>{item.new_status === "awaiting_pickup" && <p><strong>Técnico responsável:</strong> {item.release_technician_name || "Sem técnico atribuído no momento da liberação"}</p>}<small>{item.new_status === "awaiting_pickup" ? "Alteração realizada por: " : ""}{item.user_name} · {new Date(item.created_at).toLocaleString("pt-BR")}</small></div></article>)}{!history.length && <div className="lab-empty">Nenhum evento de status registrado.</div>}</div>
        </section>
      </div>}
    </div>
    </fieldset>
    <footer className="lab-detail-footer"><ActionButton disabled={loading} variant="secondary" icon={<X size={17} />} onClick={onClose}>Fechar</ActionButton><ActionButton loading={loading} success={saved} icon={<Save size={17} />} onClick={onSave}>{saved ? "Salvo" : "Salvar alterações"}</ActionButton></footer>
  </section></div>;
}

function SettingsModal({ company, companies, locationConfig, customers, technicians, workflowOptions, tab, setTab, onClose, onSaved, canManageTechnicians }: { company: CompanyCode; companies: CompanyProfile[]; locationConfig: LaboratoryLocationConfig; customers: Customer[]; technicians: Technician[]; workflowOptions: WorkflowOption[]; tab: SettingsTab; setTab: (value: SettingsTab) => void; onClose: () => void; onSaved: () => Promise<void>; canManageTechnicians: boolean }) {
  const [customerName, setCustomerName] = useState("");
  const [customerDocument, setCustomerDocument] = useState("");
  const [technicianName, setTechnicianName] = useState("");
  const [specialty, setSpecialty] = useState("");
  const [editingTechnicianId, setEditingTechnicianId] = useState<number | null>(null);
  const [workflowRows, setWorkflowRows] = useState<WorkflowOption[]>(workflowOptions);
  const [workflowKind, setWorkflowKind] = useState<"status" | "substatus">("status");
  const [workflowLabel, setWorkflowLabel] = useState("");
  const [workflowOrder, setWorkflowOrder] = useState("10");
  const [editingWorkflowId, setEditingWorkflowId] = useState<number | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);

  async function loadWorkflowRows() {
    const rows = await apiClient.get<WorkflowOption[]>("/laboratory/workflow-options?include_inactive=true");
    setWorkflowRows(rows);
  }

  useEffect(() => {
    if (tab === "workflow") void loadWorkflowRows();
  }, [tab]);

  function clearTechnicianEditor() {
    setEditingTechnicianId(null);
    setTechnicianName("");
    setSpecialty("");
  }

  function editTechnician(technician: Technician) {
    setEditingTechnicianId(technician.id);
    setTechnicianName(technician.name);
    setSpecialty(technician.specialty ?? "");
  }

  function clearWorkflowEditor() {
    setEditingWorkflowId(null);
    setWorkflowKind("status");
    setWorkflowLabel("");
    setWorkflowOrder("10");
  }

  function editWorkflow(item: WorkflowOption) {
    setEditingWorkflowId(item.id);
    setWorkflowKind(item.kind);
    setWorkflowLabel(item.label);
    setWorkflowOrder(String(item.sort_order));
  }

  async function refreshAfterSettingsChange() {
    await onSaved();
    if (tab === "workflow") await loadWorkflowRows();
  }

  async function saveCadastro() {
    setSaving(true);
    try {
      if (tab === "customers") {
        await apiClient.post("/laboratory/customers", {
          company_code: company,
          legal_name: customerName,
          document: customerDocument || null,
        });
        setCustomerName("");
        setCustomerDocument("");
      } else if (tab === "workflow") {
        if (!workflowLabel.trim()) return;
        const sortOrder = Math.max(0, Number(workflowOrder) || 0);
        if (editingWorkflowId) {
          const current = workflowRows.find((item) => item.id === editingWorkflowId);
          await apiClient.put(`/laboratory/workflow-options/${editingWorkflowId}`, {
            label: workflowLabel.trim(),
            sort_order: sortOrder,
            is_active: current?.is_active ?? true,
          });
        } else {
          await apiClient.post("/laboratory/workflow-options", {
            kind: workflowKind,
            label: workflowLabel.trim(),
            sort_order: sortOrder,
          });
        }
        clearWorkflowEditor();
      } else if (editingTechnicianId) {
        const current = technicians.find((item) => item.id === editingTechnicianId);
        await apiClient.put(`/laboratory/technicians/${editingTechnicianId}`, {
          name: technicianName,
          specialty: specialty || null,
          phone: current?.phone ?? null,
          email: current?.email ?? null,
          color: current?.color ?? null,
        });
        clearTechnicianEditor();
      } else {
        await apiClient.post("/laboratory/technicians", {
          company_code: company,
          name: technicianName,
          specialty: specialty || null,
        });
        clearTechnicianEditor();
      }
      await refreshAfterSettingsChange();
    } finally {
      setSaving(false);
    }
  }

  async function deactivate(kind: "customers" | "technicians", id: number) {
    setBusyId(id);
    try {
      await apiClient.delete(`/laboratory/${kind}/${id}`);
      if (editingTechnicianId === id) clearTechnicianEditor();
      await refreshAfterSettingsChange();
    } finally {
      setBusyId(null);
    }
  }

  async function setWorkflowActive(item: WorkflowOption, isActive: boolean) {
    setBusyId(item.id);
    try {
      await apiClient.put(`/laboratory/workflow-options/${item.id}`, {
        label: item.label,
        sort_order: item.sort_order,
        is_active: isActive,
      });
      if (!isActive && editingWorkflowId === item.id) clearWorkflowEditor();
      await refreshAfterSettingsChange();
    } finally {
      setBusyId(null);
    }
  }

  const heading = tab === "customers"
    ? ["Cadastro de clientes", "Razão social, documento e vínculos com as ordens de serviço."]
    : tab === "technicians"
      ? [editingTechnicianId ? "Editar técnico" : "Cadastro de técnicos", "Equipe técnica, especialidade e disponibilidade operacional."]
      : tab === "workflow"
        ? [editingWorkflowId ? "Editar status / substatus" : "Workflow do laboratório", "Defina status principais e sinalizadores sem apagar o histórico existente."]
        : tab === "companies"
          ? ["Empresas emissoras", "Cadastre e atualize os dados usados nas O.S. e nos orçamentos."]
          : ["Estrutura física", "Configure alas, estantes e posições sem alterar código."];

  return <div className="lab-modal"><section className="lab-settings professional">
    <header><div><p>CONFIGURAÇÕES</p><h2>Central de cadastros</h2><span>Administre clientes, técnicos e o workflow do Laboratório preservando o histórico.</span></div><button onClick={onClose}><X /></button></header>
    <div className="lab-settings-layout">
      <nav>
        <TabButton active={tab === "customers"} icon={<Users size={17} />} onClick={() => setTab("customers")}>Clientes <small>{customers.length}</small></TabButton>
        <TabButton active={tab === "technicians"} icon={<UserRoundCog size={17} />} onClick={() => setTab("technicians")}>Técnicos <small>{technicians.length}</small></TabButton>
        <TabButton active={tab === "workflow"} icon={<ClipboardList size={17} />} onClick={() => setTab("workflow")}>Status e substatus <small>{workflowRows.filter((item) => item.is_active).length}</small></TabButton>
        <TabButton active={tab === "companies"} icon={<ShieldCheck size={17} />} onClick={() => setTab("companies")}>Empresas <small>{companies.filter((item) => item.is_active).length}</small></TabButton>
        <TabButton active={tab === "locations"} icon={<Layers3 size={17} />} onClick={() => setTab("locations")}>Alas e estantes <small>{locationConfig.areas.filter((item) => item.is_active).length}</small></TabButton>
      </nav>
      <div className="lab-settings-main">
        <div className="lab-settings-heading">
          <div><h3>{heading[0]}</h3><p>{heading[1]}</p></div>
          <div className="lab-settings-heading-actions">
            {tab === "technicians" && editingTechnicianId && canManageTechnicians && <ActionButton variant="secondary" icon={<X size={16} />} onClick={clearTechnicianEditor}>Cancelar edição</ActionButton>}
            {tab === "workflow" && editingWorkflowId && canManageTechnicians && <ActionButton variant="secondary" icon={<X size={16} />} onClick={clearWorkflowEditor}>Cancelar edição</ActionButton>}
            {(tab === "customers" || ((tab === "technicians" || tab === "workflow") && canManageTechnicians)) && <ActionButton loading={saving} icon={(editingTechnicianId || editingWorkflowId) ? <Save size={17} /> : <Plus size={17} />} onClick={() => void saveCadastro()}>{(editingTechnicianId || editingWorkflowId) ? "Salvar" : "Cadastrar"}</ActionButton>}
          </div>
        </div>

        {tab === "customers" && <div className="lab-settings-form"><Input label="Razão social / cliente" value={customerName} onChange={setCustomerName} /><Input label="CNPJ/CPF" value={customerDocument} onChange={setCustomerDocument} /></div>}
        {tab === "technicians" && (canManageTechnicians ? <div className="lab-settings-form"><Input label="Nome do técnico" value={technicianName} onChange={setTechnicianName} /><Input label="Especialidade" value={specialty} onChange={setSpecialty} /></div> : <div className="lab-alert">Técnicos podem ser consultados aqui. Cadastro, edição e inativação são restritos a ADM/Gestão.</div>)}
        {(tab === "companies" || tab === "locations") && <ConfigMasterPanel
          mode={tab}
          companies={companies}
          locationConfig={locationConfig}
          canManage={canManageTechnicians}
          onChanged={onSaved}
        />}

        {tab === "workflow" && (canManageTechnicians ? <div className="lab-settings-form lab-workflow-form">
          <label>Tipo<select value={workflowKind} disabled={editingWorkflowId !== null} onChange={(e) => setWorkflowKind(e.target.value as "status" | "substatus")}><option value="status">Status principal</option><option value="substatus">Substatus / sinalizador</option></select></label>
          <Input label="Nome exibido" value={workflowLabel} onChange={setWorkflowLabel} />
          <Input label="Ordem" value={workflowOrder} onChange={setWorkflowOrder} />
        </div> : <div className="lab-alert">Status e substatus podem ser consultados aqui. Alterações são restritas a ADM/Gestão.</div>)}

        {(tab !== "companies" && tab !== "locations") && <div className="lab-settings-list">
          {tab === "customers" && customers.map((item) => <article key={item.id}>
            <div className="lab-avatar">{item.legal_name.slice(0,2).toUpperCase()}</div>
            <div className="lab-settings-item-copy"><strong>{item.legal_name}</strong><span>{item.document || "Sem documento"}</span></div>
            <ActionButton variant="danger" loading={busyId === item.id} icon={<Trash2 size={16} />} onClick={() => void deactivate("customers", item.id)}>Inativar</ActionButton>
          </article>)}
          {tab === "technicians" && technicians.map((item) => <article key={item.id}>
            <div className="lab-avatar">{item.name.slice(0,2).toUpperCase()}</div>
            <div className="lab-settings-item-copy"><strong>{item.name}</strong><span>{item.specialty || "Sem especialidade"}</span></div>
            {canManageTechnicians && <div className="lab-settings-row-actions">
              <ActionButton variant="secondary" icon={<Pencil size={16} />} onClick={() => editTechnician(item)}>Editar</ActionButton>
              <ActionButton variant="danger" loading={busyId === item.id} icon={<Trash2 size={16} />} onClick={() => void deactivate("technicians", item.id)}>Inativar</ActionButton>
            </div>}
          </article>)}
          {tab === "workflow" && [...workflowRows].sort((a,b) => a.kind.localeCompare(b.kind) || a.sort_order - b.sort_order || a.id - b.id).map((item) => <article key={item.id} className={!item.is_active ? "inactive" : ""}>
            <div className="lab-avatar">{item.kind === "status" ? "ST" : "SB"}</div>
            <div className="lab-settings-item-copy"><strong>{item.label}</strong><span>{item.kind === "status" ? "Status principal" : "Substatus / sinalizador"} · ordem {item.sort_order}{item.is_system ? " · padrão do sistema" : " · personalizado"}{!item.is_active ? " · inativo" : ""}</span></div>
            {canManageTechnicians && <div className="lab-settings-row-actions">
              <ActionButton variant="secondary" icon={<Pencil size={16} />} onClick={() => editWorkflow(item)}>Editar</ActionButton>
              {item.is_active
                ? <ActionButton variant="danger" loading={busyId === item.id} icon={<Trash2 size={16} />} onClick={() => void setWorkflowActive(item, false)}>Remover</ActionButton>
                : <ActionButton loading={busyId === item.id} icon={<RefreshCw size={16} />} onClick={() => void setWorkflowActive(item, true)}>Reativar</ActionButton>}
            </div>}
          </article>)}
        </div>}
      </div>
    </div>
  </section></div>;
}

function TabButton({ active, icon, children, onClick, disabled = false }: { active: boolean; icon: React.ReactNode; children: React.ReactNode; onClick: () => void; disabled?: boolean }) { return <button className={`lab-tab-button ${active ? "active" : ""}`} disabled={disabled} onClick={onClick}>{icon}<span>{children}</span></button>; }
function SectionTitle({ title }: { title: string }) { return <div className="lab-section-title"><span>{title}</span></div>; }
function Input({ label, value, onChange, required = false }: { label: string; value: string; onChange: (value: string) => void; required?: boolean }) { return <label>{label}<input required={required} value={value} onChange={(e) => onChange(e.target.value)} /></label>; }
function SelectCompany({ companies, value, onChange }: { companies: CompanyProfile[]; value: CompanyCode; onChange: (value: CompanyCode) => void }) { return <label>Empresa emissora<select value={value} onChange={(e) => onChange(e.target.value)}>{companies.map((item) => <option key={item.id} value={item.company_code} disabled={!item.is_active && item.company_code !== value}>{item.trade_name || item.legal_name}{!item.is_active ? " (inativa)" : ""}</option>)}</select></label>; }
function SelectLocation({ locations, value, onChange }: { locations: LaboratoryLocationConfig["locations"]; value: string; onChange: (value: string) => void }) {
  const listId = useId();
  const activeLocations = locations.filter((item) => item.is_active);
  const normalized = value.trim().toUpperCase();
  const exists = !normalized || activeLocations.some((item) => item.code === normalized);
  return <label className="lab-location-combobox">
    Localização física
    <input
      list={listId}
      value={value}
      placeholder="Digite A2, LAB, MEC... ou selecione"
      onChange={(e) => onChange(e.target.value.toUpperCase().replace(/\s+/g, ""))}
      aria-invalid={!exists}
    />
    <datalist id={listId}>
      {activeLocations
        .sort((a,b) => a.area_name.localeCompare(b.area_name) || (a.rack_name || "").localeCompare(b.rack_name || "") || a.sort_order - b.sort_order)
        .map((item) => <option key={item.id} value={item.code}>{item.area_name} · {item.rack_name || item.name}</option>)}
    </datalist>
    <small className={exists ? "lab-location-combobox-help" : "lab-location-combobox-help invalid"}>
      {exists ? "Digite o código diretamente ou escolha uma localização cadastrada." : "Código ainda não corresponde a uma localização ativa cadastrada."}
    </small>
  </label>;
}

function formatDuration(totalSeconds: number) {
  const seconds = Math.max(0, Math.floor(totalSeconds));
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  if (days > 0) return `${days}d ${hours}h`;
  if (hours > 0) return `${hours}h ${minutes}min`;
  return `${minutes}min`;
}

function currency(value: string) { const number = Number(String(value || "0").replace(",", ".")); return Number.isFinite(number) ? number.toLocaleString("pt-BR", { style: "currency", currency: "BRL" }) : "R$ 0,00"; }
