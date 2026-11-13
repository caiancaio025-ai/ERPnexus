export type CompanyCode = "universo_eletronica" | "universo_automacao" | "solucoes_eletronica";
export type PurchaseOrigin = "national" | "international";
export type PurchaseStatus =
  | "awaiting_payment"
  | "ordered"
  | "processing"
  | "shipped"
  | "customs"
  | "delivered"
  | "cancelled";

export type Supplier = {
  id: number;
  name: string;
  origin: PurchaseOrigin;
  website?: string | null;
  contact_name?: string | null;
  contact_phone?: string | null;
  is_active: boolean;
};

export type PurchaseOrder = {
  id: number;
  code: string;
  company_code: CompanyCode;
  supplier_id: number;
  supplier_name: string;
  equipment_serial?: string | null;
  invoice_number?: string | null;
  client_destination?: string | null;
  product_name: string;
  inventory_destination?: "new" | "existing" | null;
  inventory_item_id?: number | null;
  inventory_name?: string | null;
  inventory_mode?: "bulk" | "serialized" | null;
  inventory_serial?: string | null;
  inventory_category?: string | null;
  inventory_format_id?: number | null;
  quantity: number;
  total_amount: number | null;
  origin: PurchaseOrigin;
  tracking_code?: string | null;
  purchase_date: string;
  estimated_delivery_date: string;
  delivered_at?: string | null;
  status: PurchaseStatus;
  product_link?: string | null;
  notes?: string | null;
  attachment_name?: string | null;
  attachment_mime?: string | null;
  created_at: string;
  updated_at: string;
};

export type PurchaseSummary = {
  total_open: number;
  overdue: number;
  due_soon: number;
  delivered_month: number;
  total_value_open: number | null;
};

export type PurchaseAudit = {
  id: number;
  purchase_id?: number | null;
  action: string;
  description: string;
  user_id: number;
  user_name: string;
  created_at: string;
};

export type MaterialRequestStatus =
  | "awaiting_approval" | "approved" | "rejected" | "purchasing" | "purchased"
  | "in_transit" | "received" | "delivered_to_lab" | "cancelled";

export type MaterialRequest = {
  id: number; code: string; company_code: CompanyCode; work_order_id: number | null; work_order_number: string | null;
  equipment_id: number | null; equipment_serial: string | null; customer_name: string | null; source_type: "work_order" | "standalone";
  requester_user_id: number; requester_name: string; item_name: string; quantity: number;
  priority: "low" | "normal" | "high" | "urgent"; technical_note: string | null; suggested_link: string | null;
  inventory_destination: "new" | "existing" | null; inventory_item_id: number | null;
  inventory_name: string | null; inventory_mode: "bulk" | "serialized" | null;
  inventory_serial: string | null; inventory_category: string | null; inventory_format_id: number | null;
  status: MaterialRequestStatus; supplier_name: string | null; purchase_reference: string | null;
  purchase_link: string | null; tracking_code: string | null; unit_cost: number | null;
  expected_delivery_date: string | null; purchased_at: string | null; received_at: string | null;
  approved_by: number | null; approved_at: string | null; created_at: string; updated_at: string;
};

export type PurchaseSpendingSource = "purchase_order" | "material_request";

export type PurchaseSpendingItem = {
  source: PurchaseSpendingSource;
  source_id: number;
  code: string;
  company_code: CompanyCode;
  purchase_date: string;
  supplier_name: string;
  item_name: string;
  quantity: number;
  amount: number;
  status: string;
  work_order_id: number | null;
  work_order_number: string | null;
  customer_name: string | null;
  equipment_serial: string | null;
  purchase_reference: string | null;
};

export type PurchaseSpendingBreakdown = {
  key: string;
  label: string;
  count: number;
  amount: number;
};

export type PurchaseSpendingMonth = {
  month: string;
  count: number;
  amount: number;
};

export type PurchaseSpendingReport = {
  start_date: string;
  end_date: string;
  company_code: CompanyCode | null;
  summary: {
    purchase_count: number;
    total_spent: number;
    purchase_order_total: number;
    material_request_total: number;
    average_purchase: number;
  };
  by_supplier: PurchaseSpendingBreakdown[];
  by_source: PurchaseSpendingBreakdown[];
  by_month: PurchaseSpendingMonth[];
  items: PurchaseSpendingItem[];
};
