import { useEffect, useMemo, useState } from "react";
import { BarChart3, FileSpreadsheet, Printer, RefreshCw } from "lucide-react";

import { apiClient } from "../../../shared/api/apiClient";
import { ActionButton } from "./ActionButton";
import type {
  CompanyProfile,
  Customer,
  Technician,
  TechnicianProductionReport as TechnicianProductionReportData,
} from "../types";

type Props = {
  onOpenOrder: (workOrderId: number) => void;
};

function isoDate(date: Date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function firstDayOfMonth(date: Date) {
  return new Date(date.getFullYear(), date.getMonth(), 1);
}

function formatMoney(value: string | null | undefined) {
  if (value == null) return "—";
  const number = Number(value);
  return Number.isFinite(number)
    ? number.toLocaleString("pt-BR", { style: "currency", currency: "BRL" })
    : "R$ 0,00";
}

function formatPercent(value: string | null | undefined) {
  if (value == null) return "—";
  const number = Number(value);
  return Number.isFinite(number)
    ? `${number.toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 })}%`
    : "—";
}

function formatDateTime(value: string) {
  return new Date(value).toLocaleString("pt-BR", {
    dateStyle: "short",
    timeStyle: "short",
    timeZone: "America/Recife",
  });
}

function csvCell(value: unknown) {
  const text = value == null ? "" : String(value);
  return `"${text.replaceAll('"', '""')}"`;
}

export function TechnicianProductionReport({ onOpenOrder }: Props) {
  const today = useMemo(() => new Date(), []);
  const [startDate, setStartDate] = useState(isoDate(firstDayOfMonth(today)));
  const [endDate, setEndDate] = useState(isoDate(today));
  const [technicianId, setTechnicianId] = useState("all");
  const [companyCode, setCompanyCode] = useState("all");
  const [customerId, setCustomerId] = useState("all");

  const [companies, setCompanies] = useState<CompanyProfile[]>([]);
  const [technicians, setTechnicians] = useState<Technician[]>([]);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [report, setReport] = useState<TechnicianProductionReportData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const filteredTechnicians = useMemo(
    () => technicians.filter((item) => companyCode === "all" || item.company_code === companyCode),
    [companyCode, technicians],
  );
  const filteredCustomers = useMemo(
    () => customers.filter((item) => companyCode === "all" || item.company_code === companyCode),
    [companyCode, customers],
  );

  useEffect(() => {
    if (technicianId !== "all" && !filteredTechnicians.some((item) => String(item.id) === technicianId)) {
      setTechnicianId("all");
    }
    if (customerId !== "all" && !filteredCustomers.some((item) => String(item.id) === customerId)) {
      setCustomerId("all");
    }
  }, [companyCode, customerId, filteredCustomers, filteredTechnicians, technicianId]);

  async function loadMasterData() {
    try {
      const [companyRows, technicianRows, customerRows] = await Promise.all([
        apiClient.get<CompanyProfile[]>("/laboratory/settings/companies?include_inactive=true"),
        apiClient.get<Technician[]>("/laboratory/technicians"),
        apiClient.get<Customer[]>("/laboratory/customers"),
      ]);
      setCompanies(companyRows);
      setTechnicians(technicianRows);
      setCustomers(customerRows);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Falha ao carregar filtros do relatório.");
    }
  }

  async function loadReport() {
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams({ start_date: startDate, end_date: endDate });
      if (technicianId !== "all") params.set("technician_id", technicianId);
      if (companyCode !== "all") params.set("company_code", companyCode);
      if (customerId !== "all") params.set("customer_id", customerId);
      const data = await apiClient.get<TechnicianProductionReportData>(
        `/laboratory/reports/technician-production?${params.toString()}`,
      );
      setReport(data);
    } catch (reason) {
      setReport(null);
      setError(reason instanceof Error ? reason.message : "Falha ao carregar relatório por técnico.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadMasterData();
    void loadReport();
  }, []);

  function exportExcelCsv() {
    if (!report) return;
    const moneyVisible = report.sensitive_values_visible;
    const header = [
      "Data da liberação", "Técnico", "O.S.", "Cliente", "Equipamento", "Série",
      ...(moneyVisible ? ["Peças compradas", "Faturado", "Recebido", "A receber", "Custo peças", "Resultado bruto", "Margem bruta %"] : []),
    ];
    const rows = report.items.map((item) => [
      formatDateTime(item.released_at),
      item.technician_name || "Sem técnico",
      item.work_order_number,
      item.customer_name,
      item.equipment_label,
      item.equipment_serial || "",
      ...(moneyVisible ? [
        item.parts.map((part) =>
          `${part.item_name} (${part.quantity} x ${formatMoney(part.unit_cost)} = ${formatMoney(part.subtotal)})`
        ).join(" | "),
        item.invoiced_total ?? "0",
        item.received_total ?? "0",
        item.receivable_total ?? "0",
        item.parts_cost ?? "0",
        item.gross_result ?? "0",
        item.gross_margin_percent ?? "",
      ] : []),
    ]);
    const csv = [header, ...rows].map((row) => row.map(csvCell).join(";")).join("\r\n");
    const blob = new Blob(["\uFEFF", csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `producao-tecnicos_${report.start_date}_${report.end_date}.csv`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  function printReport() {
    if (!report) return;
    const cleanup = () => {
      document.body.classList.remove("lab-print-technician-report");
      window.removeEventListener("afterprint", cleanup);
    };
    document.body.classList.add("lab-print-technician-report");
    window.addEventListener("afterprint", cleanup);
    window.print();
    window.setTimeout(cleanup, 1500);
  }

  const moneyVisible = report?.sensitive_values_visible ?? false;

  return (
    <section className="lab-technician-report">
      <div className="lab-report-heading">
        <div>
          <p className="lab-eyebrow"><BarChart3 size={14} /> RELATÓRIO OPERACIONAL</p>
          <h2>Produção por técnico</h2>
          <span>Liberações, faturamento efetivo e custo real das peças compradas para cada O.S.</span>
        </div>
        <div className="lab-report-actions lab-report-no-print">
          <ActionButton
            variant="secondary"
            icon={<FileSpreadsheet size={17} />}
            disabled={!report || loading}
            onClick={exportExcelCsv}
          >
            Excel
          </ActionButton>
          <ActionButton
            variant="secondary"
            icon={<Printer size={17} />}
            disabled={!report || loading}
            onClick={printReport}
          >
            Imprimir / PDF
          </ActionButton>
        </div>
      </div>

      {error && <div className="lab-alert error lab-report-no-print">{error}</div>}

      <section className="lab-report-filters lab-report-no-print">
        <label>
          <span>Data inicial</span>
          <input type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} />
        </label>
        <label>
          <span>Data final</span>
          <input type="date" value={endDate} onChange={(event) => setEndDate(event.target.value)} />
        </label>
        <label>
          <span>Técnico</span>
          <select value={technicianId} onChange={(event) => setTechnicianId(event.target.value)}>
            <option value="all">Todos os técnicos</option>
            {filteredTechnicians.map((item) => (
              <option key={item.id} value={item.id}>{item.name}{!item.is_active ? " (inativo)" : ""}</option>
            ))}
          </select>
        </label>
        <label>
          <span>Empresa</span>
          <select value={companyCode} onChange={(event) => setCompanyCode(event.target.value)}>
            <option value="all">Todas as empresas</option>
            {companies.map((item) => (
              <option key={item.id} value={item.company_code}>
                {item.trade_name || item.legal_name}{!item.is_active ? " (inativa)" : ""}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>Cliente</span>
          <select value={customerId} onChange={(event) => setCustomerId(event.target.value)}>
            <option value="all">Todos os clientes</option>
            {filteredCustomers.map((item) => (
              <option key={item.id} value={item.id}>
                {item.trade_name || item.legal_name}{!item.is_active ? " (inativo)" : ""}
              </option>
            ))}
          </select>
        </label>
        <ActionButton
          icon={<RefreshCw size={17} />}
          loading={loading}
          onClick={() => void loadReport()}
        >
          Aplicar filtros
        </ActionButton>
      </section>

      {report && (
        <>
          <div className="lab-report-print-meta">
            <strong>Período:</strong> {new Date(`${report.start_date}T12:00:00`).toLocaleDateString("pt-BR")}
            {" a "}
            {new Date(`${report.end_date}T12:00:00`).toLocaleDateString("pt-BR")}
          </div>

          <section className="lab-report-kpis">
            <article><span>Equipamentos liberados</span><strong>{report.summary.released_equipment_count}</strong></article>
            {moneyVisible && <>
              <article><span>Faturado</span><strong>{formatMoney(report.summary.invoiced_total)}</strong></article>
              <article><span>Recebido</span><strong>{formatMoney(report.summary.received_total)}</strong></article>
              <article><span>A receber</span><strong>{formatMoney(report.summary.receivable_total)}</strong></article>
              <article><span>Custo de peças</span><strong>{formatMoney(report.summary.parts_cost_total)}</strong></article>
              <article><span>Resultado bruto</span><strong>{formatMoney(report.summary.gross_result)}</strong></article>
              <article><span>Margem bruta</span><strong>{formatPercent(report.summary.gross_margin_percent)}</strong></article>
              <article><span>Ticket médio</span><strong>{formatMoney(report.summary.average_invoice)}</strong></article>
              <article><span>Custo médio</span><strong>{formatMoney(report.summary.average_parts_cost)}</strong></article>
            </>}
          </section>

          {!moneyVisible && (
            <div className="lab-report-values-note">
              Valores financeiros ocultos conforme a permissão do usuário.
            </div>
          )}

          <section className="lab-report-section">
            <div className="lab-report-section-title">
              <div><h3>Comparativo por técnico</h3><span>Uma O.S. é atribuída à liberação mais recente dentro do período.</span></div>
            </div>
            <div className="lab-table-card lab-report-table">
              <table>
                <thead>
                  <tr>
                    <th>Técnico</th>
                    <th>Equipamentos</th>
                    {moneyVisible && <>
                      <th>Faturado</th>
                      <th>Recebido</th>
                      <th>A receber</th>
                      <th>Custo peças</th>
                      <th>Resultado bruto</th>
                      <th>Margem bruta</th>
                    </>}
                  </tr>
                </thead>
                <tbody>
                  {report.by_technician.map((item) => (
                    <tr key={`${item.technician_id ?? "none"}-${item.technician_name ?? "none"}`}>
                      <td><strong>{item.technician_name || "Sem técnico atribuído"}</strong></td>
                      <td>{item.released_equipment_count}</td>
                      {moneyVisible && <>
                        <td>{formatMoney(item.invoiced_total)}</td>
                        <td>{formatMoney(item.received_total)}</td>
                        <td>{formatMoney(item.receivable_total)}</td>
                        <td>{formatMoney(item.parts_cost_total)}</td>
                        <td>{formatMoney(item.gross_result)}</td>
                        <td><strong>{formatPercent(item.gross_margin_percent)}</strong></td>
                      </>}
                    </tr>
                  ))}
                </tbody>
              </table>
              {!report.by_technician.length && <div className="lab-empty">Nenhuma liberação encontrada no período.</div>}
            </div>
          </section>

          <section className="lab-report-section">
            <div className="lab-report-section-title">
              <div><h3>Detalhamento das O.S.</h3><span>Financeiro e peças efetivamente compradas nas solicitações de material da O.S.</span></div>
            </div>
            <div className="lab-table-card lab-report-table">
              <table>
                <thead>
                  <tr>
                    <th>Liberação</th>
                    <th>Técnico</th>
                    <th>O.S.</th>
                    <th>Cliente</th>
                    <th>Equipamento</th>
                    {moneyVisible && <>
                      <th>Peças compradas</th>
                      <th>Faturado</th>
                      <th>Recebido</th>
                      <th>A receber</th>
                      <th>Custo peças</th>
                      <th>Resultado</th>
                      <th>Margem</th>
                    </>}
                  </tr>
                </thead>
                <tbody>
                  {report.items.map((item) => (
                    <tr key={item.work_order_id}>
                      <td>{formatDateTime(item.released_at)}</td>
                      <td>{item.technician_name || "Sem técnico"}</td>
                      <td>
                        <button
                          type="button"
                          className="lab-order-link lab-report-order-link"
                          onClick={() => onOpenOrder(item.work_order_id)}
                        >
                          {item.work_order_number}
                        </button>
                      </td>
                      <td>{item.customer_name}</td>
                      <td>
                        <strong>{item.equipment_label}</strong>
                        {item.equipment_serial && <small className="lab-report-serial">Série: {item.equipment_serial}</small>}
                      </td>
                      {moneyVisible && <>
                        <td className="lab-report-parts-cell">
                          {item.parts.length ? item.parts.map((part) => (
                            <div key={part.material_request_id} className="lab-report-part-item">
                              <strong>{part.item_name}</strong>
                              <span>
                                {part.quantity} x {formatMoney(part.unit_cost)}
                                {" = "}
                                <b>{formatMoney(part.subtotal)}</b>
                              </span>
                            </div>
                          )) : <span className="lab-report-no-parts">Sem peça comprada</span>}
                        </td>
                        <td>{formatMoney(item.invoiced_total)}</td>
                        <td>{formatMoney(item.received_total)}</td>
                        <td>{formatMoney(item.receivable_total)}</td>
                        <td><strong>{formatMoney(item.parts_cost)}</strong></td>
                        <td>{formatMoney(item.gross_result)}</td>
                        <td><strong>{formatPercent(item.gross_margin_percent)}</strong></td>
                      </>}
                    </tr>
                  ))}
                </tbody>
              </table>
              {!report.items.length && <div className="lab-empty">Nenhuma O.S. liberada no período selecionado.</div>}
            </div>
          </section>

          <footer className="lab-report-print-footer">
            SÊNTICO ERP · Relatório de Produção por Técnico
          </footer>
        </>
      )}

      {!report && !loading && !error && <div className="lab-empty">Selecione os filtros para gerar o relatório.</div>}
      {loading && !report && <div className="lab-empty">Carregando relatório...</div>}
    </section>
  );
}
