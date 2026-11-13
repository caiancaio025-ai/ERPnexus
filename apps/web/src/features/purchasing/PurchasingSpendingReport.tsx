import { useEffect, useMemo, useState } from "react";
import { Download, FileText, Search } from "lucide-react";

import { apiClient } from "../../shared/api/apiClient";
import type { CompanyCode, PurchaseSpendingReport } from "./types";

type Props = {
  company: CompanyCode | "all";
};

function isoMonthStart() {
  const now = new Date();
  return new Date(now.getFullYear(), now.getMonth(), 1).toISOString().slice(0, 10);
}

function isoToday() {
  return new Date().toISOString().slice(0, 10);
}

function money(value: number | string | null | undefined) {
  return Number(value ?? 0).toLocaleString("pt-BR", {
    style: "currency",
    currency: "BRL",
  });
}

function dateLabel(value: string) {
  return new Intl.DateTimeFormat("pt-BR", { timeZone: "UTC" }).format(
    new Date(`${value}T00:00:00Z`),
  );
}

function sourceLabel(source: "purchase_order" | "material_request") {
  return source === "purchase_order" ? "Pedido de compra" : "Solicitação de material";
}

function csvEscape(value: unknown) {
  const text = String(value ?? "");
  return `"${text.replaceAll('"', '""')}"`;
}

