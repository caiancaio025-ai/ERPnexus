export type CustomerListItem = {
  id: number;
  company_code: string;
  document: string | null;
  legal_name: string;
  trade_name: string | null;
  phone: string | null;
  email: string | null;
  city: string | null;
  state: string | null;
  is_active: boolean;
};

export type CustomerPage = {
  items: CustomerListItem[];
  page: number;
  page_size: number;
  total: number;
  pages: number;
};

export type CustomerContact = {
  id: number;
  customer_id: number;
  department: string | null;
  name: string;
  job_title: string | null;
  email: string | null;
  phone: string | null;
  whatsapp: string | null;
  is_primary: boolean;
  receives_quotes: boolean;
  receives_invoices: boolean;
  receives_reports: boolean;
  receives_service_updates: boolean;
  notes: string | null;
  is_active: boolean;
  created_at: string;
};

export type BillingProfile = {
  customer_id: number;
  billing_cutoff_day: number | null;
  payment_term_days: number | null;
  requires_purchase_order: boolean;
  requires_customer_order: boolean;
  requires_measurement: boolean;
  requires_service_report: boolean;
  invoice_email: string | null;
  xml_email: string | null;
  portal_url: string | null;
  billing_instructions: string | null;
  financial_notes: string | null;
  updated_at: string;
};

export type CustomerNote = {
  id: number;
  customer_id: number;
  category: string;
  text: string;
  created_by: number;
  created_at: string;
};

export type CustomerDocument = {
  id: number;
  customer_id: number;
  category: string;
  reference_number: string | null;
  issue_date: string | null;
  expiration_date: string | null;
  original_name: string;
  mime_type: string;
  size_bytes: number;
  notes: string | null;
  created_at: string;
};

export type CustomerEquipmentSummary = {
  id: number;
  serial_number: string | null;
  manufacturer: string | null;
  model: string | null;
  equipment_type: string | null;
  power: string | null;
  voltage: string | null;
};

export type CustomerWorkOrderSummary = {
  id: number;
  number: string;
  equipment_id: number;
  equipment_serial: string | null;
  status: string;
  priority: string;
  opened_at: string;
  quoted_value: number | null;
  approved_value: number | null;
};

export type CustomerQuoteSummary = {
  id: number;
  work_order_id: number;
  work_order_number: string;
  revision: number;
  status: string;
  total: number;
  emitted_at: string | null;
  created_at: string;
};

export type CustomerDetail = CustomerListItem & {
  state_registration: string | null;
  municipal_registration: string | null;
  whatsapp: string | null;
  website: string | null;
  postal_code: string | null;
  address: string | null;
  address_number: string | null;
  complement: string | null;
  district: string | null;
  notes: string | null;
  work_orders_count: number;
  quotes_count: number;
  contacts: CustomerContact[];
  billing: BillingProfile | null;
  notes_history: CustomerNote[];
  documents: CustomerDocument[];
  equipment: CustomerEquipmentSummary[];
  work_orders: CustomerWorkOrderSummary[];
  quotes: CustomerQuoteSummary[];
};
