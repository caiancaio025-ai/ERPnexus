import { useEffect, useRef, useState } from "react";
import { CircleDollarSign, FileSearch, Plus, Search, ShieldCheck, Trash2 } from "lucide-react";
import { apiClient } from "../../../shared/api/apiClient";
import { billingAmountText, billingDraft, billingTotal, distributeBillingTotal } from "../batchBilling";
import type { BillingConfirmation, BillingReadiness, CompanyCode, FinanceWorkOrderOption, WorkOrderBillingDraft } from "../types";
import "./workOrderBilling.css";

type Props = {
  companyCode: CompanyCode;
  value: WorkOrderBillingDraft[];
  onChange: (value: WorkOrderBillingDraft[]) => void;
  disabled?: boolean;
  linksLocked?: boolean;
  linksLockReason?: string | null;
  totalAmount: number;
  obligation?: boolean;
};
const currency = (value: unknown) => Number(value || 0).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });

export function WorkOrderBillingSelector({ companyCode, value, onChange, disabled = false, linksLocked = false, linksLockReason, totalAmount, obligation = false }: Props) {
  const [search, setSearch] = useState("");
  const [results, setResults] = useState<FinanceWorkOrderOption[]>([]);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState("");
  const [readiness, setReadiness] = useState<Record<number, BillingReadiness>>({});
  const [readinessErrors, setReadinessErrors] = useState<Record<number, string>>({});
  const [retry, setRetry] = useState(0);
  const searchSequence = useRef(0);
  const selectedIds = value.map(row => row.order.id).join(",");

  useEffect(() => {
    const sequence = ++searchSequence.current;
    setResults([]); setError("");
    if (search.trim().length < 2 || linksLocked) { setSearching(false); return; }
    const timer = window.setTimeout(() => {
      setSearching(true);
      void apiClient.get<FinanceWorkOrderOption[]>(`/finance/work-orders?company_code=${encodeURIComponent(companyCode)}&search=${encodeURIComponent(search.trim())}`)
        .then(rows => { if (searchSequence.current === sequence) setResults(rows); })
        .catch(cause => { if (searchSequence.current === sequence) setError(cause instanceof Error ? cause.message : "Não foi possível pesquisar as OS."); })
        .finally(() => { if (searchSequence.current === sequence) setSearching(false); });
    }, 250);
    return () => { window.clearTimeout(timer); searchSequence.current++; };
  }, [search, companyCode, linksLocked]);

  useEffect(() => {
    let active = true;
    const ids = selectedIds.split(",").filter(Boolean).map(Number);
    setReadiness({}); setReadinessErrors({});
    if (ids.length) void Promise.allSettled(ids.map(id => apiClient.get<BillingReadiness>(`/finance/work-orders/${id}/billing-readiness`))).then(outcomes => {
      if (!active) return;
      const next: Record<number, BillingReadiness> = {}; const failures: Record<number, string> = {};
      outcomes.forEach((result, index) => {
        if (result.status === "fulfilled") next[ids[index]] = result.value;
        else failures[ids[index]] = result.reason instanceof Error ? result.reason.message : "Não foi possível consultar as exigências do cliente.";
      });
      setReadiness(next); setReadinessErrors(failures);
    });
    return () => { active = false; };
  }, [selectedIds, retry]);

  function incompatibility(order: FinanceWorkOrderOption): string | null {
    if (value.some(row => row.order.id === order.id)) return "Já selecionada";
    if (value.length >= 50) return "Limite de 50 OS";
    if (order.company_code !== companyCode) return "Outra empresa emissora";
    if (value.length && (!order.customer_id || !value[0].order.customer_id || order.customer_id !== value[0].order.customer_id)) return "Selecione OS do mesmo cadastro de cliente";
    return null;
  }
  const updateConfirmation = (id: number, confirmation: BillingConfirmation) => onChange(value.map(row => row.order.id === id ? { ...row, confirmation } : row));
  const allocated = billingTotal(value);
  const difference = (Math.round(totalAmount * 100) - Math.round(allocated * 100)) / 100;

  function addOrder(order: FinanceWorkOrderOption) {
    const draft = billingDraft(order);
    if (value.length || totalAmount > 0) draft.amount = difference > 0 ? billingAmountText(difference) : "";
    onChange([...value, draft]);
    setSearch("");
  }

  return <section className="billing-workflow-card billing-orders-selector" aria-label="Ordens de serviço do faturamento">
    <header><div><span>INTEGRAÇÃO COM O LABORATÓRIO</span><strong>Ordens de serviço do faturamento</strong></div><ShieldCheck size={22} /></header>
    <p>Adicione as OS da mesma empresa e do mesmo cliente a este faturamento. O total da receita e as parcelas são mantidos; distribua o valor entre as OS abaixo.</p>
    {obligation && <p className="billing-orders-scope"><strong>Rateio de todo o faturamento: {currency(totalAmount)}.</strong> Os vínculos e valores abaixo valem para todas as parcelas. O valor desta parcela continua no campo “Valor da parcela”.</p>}
    {linksLocked && <p className="billing-orders-lock" role="status"><ShieldCheck size={17} /><span><strong>Vínculos de OS protegidos</strong>{linksLockReason || "Há baixa ou competência fechada neste faturamento. Os vínculos e o rateio foram preservados."}</span></p>}
    {!linksLocked && <label className="billing-orders-search">Buscar Ordem de Serviço<div><Search size={17} /><input disabled={disabled} value={search} onChange={event => setSearch(event.target.value)} placeholder="Digite OS, cliente ou série..." /></div></label>}
    {error && <p role="alert" className="billing-orders-error">{error}</p>}
    {searching && <p role="status">Pesquisando OS…</p>}
    {!searching && search.trim().length >= 2 && !linksLocked && <div className="billing-orders-results">
      {results.map(order => {
        const reason = incompatibility(order);
        return <button key={order.id} type="button" disabled={disabled || Boolean(reason)} onClick={() => addOrder(order)}>
          <span><strong>{order.number} · {order.customer_name}</strong><small>{order.equipment_label}</small><small>{reason || (order.remaining_to_issue != null ? `Saldo a lançar: ${currency(order.remaining_to_issue)}` : "Valor aprovado não informado")}</small></span><Plus size={17} />
        </button>;
      })}
      {!results.length && !error && <p>Nenhuma OS encontrada.</p>}
    </div>}
    {!value.length && search.trim().length < 2 && <small>Digite pelo menos 2 caracteres para localizar uma OS. Deixe em branco para receita sem vínculo.</small>}
    {value.map(row => <article key={row.order.id} className="billing-order-card">
      <header><div><strong>{row.order.number} · {row.order.customer_name}</strong><span>{row.order.equipment_label}</span></div>{!linksLocked && <button type="button" disabled={disabled} aria-label={`Remover ${row.order.number} do faturamento`} onClick={() => onChange(value.filter(item => item.order.id !== row.order.id))}><Trash2 size={16} /></button>}</header>
      <div className="billing-order-values"><span>Aprovado<strong>{row.order.approved_value == null ? "Não informado" : currency(row.order.approved_value)}</strong></span><span>Já lançado<strong>{row.order.billing_metadata_loaded === false ? "Não consultado" : currency(row.order.total_registered)}</strong></span><span>Saldo a lançar<strong>{row.order.billing_metadata_loaded === false ? "Não consultado" : row.order.remaining_to_issue == null ? "Não definido" : currency(row.order.remaining_to_issue)}</strong></span></div>
      <div className="billing-order-links"><a href={`/laboratorio?os=${row.order.id}&aba=quote`} target="_blank" rel="noreferrer" title={`Abrir orçamento de ${row.order.number} em outra aba, preservando esta edição`}><FileSearch size={16} />Ver orçamento da OS</a><a href={`/laboratorio?os=${row.order.id}&aba=financial`} target="_blank" rel="noreferrer" title={`Abrir valores de ${row.order.number} em outra aba, preservando esta edição`}><CircleDollarSign size={16} />Ver valor aprovado</a></div>
      <label>Valor atribuído — {row.order.number}<input aria-label={`Valor atribuído — ${row.order.number}`} aria-describedby={`billing-amount-help-${row.order.id}`} disabled={disabled || linksLocked} readOnly={value.length === 1} inputMode="decimal" value={row.amount} placeholder="0,00" onChange={event => onChange(value.map(item => item.order.id === row.order.id ? { ...item, amount: event.target.value } : item))} /><small id={`billing-amount-help-${row.order.id}`}>{value.length === 1 ? "Esta OS recebe o total do faturamento." : obligation ? "Parte desta OS no total de todas as parcelas." : "Parte desta OS no valor da receita."}</small></label>
      {[row.order.exit_invoice, row.order.exit_invoice_2, row.order.exit_invoice_3].some(Boolean) && <small>Notas de saída registradas: {[row.order.exit_invoice, row.order.exit_invoice_2, row.order.exit_invoice_3].filter(Boolean).join(" · ")}</small>}
      {readiness[row.order.id] ? <BillingChecklist readiness={readiness[row.order.id]} value={row.confirmation} onChange={confirmation => updateConfirmation(row.order.id, confirmation)} disabled={disabled || linksLocked} />
        : readinessErrors[row.order.id] ? <p role="alert" className="billing-orders-error">{readinessErrors[row.order.id]} <button type="button" disabled={disabled} onClick={() => setRetry(current => current + 1)}>Tentar novamente</button></p>
        : <p role="status">Consultando exigências desta OS…</p>}
    </article>)}
    {value.length > 0 && <div className={`billing-orders-total${difference !== 0 ? " has-difference" : ""}`} aria-live="polite"><span>Total do faturamento<strong>{currency(totalAmount)}</strong></span><span>Distribuído entre {value.length} OS<strong>{currency(allocated)}</strong></span>{difference !== 0 && <span>{difference > 0 ? "Falta distribuir" : "Excesso no rateio"}<strong>{currency(Math.abs(difference))}</strong></span>}<small>As OS compartilham a mesma receita. O rateio identifica a parte de cada equipamento e preserva o total financeiro.</small>{value.length > 1 && !linksLocked && <button type="button" disabled={disabled || Math.round(totalAmount * 100) < value.length} onClick={() => onChange(distributeBillingTotal(value, totalAmount))}>Dividir total entre as OS</button>}</div>}
  </section>;
}

