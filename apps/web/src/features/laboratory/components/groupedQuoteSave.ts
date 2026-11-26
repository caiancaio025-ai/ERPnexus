/** Compare persisted user content, ignoring DB IDs, versions and totals. */
export function groupedQuoteContentMatches(expected: unknown, persisted: unknown): boolean {
  if (!expected || !persisted || typeof expected !== "object" || typeof persisted !== "object") return false;
  const first = expected as Record<string, unknown>;
  const second = persisted as Record<string, unknown>;
  const textFields = ["title", "service_code", "technical_report", "services_description", "billing_terms", "warranty_terms", "payment_terms", "return_condition", "consumer_clause", "supply_clause", "estimate_clause", "discount_type"];
  const numericFields = ["delivery_days", "billing_days", "warranty_months", "validity_days", "discount_value"];
  if (textFields.some(key => String(first[key] ?? "") !== String(second[key] ?? ""))) return false;
  if (numericFields.some(key => !Number.isFinite(Number(first[key])) || Number(first[key]) !== Number(second[key]))) return false;
  const firstIds = first.work_order_ids; const secondIds = second.work_order_ids;
  if (!Array.isArray(firstIds) || !Array.isArray(secondIds) || JSON.stringify([...firstIds].sort((a, b) => a - b)) !== JSON.stringify([...secondIds].sort((a, b) => a - b))) return false;
  if (!Array.isArray(first.items) || !Array.isArray(second.items) || first.items.length !== second.items.length) return false;
  // Preserve each OS's item order while allowing the server to group OS together.
  const canonical = (items: unknown[]) => [...new Set(firstIds)].sort((a, b) => a - b).map(id => items.filter(item => item && typeof item === "object" && Number((item as Record<string, unknown>).work_order_id) === id).map(item => {
    const row = item as Record<string, unknown>;
    const quantity = Number(row.quantity); const unitValue = Number(row.unit_value);
    if (!Number.isFinite(quantity) || !Number.isFinite(unitValue)) return null;
    return [id, String(row.description ?? ""), quantity, unitValue];
  }));
  return JSON.stringify(canonical(first.items)) === JSON.stringify(canonical(second.items));
}
