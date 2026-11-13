from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models import Base


class FinancialAccount(Base):
    __tablename__ = "financial_accounts"
    __table_args__ = (
        UniqueConstraint(
            "company_code",
            "name",
            name="uq_financial_accounts_company_name",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    company_code: Mapped[str] = mapped_column(
        String(40),
        index=True,
        default="universo_eletronica",
    )
    name: Mapped[str] = mapped_column(String(120))
    account_type: Mapped[str] = mapped_column(String(30), default="bank")
    opening_balance: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class FinancialCategory(Base):
    __tablename__ = "financial_categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    entry_type: Mapped[str] = mapped_column(String(20))
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())



class FinancialPeriodClosure(Base):
    __tablename__ = "financial_period_closures"
    __table_args__ = (
        UniqueConstraint(
            "company_code",
            "year",
            "month",
            name="uq_financial_period_closures_company_period",
        ),
        CheckConstraint("month >= 1 AND month <= 12", name="ck_financial_period_closures_month"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    company_code: Mapped[str] = mapped_column(String(40), index=True)
    year: Mapped[int] = mapped_column(index=True)
    month: Mapped[int] = mapped_column(index=True)
    is_closed: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    snapshot_data: Mapped[dict] = mapped_column(JSON, default=dict)
    closed_by: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    closed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    reopened_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reopened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class FinancialAlertAcknowledgment(Base):
    __tablename__ = "financial_alert_acknowledgments"
    __table_args__ = (
        UniqueConstraint(
            "entry_id",
            "fingerprint",
            name="uq_financial_alert_acknowledgments_entry_fingerprint",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    entry_id: Mapped[int] = mapped_column(
        ForeignKey("financial_entries.id", ondelete="CASCADE"), index=True
    )
    fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    acknowledged_by: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    acknowledged_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class FinancialObligation(Base):
    __tablename__ = "financial_obligations"
    __table_args__ = (
        CheckConstraint(
            "installment_count > 0",
            name="ck_financial_obligations_installment_count_positive",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    entry_type: Mapped[str] = mapped_column(String(20), index=True)
    company_code: Mapped[str] = mapped_column(String(40), index=True)
    invoice_type: Mapped[str | None] = mapped_column(String(10), nullable=True)
    series: Mapped[str | None] = mapped_column(String(40), nullable=True)
    nfse_number: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    nfe_number: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    counterparty_name: Mapped[str] = mapped_column(String(180))
    description: Mapped[str] = mapped_column(String(180))
    total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    installment_count: Mapped[int] = mapped_column()
    issue_date: Mapped[date] = mapped_column(Date)
    posting_date: Mapped[date] = mapped_column(Date, index=True)
    bank_name: Mapped[str] = mapped_column(String(80))
    expense_kind: Mapped[str | None] = mapped_column(String(30), nullable=True, index=True)
    account_id: Mapped[int | None] = mapped_column(
        ForeignKey("financial_accounts.id"), nullable=True
    )
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("financial_categories.id"), nullable=True
    )
    document_number: Mapped[str | None] = mapped_column(String(80), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    work_order_id: Mapped[int | None] = mapped_column(
        ForeignKey("laboratory_work_orders.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    idempotency_key: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
        unique=True,
    )
    idempotency_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class FinancialEntry(Base):
    __tablename__ = "financial_entries"
    __table_args__ = (
        UniqueConstraint(
            "obligation_id",
            "installment_number",
            name="uq_financial_entries_obligation_installment",
        ),
        CheckConstraint(
            "installment_number IS NULL OR installment_number > 0",
            name="ck_financial_entries_installment_number_positive",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    obligation_id: Mapped[int | None] = mapped_column(
        ForeignKey("financial_obligations.id"),
        nullable=True,
        index=True,
    )
    installment_number: Mapped[int | None] = mapped_column(nullable=True)
    entry_type: Mapped[str] = mapped_column(String(20), index=True)
    company_code: Mapped[str] = mapped_column(String(40), index=True, default="universo_eletronica")
    invoice_type: Mapped[str | None] = mapped_column(String(10), nullable=True)
    series: Mapped[str | None] = mapped_column(String(40), nullable=True)
    nfse_number: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    nfe_number: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    counterparty_name: Mapped[str] = mapped_column(String(180))
    description: Mapped[str] = mapped_column(String(180))
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    issue_date: Mapped[date] = mapped_column(Date)
    posting_date: Mapped[date] = mapped_column(Date, index=True)
    due_date: Mapped[date] = mapped_column(Date, index=True)
    settlement_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    bank_name: Mapped[str] = mapped_column(String(80))
    expense_kind: Mapped[str | None] = mapped_column(String(30), nullable=True, index=True)
    account_id: Mapped[int | None] = mapped_column(
        ForeignKey("financial_accounts.id"), nullable=True
    )
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("financial_categories.id"), nullable=True
    )
    document_number: Mapped[str | None] = mapped_column(String(80), nullable=True)
    payment_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    billing_compliance: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    work_order_id: Mapped[int | None] = mapped_column(
        ForeignKey("laboratory_work_orders.id", ondelete="SET NULL"), nullable=True, index=True
    )
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    idempotency_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    attachment_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    attachment_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    attachment_mime: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class FinancialTransfer(Base):
    __tablename__ = "financial_transfers"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_account_id: Mapped[int] = mapped_column(ForeignKey("financial_accounts.id"))
    destination_account_id: Mapped[int] = mapped_column(ForeignKey("financial_accounts.id"))
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    transfer_date: Mapped[date] = mapped_column(Date, index=True)
    reason: Mapped[str] = mapped_column(String(240))
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class FinancialAuditEvent(Base):
    __tablename__ = "financial_audit_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(40), index=True)
    entity_id: Mapped[int] = mapped_column(index=True)
    action: Mapped[str] = mapped_column(String(40), index=True)
    description: Mapped[str] = mapped_column(String(280))
    before_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    after_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
