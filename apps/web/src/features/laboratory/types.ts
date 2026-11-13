
export type LocationHistory = {
  id: number;
  location: string;
  assigned_at: string;
  released_at: string | null;
  changed_by: number;
  changed_by_name: string;
  duration_seconds: number;
  is_current: boolean;
};

export type PaintingItem = {
  id: number;
  position: number;
  description: string;
  returned: boolean;
  return_note: string | null;
  returned_at: string | null;
};

export type PaintingPhoto = {
  id: number;
  document_id: number;
  phase: "outbound" | "return";
  position: number;
  caption: string | null;
  original_name: string;
  mime_type: string;
  created_at: string;
};

export type PaintingDispatch = {
  id: number;
  work_order_id: number;
  status: "draft" | "sent" | "returned";
  provider: string | null;
  notes: string | null;
  sent_at: string | null;
  returned_at: string | null;
  created_by: number;
  created_by_name: string;
  sent_by: number | null;
  sent_by_name: string | null;
  returned_by: number | null;
  returned_by_name: string | null;
  created_at: string;
  updated_at: string;
  items: PaintingItem[];
  photos: PaintingPhoto[];
};


export type CompanyProfile = {
  id: number; company_code: string; legal_name: string; trade_name: string | null;
  document: string | null; state_registration: string | null; email: string | null;
  phone: string | null; address: string | null; city: string | null; state: string | null;
  is_active: boolean; created_at: string; updated_at: string;
};

export type LaboratoryAreaConfig = {
  id: number; code: string; name: string; sort_order: number; is_active: boolean;
  direct_location_code: string | null;
};

export type LaboratoryRackConfig = {
  id: number; area_id: number; area_code: string; area_name: string; code: string; name: string;
  position_prefix: string; rows: number; columns: number;
  layout_row: number; layout_column: number; layout_span: number;
  sort_order: number; is_active: boolean;
};

export type LaboratoryLocationConfigItem = {
  id: number; area_id: number; area_code: string; area_name: string; rack_id: number | null;
  rack_code: string | null; rack_name: string | null; code: string; name: string;
  sort_order: number; is_active: boolean;
};

export type LaboratoryLocationConfig = {
  areas: LaboratoryAreaConfig[];
  racks: LaboratoryRackConfig[];
  locations: LaboratoryLocationConfigItem[];
};

export type CompanyCode = string;
export type Priority = "low" | "normal" | "high" | "urgent";
export type WorkOrderStatus = string;

export type WorkflowOption = {
  id: number; kind: "status" | "substatus"; code: string; label: string;
  sort_order: number; is_active: boolean; is_system: boolean;
};

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
  entry_invoice: string | null; entry_invoice_2: string | null; entry_invoice_3: string | null; entry_invoice_access_key: string | null;
  exit_invoice: string | null; exit_invoice_2: string | null; exit_invoice_3: string | null; exit_invoice_access_key: string | null; warranty_invoice: string | null; warranty_invoice_2: string | null; warranty_invoice_3: string | null; warranty_entry_invoice_1: string | null; warranty_entry_invoice_2: string | null; warranty_entry_invoice_3: string | null; warranty_exit_invoice_1: string | null; warranty_exit_invoice_2: string | null; warranty_exit_invoice_3: string | null;
  is_inactive: boolean; inactivation_reason: string | null; inactivated_at: string | null;
  storage_location: string | null; status: WorkOrderStatus;
  priority: Priority; reported_defect: string; entry_condition: string | null;
  accessories_received: string | null; assigned_technician_id: number | null;
  opened_at: string; completed_at: string | null; delivered_at: string | null;
  parts_cost: string | null; quoted_value: string | null; approved_value: string | null;
  internal_notes: string | null; customer_notes: string | null; substatuses: string[]; version: number;
  created_at: string; updated_at: string;
};

export type StatusHistory = {
  id: number; previous_status: string | null; new_status: string; note: string | null;
  user_id: number; user_name: string; created_at: string;
  release_event_id: number | null; release_technician_id: number | null;
  release_technician_name: string | null; release_released_at: string | null;
};

export type WorkOrderPage = { items: WorkOrder[]; page: number; page_size: number; total: number; pages: number };
export type WorkOrderSummary = {
  total_open: number; analyzed: number; awaiting_approval: number; approved: number;
  awaiting_analysis: number; in_repair: number; in_testing: number;
  high_priority: number; completed_month: number;
  approved_total: string | null; awaiting_approval_total: string | null;
};