function BillingChecklist({ readiness, value, onChange, disabled }: { readiness: BillingReadiness; value: BillingConfirmation; onChange: (value: BillingConfirmation) => void; disabled: boolean }) {
  const textFields: Array<[string, keyof BillingConfirmation, string]> = [["purchase_order", "purchase_order_number", "PO / pedido de compra"], ["customer_order", "customer_order_number", "OS / pedido do cliente"], ["measurement", "measurement_reference", "Medição"]];
  const checkFields: Record<string, keyof BillingConfirmation> = { service_report: "service_report_confirmed", portal: "portal_submitted", invoice_email: "invoice_email_confirmed", xml_email: "xml_email_confirmed" };
  return <details className="billing-order-checklist" open={readiness.items.some(item => item.required)}>
    <summary>Conferências de faturamento — {readiness.work_order_number}{readiness.items.some(item => item.required) ? " · há campos obrigatórios" : ""}</summary>
    {(readiness.billing_instructions || readiness.financial_notes) && <p className="billing-guidance">{[readiness.billing_instructions, readiness.financial_notes].filter(Boolean).join("\n")}</p>}
    <fieldset disabled={disabled}>
      {textFields.map(([key, field, label]) => { const item = readiness.items.find(item => item.key === key); return item ? <label key={key}>{label}{item.required ? " *" : ""}<input value={String(value[field])} onChange={event => onChange({ ...value, [field]: event.target.value })} /></label> : null; })}
      {readiness.items.filter(item => checkFields[item.key]).map(item => <label key={item.key} className="billing-check"><input type="checkbox" checked={Boolean(value[checkFields[item.key]])} onChange={event => onChange({ ...value, [checkFields[item.key]]: event.target.checked })} /><span><strong>{item.label}{item.required ? " *" : ""}</strong>{item.configured_value && <small>{item.configured_value}</small>}</span></label>)}
      {readiness.portal_url && <label>Protocolo / comprovante do portal<input value={value.portal_protocol} onChange={event => onChange({ ...value, portal_protocol: event.target.value })} /></label>}
      <label>Observação do checklist<textarea rows={2} value={value.notes} onChange={event => onChange({ ...value, notes: event.target.value })} /></label>
    </fieldset>
  </details>;
}
