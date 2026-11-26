import { moneyInput } from "../../shared/forms/moneyInput";
import type { BillingConfirmation, FinanceWorkOrderOption, WorkOrderBillingDraft } from "./types";

export function emptyBillingConfirmation(): BillingConfirmation {
  return { purchase_order_number: "", customer_order_number: "", measurement_reference: "", service_report_confirmed: false,
    portal_submitted: false, portal_protocol: "", invoice_email_confirmed: false, xml_email_confirmed: false, notes: "" };
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
    if (Math.round(amount * 100) < installmentCount) return `${row.order.number} precisa ter pelo menos R$ 0,01 para cada parcela. Reduza as parcelas ou ajuste o valor.`;
  }
  return null;
}

export function suggestedExitInvoice(nfse: string, nfe: string): string {
  const numbers = [...new Set([nfse.trim(), nfe.trim()].filter(Boolean))];
  return numbers.length === 1 ? numbers[0] : "";
}
