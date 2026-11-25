/** Accept both Brazilian user input and decimal strings returned by the API. */
export function moneyInput(value: unknown): number {
  if (typeof value === "number") return value;
  const raw = String(value ?? "").replace(/\s|R\$/gi, "");
  if (!raw) return 0;
  if (/^-?\d{1,3}(\.\d{3})+$/.test(raw)) return Number(raw.replace(/\./g, ""));
  const comma = raw.lastIndexOf(","), dot = raw.lastIndexOf(".");
  const normalized = comma > dot ? raw.replace(/\./g, "").replace(",", ".")
    : comma !== -1 && dot !== -1 ? raw.replace(/,/g, "") : raw;
  return Number(normalized);
}

export function optionalMoneyInput(value: string): string | null {
  if (!value.trim()) return null;
  const parsed = moneyInput(value);
  // Keep invalid/incomplete input intact: the form/API can explain the error,
  // and typing never throws or silently changes an invalid value to zero.
  return Number.isFinite(parsed) ? String(parsed) : value;
}
