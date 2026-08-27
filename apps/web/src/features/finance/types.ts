export type CompanyCode = "universo_eletronica" | "universo_automacao" | "solucoes_eletronica";
export type CompanyFilter = CompanyCode | "consolidated";
export type FinanceTone = "positive" | "negative" | "warning" | "neutral";
export type FinanceStatus = "overdue" | "due_soon" | "on_time" | "settled";
export type EntryType = "income" | "expense";
export type ExpenseKind = "fixed" | "tax" | "salary" | "supplier" | "variable";
export type InvoiceType = "nfse" | "nfe";
export type EntryStatus = "pending" | "paid" | "received" | "cancelled";
export type DateBasis = "posting" | "issue" | "due" | "settlement";

export type FinanceKpi = { label: string; value: number; detail: string; tone: FinanceTone };
export type FinanceEvent = {
  id: number; description: string; amount: number; due_date: string; due_label: string;
  entry_type: EntryType; status: FinanceStatus; company_code: CompanyCode;
  bank_name?: string | null; counterparty_name?: string | null;
};
export type CashFlowPoint = { label: string; income: number; expense: number; balance: number };
export type FinanceSummary = {
  current_balance: number; period_income: number; period_expense: number; period_result: number;
  settled_income: number; settled_expense: number; pending_income: number; pending_expense: number;
  overdue_income: number; overdue_expense: number;
  period_entry_count: number; period_income_count: number; period_expense_count: number;
  period_start: string; period_end: string; date_basis: DateBasis; projected_balance: number;
  overdue_count: number; due_soon_count: number; kpis: FinanceKpi[]; urgent_events: FinanceEvent[];
  income_events: FinanceEvent[]; expense_events: FinanceEvent[]; cash_flow: CashFlowPoint[];
};
export type FinanceDateBounds = { min_date?: string | null; max_date?: string | null; count: number; date_basis: DateBasis };
export type FinancialEntry = {
  id: number; entry_type: EntryType; company_code: CompanyCode; invoice_type?: InvoiceType | null;
  series?: string | null; nfse_number?: string | null; nfe_number?: string | null; counterparty_name: string; description: string; amount: number;
  issue_date: string; posting_date: string; due_date: string; settlement_date?: string | null;
  status: EntryStatus; bank_name: string; expense_kind?: ExpenseKind | null;
  account_id?: number | null; category_id?: number | null; document_number?: string | null;
  payment_code?: string | null; notes?: string | null; work_order_id?: number | null; billing_compliance?: Record<string, unknown> | null; attachment_name?: string | null;
  attachment_mime?: string | null; created_at: string; updated_at: string;
};
export type FinancialEntryPage = {
  items: FinancialEntry[];
  page: number;
  page_size: number;
  total: number;
  pages: number;
};

export type AuditEvent = {
  id: number; entity_type: string; entity_id: number; action: string; description: string;
  user_id: number; user_name: string; before_data?: Record<string, unknown> | null;
  after_data?: Record<string, unknown> | null; created_at: string;
};

export type FinanceWorkOrderOption = {
  id: number;
  number: string;
  company_code: CompanyCode;
  customer_name: string;
  equipment_label: string;
  status: string;
  approved_value?: number | null;
};

export type BillingChecklistItem = {
  key: string;
  label: string;
  required: boolean;
  evidence_type: string;
  configured_value?: string | null;
};

export type BillingReadiness = {
  work_order_id: number;
  work_order_number: string;
  customer_id?: number | null;
  customer_name: string;
  approved_value?: number | null;
  portal_url?: string | null;
  invoice_email?: string | null;
  xml_email?: string | null;
  billing_instructions?: string | null;
  financial_notes?: string | null;
  items: BillingChecklistItem[];
};

export type BillingConfirmation = {
  purchase_order_number: string;
  customer_order_number: string;
  measurement_reference: string;
  service_report_confirmed: boolean;
  portal_submitted: boolean;
  portal_protocol: string;
  invoice_email_confirmed: boolean;
  xml_email_confirmed: boolean;
  notes: string;
};