export function PurchasingSpendingReport({ company }: Props) {
  const [startDate, setStartDate] = useState(isoMonthStart());
  const [endDate, setEndDate] = useState(isoToday());
  const [supplier, setSupplier] = useState("");
  const [report, setReport] = useState<PurchaseSpendingReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function loadReport() {
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams({
        start_date: startDate,
        end_date: endDate,
      });
      if (company !== "all") params.set("company_code", company);
      if (supplier.trim()) params.set("supplier", supplier.trim());
      const data = await apiClient.request<PurchaseSpendingReport>(
        `/api/purchasing/reports/spending?${params.toString()}`,
      );
      setReport(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível gerar o relatório.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadReport();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [company]);

  const topSuppliers = useMemo(() => report?.by_supplier.slice(0, 10) ?? [], [report]);

  function exportCsv() {
    if (!report) return;
    const header = [
      "Data",
      "Origem",
      "Código",
      "Fornecedor",
      "Item",
      "Quantidade",
      "Valor",
      "O.S.",
      "Cliente",
      "Série",
      "Referência",
      "Status",
    ];
    const rows = report.items.map((item) => [
      item.purchase_date,
      sourceLabel(item.source),
      item.code,
      item.supplier_name,
      item.item_name,
      item.quantity,
      item.amount,
      item.work_order_number ?? "",
      item.customer_name ?? "",
      item.equipment_serial ?? "",
      item.purchase_reference ?? "",
      item.status,
    ]);
    const csv = "\ufeff" + [header, ...rows]
      .map((row) => row.map(csvEscape).join(";"))
      .join("\r\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const href = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = href;
    anchor.download = `relatorio-compras-${report.start_date}-${report.end_date}.csv`;
    anchor.click();
    URL.revokeObjectURL(href);
  }

  function printReport() {
    document.body.classList.add("purchase-spending-print");
    window.print();
    window.setTimeout(() => document.body.classList.remove("purchase-spending-print"), 300);
  }

  return (
    <section className="purchase-spending-report">
      <div className="purchase-report-heading">
        <div>
          <small>GESTÃO DE GASTOS</small>
          <h2>Relatório de gastos de compras</h2>
          <span>
            Consolida pedidos de compra e solicitações de material efetivamente compradas,
            mantendo a origem de cada lançamento.
          </span>
        </div>
        <div className="purchase-report-actions">
          <button type="button" onClick={exportCsv} disabled={!report}><Download size={16}/>Excel/CSV</button>
          <button type="button" onClick={printReport} disabled={!report}><FileText size={16}/>Imprimir/PDF</button>
        </div>
      </div>

      <div className="purchase-report-filters">
        <label><span>De</span><input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} /></label>
        <label><span>Até</span><input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} /></label>
        <label className="supplier-search"><span>Fornecedor</span><div><Search size={15}/><input value={supplier} onChange={(e) => setSupplier(e.target.value)} placeholder="Todos" /></div></label>
        <button type="button" className="purchase-report-generate" onClick={() => void loadReport()} disabled={loading}>
          {loading ? "Gerando..." : "Gerar relatório"}
        </button>
      </div>

      {error && <div className="purchase-alert error">{error}</div>}

      {report && <>
        <section className="purchase-report-kpis">
          <article><span>Gasto total</span><strong>{money(report.summary.total_spent)}</strong><small>{report.summary.purchase_count} lançamento(s)</small></article>
          <article><span>Pedidos de compra</span><strong>{money(report.summary.purchase_order_total)}</strong><small>Compras lançadas diretamente</small></article>
          <article><span>Materiais de O.S./avulsos</span><strong>{money(report.summary.material_request_total)}</strong><small>Comprados nas solicitações</small></article>
          <article><span>Compra média</span><strong>{money(report.summary.average_purchase)}</strong><small>No período selecionado</small></article>
        </section>

        <div className="purchase-report-grid">
          <section className="purchase-report-card">
            <div className="purchase-report-card-title"><h3>Maiores fornecedores</h3><span>Ranking por valor comprado</span></div>
            <div className="purchase-report-ranking">
              {topSuppliers.map((item, index) => <div key={item.key}><span>{index + 1}</span><div><strong>{item.label}</strong><small>{item.count} compra(s)</small></div><b>{money(item.amount)}</b></div>)}
              {!topSuppliers.length && <p>Nenhum gasto no período.</p>}
            </div>
          </section>

          <section className="purchase-report-card">
            <div className="purchase-report-card-title"><h3>Origem dos gastos</h3><span>Separação dos dois fluxos do SÊNTICO</span></div>
            <div className="purchase-report-source">
              {report.by_source.map((item) => <article key={item.key}><span>{item.label}</span><strong>{money(item.amount)}</strong><small>{item.count} lançamento(s)</small></article>)}
              {!report.by_source.length && <p>Nenhum gasto no período.</p>}
            </div>
          </section>
        </div>

        <section className="purchase-report-card purchase-report-months">
          <div className="purchase-report-card-title"><h3>Evolução mensal</h3><span>Valor efetivamente registrado por mês</span></div>
          <div className="purchase-report-month-list">
            {report.by_month.map((item) => <article key={item.month}><span>{item.month.split("-").reverse().join("/")}</span><strong>{money(item.amount)}</strong><small>{item.count} lançamento(s)</small></article>)}
            {!report.by_month.length && <p>Nenhum gasto no período.</p>}
          </div>
        </section>

        <section className="purchase-report-card purchase-report-detail">
          <div className="purchase-report-card-title"><h3>Detalhamento das compras</h3><span>Fonte, fornecedor, item, O.S. e valor de cada gasto.</span></div>
          <div className="purchase-report-table-wrap">
            <table>
              <thead><tr><th>Data</th><th>Origem</th><th>Código</th><th>Fornecedor</th><th>Item</th><th>Qtd.</th><th>O.S. / destino</th><th>Referência</th><th>Valor</th></tr></thead>
              <tbody>
                {report.items.map((item) => <tr key={`${item.source}-${item.source_id}`}>
                  <td>{dateLabel(item.purchase_date)}</td>
                  <td><span className={`purchase-source-pill ${item.source}`}>{sourceLabel(item.source)}</span></td>
                  <td><strong>{item.code}</strong></td>
                  <td>{item.supplier_name}</td>
                  <td><strong>{item.item_name}</strong>{item.equipment_serial && <small>Série: {item.equipment_serial}</small>}</td>
                  <td>{item.quantity}</td>
                  <td>{item.work_order_number || item.customer_name || "—"}{item.work_order_number && item.customer_name && <small>{item.customer_name}</small>}</td>
                  <td>{item.purchase_reference || "—"}</td>
                  <td className="purchase-report-amount">{money(item.amount)}</td>
                </tr>)}
                {!report.items.length && <tr><td colSpan={9} className="purchase-report-empty">Nenhum gasto encontrado.</td></tr>}
              </tbody>
            </table>
          </div>
        </section>
      </>}
    </section>
  );
}