export type QuoteItem = { id?: number; position?: number; description: string; quantity: string; unit_value: string | null };
export type QuotePhoto = { id?: number; document_id: number; position: number; caption: string | null; original_name: string; mime_type: string };
export type Quote = {
  id: number; work_order_id: number; revision: number; status: string; service_code: string;
  technical_report: string; services_description: string | null; delivery_days: number;
  billing_days: number; billing_terms: string | null;
  warranty_months: number; warranty_terms: string | null; payment_terms: string; validity_days: number;
  return_condition: string; consumer_clause: string; supply_clause: string; estimate_clause: string;
  discount_type: "none" | "amount" | "percent"; discount_value: string | null; subtotal: string | null; total: string | null;
  emitted_at: string | null; created_at: string; updated_at: string; items: QuoteItem[]; photos: QuotePhoto[];
};

export type MaterialRequestStatus =
  | "awaiting_approval" | "approved" | "rejected" | "purchasing" | "purchased"
  | "in_transit" | "received" | "delivered_to_lab" | "cancelled";

export type MaterialRequest = {
  id: number; code: string; company_code: string; work_order_id: number; work_order_number: string;
  equipment_id: number; equipment_serial: string | null; customer_name: string;
  requester_user_id: number; requester_name: string; item_name: string; quantity: number;
  priority: Priority; technical_note: string | null; suggested_link: string | null;
  inventory_destination: "new" | "existing" | null; inventory_item_id: number | null;
  inventory_name: string | null; inventory_mode: "bulk" | "serialized" | null;
  inventory_serial: string | null; inventory_category: string | null; inventory_format_id: number | null;
  status: MaterialRequestStatus; supplier_name: string | null; purchase_reference: string | null;
  purchase_link: string | null; tracking_code: string | null; unit_cost: string | null;
  expected_delivery_date: string | null; purchased_at: string | null; received_at: string | null;
  approved_by: number | null; approved_at: string | null; created_at: string; updated_at: string;
};


export type LaboratoryLocationOccupant = {
  work_order_id: number;
  work_order_number: string;
  customer_name: string;
  equipment_label: string;
  status: string;
  priority: string;
  location_assigned_at: string | null;
  location_duration_seconds: number;
  dwell_level: "normal" | "attention" | "critical";
};

export type LaboratoryLocationSlot = {
  location: string;
  area_code: string;
  area_name: string;
  area_sort_order: number;
  rack_code: string | null;
  rack_name: string | null;
  rack_sort_order: number;
  rack_rows: number;
  rack_columns: number;
  rack_layout_row: number;
  rack_layout_column: number;
  rack_layout_span: number;
  slot_number: number;
  occupants: LaboratoryLocationOccupant[];
  occupancy_count: number;
  has_urgent: boolean;
  has_attention: boolean;
  has_critical: boolean;
  max_location_duration_seconds: number;
  work_order_id: number | null;
  work_order_number: string | null;
  customer_name: string | null;
  equipment_label: string | null;
  status: string | null;
  priority: string | null;
};

export type LaboratoryLocationMap = {
  total_positions: number;
  occupied_positions: number;
  free_positions: number;
  located_work_orders: number;
  urgent_positions: number;
  urgent_work_orders: number;
  attention_positions: number;
  attention_work_orders: number;
  critical_positions: number;
  critical_work_orders: number;
  work_orders_without_location: number;
  slots: LaboratoryLocationSlot[];
};
export type TechnicianProductionPartItem = {
  material_request_id: number;
  code: string;
  item_name: string;
  quantity: number;
  unit_cost: string;
  subtotal: string;
  status: string;
};

export type TechnicianProductionRow = {
  release_event_id: number;
  released_at: string;
  technician_id: number | null;
  technician_name: string | null;
  work_order_id: number;
  work_order_number: string;
  company_code: string;
  customer_id: number | null;
  customer_name: string;
  equipment_id: number;
  equipment_label: string;
  equipment_serial: string | null;
  invoiced_total: string | null;
  received_total: string | null;
  receivable_total: string | null;
  parts_cost: string | null;
  parts: TechnicianProductionPartItem[];
  gross_result: string | null;
  gross_margin_percent: string | null;
};

export type TechnicianProductionSummary = {
  released_equipment_count: number;
  release_event_count: number;
  invoiced_total: string | null;
  received_total: string | null;
  receivable_total: string | null;
  parts_cost_total: string | null;
  gross_result: string | null;
  gross_margin_percent: string | null;
  average_invoice: string | null;
  average_parts_cost: string | null;
};

export type TechnicianProductionBreakdown = {
  technician_id: number | null;
  technician_name: string | null;
  released_equipment_count: number;
  invoiced_total: string | null;
  received_total: string | null;
  receivable_total: string | null;
  parts_cost_total: string | null;
  gross_result: string | null;
  gross_margin_percent: string | null;
};

export type TechnicianProductionReport = {
  start_date: string;
  end_date: string;
  sensitive_values_visible: boolean;
  summary: TechnicianProductionSummary;
  by_technician: TechnicianProductionBreakdown[];
  items: TechnicianProductionRow[];
};
