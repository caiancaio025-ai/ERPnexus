/** Confirm the visible result of a PATCH whose response was lost, without retrying the write. */
export function materialRequestSaveMatches(expected: Record<string, unknown>, saved: Record<string, unknown>): boolean {
  // Notes are audit events; the request record alone cannot prove their delivery.
  if (String(expected.note ?? "").trim()) return false;
  const text = (value: unknown) => String(value ?? "").trim();
  const fields = ["status", "supplier_name", "purchase_reference", "purchase_link", "tracking_code", "expected_delivery_date", "inventory_destination", "inventory_mode", "inventory_serial", "inventory_category"];
  if (fields.some(key => key in expected && text(expected[key]) !== text(saved[key]))) return false;
  if ("unit_cost" in expected && (expected.unit_cost == null ? saved.unit_cost != null : Number(expected.unit_cost) !== Number(saved.unit_cost))) return false;
  if (expected.inventory_destination === "existing" && Number(expected.inventory_item_id) !== Number(saved.inventory_item_id)) return false;
  if (expected.inventory_destination === "new") {
    if (text(expected.inventory_name) !== text(saved.inventory_name) || Number(expected.inventory_format_id || 0) !== Number(saved.inventory_format_id || 0)) return false;
    const first = (expected.inventory_details || {}) as Record<string, unknown>;
    const second = (saved.inventory_details || {}) as Record<string, unknown>;
    if (["manufacturer", "model", "notes"].some(key => text(first[key]) !== text(second[key]))) return false;
    if (text(first.unit || "UN").toUpperCase() !== text(second.unit || "UN").toUpperCase()) return false;
    if (["slot_id", "subtype_id"].some(key => Number(first[key] || 0) !== Number(second[key] || 0))) return false;
  }
  return true;
}
