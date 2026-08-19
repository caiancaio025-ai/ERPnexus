export type CompanyCode = "universo_eletronica" | "universo_automacao" | "solucoes_eletronica";
export type Priority = "low" | "normal" | "high" | "urgent";
export type WorkOrderStatus =
  | "received" | "awaiting_analysis" | "in_analysis" | "awaiting_quote" | "quote_sent"
  | "awaiting_approval" | "approved" | "rejected" | "awaiting_parts" | "in_repair"
  | "in_testing" | "completed" | "awaiting_pickup" | "delivered" | "warranty" | "invoiced"
  | "cancelled" | "no_repair";

export type Customer = {
  id: number; company_code: CompanyCode; document: string | null; legal_name: string;
  trade_name: string | null; phone: string | null; email: string | null; address: string | null;
  city: string | null; state: string | null; is_active: boolean;
};

export type Technician = {
  id: number; company_code: CompanyCode; name: string; specialty: string | null;
  phone: string | null; email: string | null; color: string | null; user_id: number | null;
  is_active: boolean;
};

export type WorkOrder = {
  id: number; number: string; company_code: CompanyCode; customer_id: number | null;
  equipment_id: number; customer_name: string; equipment_serial: string | null;
  equipment_type: string | null; manufacturer: string | null; model: string | null;
  power: string | null; voltage: string | null; equipment_notes: string | null;
  entry_invoice: string | null; exit_invoice: string | null; status: WorkOrderStatus;
  priority: Priority; reported_defect: string; entry_condition: string | null;
  accessories_received: string | null; assigned_technician_id: number | null;
  opened_at: string; completed_at: string | null; delivered_at: string | null;
  parts_cost: string | null; quoted_value: string | null; approved_value: string | null;
  internal_notes: string | null; customer_notes: string | null; version: number;
  created_at: string; updated_at: string;
};

export type StatusHistory = {
  id: number; previous_status: string | null; new_status: string; note: string | null;
  user_id: number; user_name: string; created_at: string;
};

export type WorkOrderPage = { items: WorkOrder[]; page: number; page_size: number; total: number; pages: number };
export type WorkOrderSummary = {
  total_open: number; awaiting_analysis: number; in_repair: number;
  in_testing: number; high_priority: number; completed_month: number;
};

export type QuoteItem = { id?: number; position?: number; description: string; quantity: string; unit_value: string };
export type Quote = {
  id: number; work_order_id: number; revision: number; status: string; service_code: string;
  technical_report: string; services_description: string | null; delivery_days: number;
  billing_days: number; warranty_months: number; payment_terms: string; validity_days: number;
  return_condition: string; consumer_clause: string; supply_clause: string; estimate_clause: string;
  discount_type: "none" | "amount" | "percent"; discount_value: string; subtotal: string; total: string;
  emitted_at: string | null; created_at: string; updated_at: string; items: QuoteItem[];
};

export type MaterialRequestStatus =
  | "awaiting_approval" | "approved" | "rejected" | "purchasing" | "purchased"
  | "in_transit" | "received" | "delivered_to_lab" | "cancelled";

export type MaterialRequest = {
  id: number; code: string; company_code: string; work_order_id: number; work_order_number: string;
  equipment_id: number; equipment_serial: string | null; customer_name: string;
  requester_user_id: number; requester_name: string; item_name: string; quantity: number;
  priority: Priority; technical_note: string | null; suggested_link: string | null;
  status: MaterialRequestStatus; supplier_name: string | null; purchase_reference: string | null;
  purchase_link: string | null; tracking_code: string | null; unit_cost: string | null;
  expected_delivery_date: string | null; purchased_at: string | null; received_at: string | null;
  approved_by: number | null; approved_at: string | null; created_at: string; updated_at: string;
};
