import { moneyInput } from "../../shared/forms/moneyInput";
import type { BillingConfirmation, FinancialEntry, FinancialWorkOrderLink, FinanceWorkOrderOption, WorkOrderBillingDraft } from "./types";

export function emptyBillingConfirmation(): BillingConfirmation {
  return { purchase_order_number: "", customer_order_number: "", measurement_reference: "", service_report_confirmed: false,
    portal_submitted: false, portal_protocol: "", invoice_email_confirmed: false, xml_email_confirmed: false, notes: "" };
}

export function normalizeBillingConfirmation(value?: Partial<BillingConfirmation> | null): BillingConfirmation {
  return Object.fromEntries(Object.entries(emptyBillingConfirmation()).map(([key, fallback]) => {
    const field = value?.[key as keyof BillingConfirmation];
    return [key, typeof fallback === "boolean" ? Boolean(field) : String(field ?? "")];
  })) as BillingConfirmation;
}

export function billingDraft(order: FinanceWorkOrderOption): WorkOrderBillingDraft {
  const value = order.remaining_to_issue ?? order.approved_value;
  return { order, amount: value != null && Number(value) > 0 ? Number(value).toFixed(2).replace(".", ",") : "", confirmation: emptyBillingConfirmation() };
}

export function billingTotal(rows: WorkOrderBillingDraft[]): number {
  return rows.reduce((sum, row) => {
    const value = moneyInput(row.amount);
    return sum + (Number.isFinite(value) ? Math.round(value * 100) : 0);
  }, 0) / 100;
}

export function validateBillingSelection(rows: WorkOrderBillingDraft[], installmentCount = 1): string | null {
  if (!rows.length || rows.length > 50) return "Selecione de 1 a 50 ordens de serviço.";
  if (new Set(rows.map(row => row.order.id)).size !== rows.length) return "Uma OS não pode aparecer duas vezes no faturamento.";
  if (rows.some(row => row.order.company_code !== rows[0].order.company_code)) return "Selecione OS da mesma empresa emissora.";
  if (rows.length > 1 && (!rows[0].order.customer_id || rows.some(row => row.order.customer_id !== rows[0].order.customer_id))) {
    return "As OS do faturamento conjunto precisam estar vinculadas ao mesmo cadastro de cliente. Confira o vínculo no Laboratório.";
  }
  if (rows.length * installmentCount > 1000) return "O faturamento permite até 1.000 parcelas no total. Reduza a quantidade de OS ou de parcelas.";
  for (const row of rows) {
    const amount = moneyInput(row.amount);
    if (!Number.isFinite(amount) || amount <= 0 || Math.abs(amount * 100 - Math.round(amount * 100)) > 0.000001) return `Informe um valor positivo com até duas casas decimais para ${row.order.number}.`;
  }
  return null;
}

export function billingAmountText(amount: number | string): string {
  return Number(amount).toFixed(2).replace(".", ",");
}

export function billingDescription(rows: WorkOrderBillingDraft[]): string {
  if (!rows.length) return "";
  const full = `Serviços de laboratório — ${rows.map(row => row.order.number).join(", ")}`;
  return full.length <= 180 ? full : `Serviços de laboratório — ${rows.length} ordens de serviço`;
}

/** The allocation belongs to the entire invoice, even while editing one installment. */
export function billingDocumentTotal(entry: FinancialEntry | null, editedAmount: string): number {
  const amount = moneyInput(editedAmount);
  if (!Number.isFinite(amount)) return 0;
  if (!entry?.obligation_id || entry.obligation_total_amount == null) return amount;
  return (Math.round(Number(entry.obligation_total_amount) * 100) - Math.round(Number(entry.amount) * 100) + Math.round(amount * 100)) / 100;
}

export function savedBillingLinks(entry: FinancialEntry): FinancialWorkOrderLink[] {
  return entry.obligation_id ? (entry.obligation_work_orders ?? entry.work_orders ?? []) : (entry.work_orders ?? []);
}

export function draftsFromSavedLinks(entry: FinancialEntry): WorkOrderBillingDraft[] {
  return savedBillingLinks(entry).map(link => ({
    order: {
      id: link.work_order_id, number: link.work_order_number, company_code: link.company_code,
      customer_id: link.customer_id, customer_name: link.customer_name, equipment_label: link.equipment_label || "",
      status: "", version: link.version, approved_value: link.approved_value == null ? null : Number(link.approved_value),
      total_registered: link.total_registered ?? 0, remaining_to_issue: link.remaining_to_issue ?? null,
      exit_invoice: link.exit_invoice, exit_invoice_2: link.exit_invoice_2, exit_invoice_3: link.exit_invoice_3,
      billing_metadata_loaded: link.total_registered != null,
    },
    amount: billingAmountText(link.amount), confirmation: normalizeBillingConfirmation(link.billing_confirmation),
  }));
}

export function effectiveBillingRows(rows: WorkOrderBillingDraft[], total: number): WorkOrderBillingDraft[] {
  return rows.length === 1 && total > 0 ? [{ ...rows[0], amount: billingAmountText(total) }] : rows;
}

export function validateBillingAllocation(rows: WorkOrderBillingDraft[], total: number, installmentCount = 1): string | null {
  if (!rows.length) return null;
  const error = validateBillingSelection(rows, installmentCount);
  if (error) return error;
  if (Math.round(billingTotal(rows) * 100) !== Math.round(total * 100)) {
    return "A soma dos valores atribuídos às OS deve ser igual ao total do faturamento. Ajuste o rateio sem alterar as parcelas.";
  }
  return null;
}

export function distributeBillingTotal(rows: WorkOrderBillingDraft[], total: number): WorkOrderBillingDraft[] {
  const cents = Math.round(total * 100);
  if (!rows.length || !Number.isFinite(cents) || cents < rows.length) throw new Error("Informe um total que permita atribuir pelo menos R$ 0,01 para cada OS.");
  const base = Math.floor(cents / rows.length);
  const remainder = cents % rows.length;
  return rows.map((row, index) => ({ ...row, amount: billingAmountText((base + (index < remainder ? 1 : 0)) / 100) }));
}

export function suggestedExitInvoice(nfse: string, nfe: string): string {
  const numbers = [...new Set([nfse.trim(), nfe.trim()].filter(Boolean))];
  return numbers.length === 1 ? numbers[0] : "";
}
