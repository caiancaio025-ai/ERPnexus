import type { Quote } from "../types";

/** Interpreta valores do formulário com ponto decimal ou vírgula brasileira. */
export function quoteNumber(value: unknown): number {
  if (typeof value === "number") return value;
  const raw = String(value ?? "").replace(/\s|R\$/gi, "").trim();
  if (!raw) return 0;
  const comma = raw.lastIndexOf(",");
  const dot = raw.lastIndexOf(".");
  const normalized = comma > dot
    ? raw.replace(/\./g, "").replace(",", ".")
    : comma !== -1 && dot !== -1
      ? raw.replace(/,/g, "")
      : raw.replace(",", ".");
  return normalized ? Number(normalized) : 0;
}

/** Valores monetários permitem pontos como milhares: 22.000 = vinte e dois mil. */
export function quoteMoneyNumber(value: unknown): number {
  const raw = String(value ?? "").replace(/\s|R\$/gi, "").trim();
  if (/^-?\d{1,3}(\.\d{3})+$/.test(raw)) return Number(raw.replace(/\./g, ""));
  return quoteNumber(value);
}

/** A API devolve Decimal como string com PONTO decimal, sem separador de milhar.
 * Nunca aplicar aqui a interpretação de campo digitado em pt-BR. */
const serverCents = (value: unknown): number => Math.round(Number(value) * 100);
const cents = (value: unknown) => Math.round(quoteMoneyNumber(value) * 100);
const thousandths = (value: unknown) => Math.round(quoteNumber(value) * 1000);
const str = (value: unknown) => String(value ?? "").trim();
const formatBRL = (centsValue: number): string =>
  Number.isFinite(centsValue) ? (centsValue / 100).toLocaleString("pt-BR", {style:"currency", currency:"BRL"}) : "valor indisponível";

export type QuoteSaveSnapshot = {
  service_code: string;
  technical_report: string;
  services_description: string | null;
  billing_terms: string | null;
  warranty_terms: string | null;
  payment_terms: string;
  return_condition: string;
  consumer_clause: string;
  supply_clause: string;
  estimate_clause: string;
  delivery_days: number;
  billing_days: number;
  warranty_months: number;
  validity_days: number;
  discount_type: "none" | "amount" | "percent";
  discount_value: number;
  items: { description: string; quantity: number; unit_value: number }[];
  photos: { document_id: number; caption: string | null }[];
};

/** Opera sobre centavos x milésimos de quantidade, sem drift binário de reais.
 * O banco mantém quantidade com 3 casas e valores com 2 casas. */
const subtotalInFractionalCents = (payload: QuoteSaveSnapshot) => payload.items.reduce(
  (sum, item) => sum + Math.round(item.quantity * 1000) * Math.round(item.unit_value * 100) / 1000,
  0,
);
export function expectedQuoteSubtotal(payload: QuoteSaveSnapshot): number {
  return Math.round(subtotalInFractionalCents(payload) + 1e-8);
}
export function expectedQuoteTotal(payload: QuoteSaveSnapshot): number {
  const subtotalCents = subtotalInFractionalCents(payload);
  const discountCents = payload.discount_type === "percent"
    ? subtotalCents * payload.discount_value / 100
    : payload.discount_type === "amount" ? Math.round(payload.discount_value * 100) : 0;
  return Math.round(Math.max(0, subtotalCents - discountCents) + 1e-8);
}

/** Nunca reidratar o formulário com dados do servidor se qualquer comparação falhar. */
export function verifyQuoteSaved(payload: QuoteSaveSnapshot, saved: Quote): string | null {
  if (saved.status !== "draft" || saved.emitted_at) {
    return "Esta revisão não está mais em rascunho. As alterações não foram confirmadas.";
  }
  if (saved.total == null || !Number.isFinite(expectedQuoteTotal(payload)) || serverCents(saved.total) !== expectedQuoteTotal(payload)) {
    return `Divergência no total: solicitado ${formatBRL(expectedQuoteTotal(payload))}, registrado ${formatBRL(serverCents(saved.total))}. Rev. ${saved.revision}.`;
  }
  if (saved.subtotal == null || !Number.isFinite(serverCents(saved.subtotal)) || serverCents(saved.subtotal) !== expectedQuoteSubtotal(payload)) {
    return `Divergência no subtotal: solicitado ${formatBRL(expectedQuoteSubtotal(payload))}, registrado ${formatBRL(serverCents(saved.subtotal))}.`;
  }
  if (saved.items.length !== payload.items.length) {
    return "A quantidade de itens gravados não corresponde ao formulário.";
  }
  for (const [i, item] of payload.items.entries()) {
    const stored = saved.items[i];
    if (str(stored.description) !== str(item.description)
      || thousandths(stored.quantity) !== thousandths(item.quantity)
      || serverCents(stored.unit_value) !== cents(item.unit_value)) {
      return `O item ${i + 1} não foi gravado com a descrição, quantidade ou valor informado.`;
    }
  }
  const texts = ["service_code", "technical_report", "services_description", "billing_terms", "warranty_terms", "payment_terms", "return_condition", "consumer_clause", "supply_clause", "estimate_clause"] as const;
  for (const key of texts) {
    if (str(saved[key]) !== str(payload[key])) {
      return `A alteração no campo ${key.replace(/_/g, " ")} não foi confirmada pelo servidor.`;
    }
  }
  const numeric = ["delivery_days", "billing_days", "warranty_months", "validity_days"] as const;
  for (const key of numeric) {
    if (saved[key] !== payload[key]) {
      return `O campo ${key.replace(/_/g, " ")} não foi salvo corretamente.`;
    }
  }
  if (saved.discount_type !== payload.discount_type || serverCents(saved.discount_value) !== cents(payload.discount_value)) {
    return "O desconto do orçamento não foi gravado corretamente.";
  }
  if (saved.photos.length !== payload.photos.length) {
    return "Nem todas as fotos vinculadas ao orçamento foram confirmadas.";
  }
  for (const [i, photo] of payload.photos.entries()) {
    const stored = saved.photos[i];
    if (stored.document_id !== photo.document_id || str(stored.caption) !== str(photo.caption)) {
      return `A fotografia ${i + 1} ou sua legenda não foi confirmada.`;
    }
  }
  return null;
}
