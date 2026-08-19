from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class EmploymentHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    employee_id: int
    start_date: date
    end_date: date | None
    department: str
    position: str
    salary: Decimal
    employment_type: str
    reason_end: str | None
    created_at: datetime


class EmployeeDocumentListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    employee_id: int
    document_type: str
    original_name: str
    mime_type: str
    file_size: int
    version: int
    metadata_period: str | None
    expiration_date: date | None
    is_public: bool
    accessed_count: int
    downloaded_count: int
    last_accessed_at: datetime | None
    last_downloaded_at: datetime | None
    created_at: datetime


class EmployeeCreate(BaseModel):
    company_code: str = Field(default="universo_eletronica", min_length=2, max_length=40)
    user_id: int | None = None
    full_name: str = Field(min_length=3, max_length=180)
    document: str = Field(min_length=11, max_length=20)
    document_type: str = Field(default="cpf", pattern="^(cpf|cnpj)$")
    date_birth: date | None = None
    gender: str | None = Field(default=None, pattern="^[MFO]$")
    nationality: str | None = None
    email: str | None = Field(default=None, max_length=180)
    phone: str | None = None
    whatsapp: str | None = None
    postal_code: str | None = None
    address: str | None = None
    address_number: str | None = None
    complement: str | None = None
    district: str | None = None
    city: str | None = None
    state: str | None = Field(default=None, pattern="^[A-Z]{2}$")
    department: str = Field(min_length=2, max_length=120)
    position: str = Field(min_length=2, max_length=120)
    salary_base: Decimal = Field(ge=0, decimal_places=2)
    hiring_date: date
    employment_type: str = Field(default="clt", pattern="^(clt|pj|trainee)$")
    bank_name: str | None = None
    bank_account: str | None = None
    bank_routing: str | None = None
    account_type: str | None = None
    account_holder: str | None = None
    pix_key: str | None = None
    pis: str | None = None
    ctps: str | None = None
    rg_number: str | None = None
    rg_issuer: str | None = None
    rg_issue_date: date | None = None
    marital_status: str | None = None
    dependents: int = Field(default=0, ge=0)
    notes: str | None = None

    @field_validator("document")
    @classmethod
    def normalize_document(cls, value: str) -> str:
        digits = "".join(filter(str.isdigit, value))
        if len(digits) not in {11, 14}:
            raise ValueError("CPF/CNPJ deve conter 11 ou 14 dígitos.")
        return digits


class EmployeeUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=3, max_length=180)
    date_birth: date | None = None
    gender: str | None = Field(default=None, pattern="^[MFO]$")
    nationality: str | None = None
    email: str | None = Field(default=None, max_length=180)
    phone: str | None = None
    whatsapp: str | None = None
    postal_code: str | None = None
    address: str | None = None
    address_number: str | None = None
    complement: str | None = None
    district: str | None = None
    city: str | None = None
    state: str | None = Field(default=None, pattern="^[A-Z]{2}$")
    department: str | None = None
    position: str | None = None
    salary_base: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    employment_type: str | None = Field(default=None, pattern="^(clt|pj|trainee)$")
    bank_name: str | None = None
    bank_account: str | None = None
    bank_routing: str | None = None
    account_type: str | None = None
    account_holder: str | None = None
    pix_key: str | None = None
    pis: str | None = None
    ctps: str | None = None
    rg_number: str | None = None
    rg_issuer: str | None = None
    rg_issue_date: date | None = None
    marital_status: str | None = None
    dependents: int | None = Field(default=None, ge=0)
    notes: str | None = None
    is_active: bool | None = None


class EmployeeListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    full_name: str
    document: str
    email: str | None
    department: str
    position: str
    salary_base: Decimal
    hiring_date: date
    termination_date: date | None
    is_active: bool
    created_at: datetime


class EmployeeDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    company_code: str
    user_id: int | None
    full_name: str
    document: str
    document_type: str
    date_birth: date | None
    gender: str | None
    nationality: str | None
    email: str | None
    phone: str | None
    whatsapp: str | None
    postal_code: str | None
    address: str | None
    address_number: str | None
    complement: str | None
    district: str | None
    city: str | None
    state: str | None
    department: str
    position: str
    salary_base: Decimal
    hiring_date: date
    termination_date: date | None
    employment_type: str
    bank_name: str | None
    pix_key: str | None
    pis: str | None
    ctps: str | None
    rg_number: str | None
    marital_status: str | None
    dependents: int
    notes: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    employment_history: list[EmploymentHistoryResponse] = Field(default_factory=list)
    documents: list[EmployeeDocumentListResponse] = Field(default_factory=list)


class EmployeeTerminateRequest(BaseModel):
    termination_date: date
    reason_end: str = Field(min_length=5, max_length=500)


class PaginatedEmployeeResponse(BaseModel):
    total: int
    limit: int
    offset: int
    data: list[EmployeeListResponse]
