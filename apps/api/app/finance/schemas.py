from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, model_validator

EntryType = Literal["income", "expense"]
EntryStatus = Literal["pending", "paid", "received", "cancelled"]
CompanyCode = Literal["universo_eletronica", "universo_automacao", "solucoes_eletronica"]
ExpenseKind = Literal["fixed", "tax", "salary", "supplier", "variable"]
InvoiceType = Literal["nfse", "nfe"]
DateBasis = Literal["posting", "issue", "due", "settlement"]


class FinanceKpi(BaseModel):
    label: str
    value: float
    detail: str
    tone: Literal["positive", "negative", "warning", "neutral"]


class FinanceEvent(BaseModel):
    id: int
    description: str
    amount: float
    due_date: date
    due_label: str
    entry_type: EntryType
    status: Literal["overdue", "due_soon", "on_time", "settled"]
    company_code: CompanyCode
    bank_name: str | None = None
    counterparty_name: str | None = None


class CashFlowPoint(BaseModel):
    label: str
    income: float
    expense: float
    balance: float


class FinanceSummary(BaseModel):
    current_balance: float
    period_income: float
    period_expense: float
    period_result: float
    settled_income: float
    settled_expense: float
    pending_income: float
    pending_expense: float
    period_entry_count: int
    period_income_count: int
    period_expense_count: int
    period_start: date
    period_end: date
    date_basis: DateBasis
    projected_balance: float
    overdue_count: int
    due_soon_count: int
    kpis: list[FinanceKpi]
    urgent_events: list[FinanceEvent]
    income_events: list[FinanceEvent]
    expense_events: list[FinanceEvent]
    cash_flow: list[CashFlowPoint]


class FinancialEntryBase(BaseModel):
    entry_type: EntryType
    company_code: CompanyCode
    invoice_type: InvoiceType | None = None
    series: str | None = Field(default=None, max_length=40)
    nfse_number: str | None = Field(default=None, max_length=80)
    nfe_number: str | None = Field(default=None, max_length=80)
    counterparty_name: str = Field(min_length=2, max_length=180)
    description: str = Field(min_length=3, max_length=180)
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    issue_date: date
    posting_date: date
    due_date: date
    bank_name: str = Field(min_length=2, max_length=80)
    expense_kind: ExpenseKind | None = None
    account_id: int | None = None
    category_id: int | None = None
    document_number: str | None = Field(default=None, max_length=80)
    payment_code: str | None = Field(default=None, max_length=600)
    notes: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def validate_business_rules(self):
        allowed_banks = {
            "universo_eletronica": {"Itaú", "Bradesco"},
            "universo_automacao": {"Banco do Brasil", "Bradesco"},
            "solucoes_eletronica": {"Bradesco"},
        }
        if self.bank_name not in allowed_banks[self.company_code]:
            raise ValueError("Banco não permitido para a empresa selecionada.")
        if self.entry_type == "expense" and self.expense_kind is None:
            raise ValueError("Informe a classificação da despesa.")
        if self.entry_type == "income":
            self.expense_kind = None
        if self.entry_type == "income":
            nfse = (self.nfse_number or "").strip()
            nfe = (self.nfe_number or "").strip()
            if not nfse and not nfe:
                raise ValueError("Informe o número da NFS-e ou da NF-e.")
            self.nfse_number = nfse or None
            self.nfe_number = nfe or None
            if nfse and not nfe:
                self.invoice_type = "nfse"
            elif nfe and not nfse:
                self.invoice_type = "nfe"
            else:
                self.invoice_type = None
            self.document_number = None
        return self


class BillingConfirmation(BaseModel):
    purchase_order_number: str | None = Field(default=None, max_length=120)
    customer_order_number: str | None = Field(default=None, max_length=120)
    measurement_reference: str | None = Field(default=None, max_length=120)
    service_report_confirmed: bool = False
    portal_submitted: bool = False
    portal_protocol: str | None = Field(default=None, max_length=180)
    invoice_email_confirmed: bool = False
    xml_email_confirmed: bool = False
    notes: str | None = Field(default=None, max_length=1000)


class FinancialEntryInput(FinancialEntryBase):
    work_order_id: int | None = None
    billing_confirmation: BillingConfirmation | None = None


class FinancialEntryUpdate(FinancialEntryBase):
    work_order_id: int | None = None
    billing_confirmation: BillingConfirmation | None = None


class FinancialEntryOutput(BaseModel):
    """Projection used when reading persisted rows.

    Legacy imports can legitimately contain historical records that do not satisfy
    today's creation rules (for example an old income without NFS-e/NF-e metadata).
    Read models therefore must not inherit the input validators used for new writes.
    """

    id: int
    entry_type: EntryType
    company_code: CompanyCode
    invoice_type: InvoiceType | None = None
    series: str | None = None
    nfse_number: str | None = None
    nfe_number: str | None = None
    counterparty_name: str
    description: str
    amount: Decimal
    issue_date: date
    posting_date: date
    due_date: date
    bank_name: str
    expense_kind: ExpenseKind | None = None
    account_id: int | None = None
    category_id: int | None = None
    document_number: str | None = None
    payment_code: str | None = None
    notes: str | None = None
    status: EntryStatus
    settlement_date: date | None = None
    attachment_name: str | None = None
    attachment_mime: str | None = None
    work_order_id: int | None = None
    billing_compliance: dict | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SettlementInput(BaseModel):
    settlement_date: date


class FinanceWorkOrderOption(BaseModel):
    id: int
    number: str
    company_code: str
    customer_name: str
    equipment_label: str
    status: str
    approved_value: Decimal | None = None


class BillingChecklistItem(BaseModel):
    key: str
    label: str
    required: bool
    evidence_type: str
    configured_value: str | None = None


class BillingReadiness(BaseModel):
    work_order_id: int
    work_order_number: str
    customer_id: int | None
    customer_name: str
    approved_value: Decimal | None
    portal_url: str | None
    invoice_email: str | None
    xml_email: str | None
    billing_instructions: str | None
    financial_notes: str | None
    items: list[BillingChecklistItem]


class AuditOutput(BaseModel):
    id: int
    entity_type: str
    entity_id: int
    action: str
    description: str
    user_id: int
    user_name: str
    before_data: dict | None
    after_data: dict | None
    created_at: datetime


class TransferInput(BaseModel):
    source_account_id: int
    destination_account_id: int
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    transfer_date: date
    reason: str = Field(min_length=3, max_length=240)

    @model_validator(mode="after")
    def validate_accounts(self):
        if self.source_account_id == self.destination_account_id:
            raise ValueError("A conta de origem deve ser diferente da conta de destino.")
        return self


class TransferOutput(TransferInput):
    id: int
    created_at: datetime
    model_config = {"from_attributes": True}
