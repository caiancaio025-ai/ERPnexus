import { ApiError } from "../../shared/api/apiError";
import { moneyInput } from "../../shared/forms/moneyInput";
import { normalizeBillingConfirmation, savedBillingLinks } from "./batchBilling";
import type { BillingConfirmation, FinancialEntry, FinancialWorkOrderLink, WorkOrderBillingDraft } from "./types";

type LinkInput = { work_order_id: number; amount: number | string; billing_confirmation?: Partial<BillingConfirmation> | null };
export type FinancialUpdatePayload = Record<string, unknown> & { work_orders?: LinkInput[]; exit_invoice?: string | null };

const text = (value: unknown) => String(value ?? "").trim();
const cents = (value: unknown) => Math.round(Number(value) * 100);
const moneyFields = new Set(["amount", "obligation_total_amount"]);
const ignoredFields = new Set(["version", "obligation_version", "work_order_version", "work_orders", "billing_confirmation", "exit_invoice", "work_order_id"]);

function confirmationSnapshot(value?: Partial<BillingConfirmation> | null) {
  const merged = normalizeBillingConfirmation(value);
  return Object.fromEntries(Object.entries(merged).sort(([a], [b]) => a.localeCompare(b))
    .map(([key, field]) => [key, typeof field === "boolean" ? field : text(field)]));
}

export function billingLinkSnapshot(links: LinkInput[]): string {
  return JSON.stringify(links.map(link => ({
    id: link.work_order_id, cents: cents(link.amount), confirmation: confirmationSnapshot(link.billing_confirmation),
  })).sort((a, b) => a.id - b.id));
}

export function billingDraftSnapshot(rows: WorkOrderBillingDraft[]): string {
  return billingLinkSnapshot(rows.map(row => ({ work_order_id: row.order.id, amount: moneyInput(row.amount), billing_confirmation: row.confirmation })));
}

/** Compare persisted intent, never the versions that the successful write has incremented. */
export function financialUpdateMatches(entry: FinancialEntry, payload: FinancialUpdatePayload): boolean {
  const stored = entry as unknown as Record<string, unknown>;
  for (const [key, value] of Object.entries(payload)) {
    if (ignoredFields.has(key)) continue;
    if (moneyFields.has(key) ? cents(value) !== cents(stored[key]) : text(value) !== text(stored[key])) return false;
  }
  const links = savedBillingLinks(entry);
  if (payload.work_orders && billingLinkSnapshot(payload.work_orders) !== billingLinkSnapshot(links)) return false;
  if (!payload.work_orders && "work_order_id" in payload && Number(payload.work_order_id || 0) !== Number(entry.work_order_id || 0)) return false;
  const invoice = text(payload.exit_invoice);
  if (invoice && links.some((link: FinancialWorkOrderLink) => ![link.exit_invoice, link.exit_invoice_2, link.exit_invoice_3].some(value => text(value) === invoice))) return false;
  return true;
}

/** A lost acknowledgement is resolved with one read, without blindly replaying a financial write. */
export async function persistFinancialUpdate(
  payload: FinancialUpdatePayload,
  write: () => Promise<FinancialEntry>,
  read: () => Promise<FinancialEntry>,
): Promise<FinancialEntry> {
  try { return await write(); }
  catch (error) {
    const status = error instanceof ApiError ? error.status : null;
    if (status === 0 || status === 409 || (status != null && status >= 500)) {
      try {
        const saved = await read();
        if (financialUpdateMatches(saved, payload)) return saved;
      } catch { /* Keep the original write failure and the user's draft. */ }
    }
    throw error;
  }
}
