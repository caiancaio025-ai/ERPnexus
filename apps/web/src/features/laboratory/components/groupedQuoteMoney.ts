/** Round every line HALF_UP to cents before adding OS/document subtotals. */
export function quoteLineCents(quantity: number, unitValue: number): number {
  if (!Number.isFinite(quantity) || !Number.isFinite(unitValue) || quantity < 0 || unitValue < 0) return 0;
  const thousandths = Math.round(quantity * 1000);
  const unitCents = Math.round(unitValue * 100);
  if (!Number.isSafeInteger(thousandths) || !Number.isSafeInteger(unitCents)) return 0;
  return Number((BigInt(thousandths) * BigInt(unitCents) + 500n) / 1000n);
}

export function quoteDiscountCents(subtotalCents: number, kind: "none" | "amount" | "percent", value: number): number {
  if (!Number.isSafeInteger(subtotalCents) || !Number.isFinite(value) || value < 0 || kind === "none") return 0;
  const hundredths = Math.round(value * 100);
  if (!Number.isSafeInteger(hundredths)) return 0;
  return kind === "amount" ? hundredths : Number((BigInt(subtotalCents) * BigInt(hundredths) + 5000n) / 10000n);
}
