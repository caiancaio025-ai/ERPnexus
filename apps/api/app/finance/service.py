from datetime import date, timedelta
from decimal import Decimal
from typing import Literal, cast

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.finance.models import FinancialAccount, FinancialEntry
from app.finance.schemas import (
    CashFlowPoint,
    CompanyCode,
    DateBasis,
    EntryType,
    FinanceEvent,
    FinanceKpi,
    FinanceSummary,
)

ZERO = Decimal("0.00")
FinanceEventStatus = Literal["overdue", "due_soon", "on_time", "settled"]


def _money(value: object | None) -> Decimal:
    return Decimal(str(value or 0))


def _period_range(year: int, month: int | None) -> tuple[date, date]:
    if month is None:
        return date(year, 1, 1), date(year, 12, 31)
    start = date(year, month, 1)
    next_month = date(year + (month == 12), 1 if month == 12 else month + 1, 1)
    return start, next_month - timedelta(days=1)


def _date_column(date_basis: DateBasis):
    return {
        "posting": FinancialEntry.posting_date,
        "issue": FinancialEntry.issue_date,
        "due": FinancialEntry.due_date,
        "settlement": FinancialEntry.settlement_date,
    }[date_basis]


def _entry_scope(company_code: str | None, consolidated: bool) -> list[ColumnElement[bool]]:
    clauses: list[ColumnElement[bool]] = [FinancialEntry.is_deleted.is_(False)]
    if company_code and not consolidated:
        clauses.append(FinancialEntry.company_code == company_code)
    return clauses


def _event(entry: FinancialEntry, today: date, due_limit: date) -> FinanceEvent:
    event_status: FinanceEventStatus
    due_label: str
    if entry.status in {"paid", "received"}:
        event_status = "settled"
        due_label = "Baixado"
    elif entry.due_date < today:
        days = (today - entry.due_date).days
        event_status = "overdue"
        due_label = f"Atrasado há {days} dia{'s' if days != 1 else ''}"
    elif entry.due_date <= due_limit:
        days = (entry.due_date - today).days
        event_status = "due_soon"
        due_label = "Vence hoje" if days == 0 else f"Vence em {days} dia{'s' if days != 1 else ''}"
    else:
        event_status = "on_time"
        due_label = "Dentro do prazo"
    return FinanceEvent(
        id=entry.id,
        description=entry.description,
        amount=float(entry.amount),
        due_date=entry.due_date,
        due_label=due_label,
        entry_type=cast(EntryType, entry.entry_type),
        status=event_status,
        company_code=cast(CompanyCode, entry.company_code),
        bank_name=entry.bank_name,
        counterparty_name=entry.counterparty_name,
    )


async def build_finance_summary(
    db: AsyncSession,
    company_code: str | None = None,
    consolidated: bool = False,
    year: int | None = None,
    month: int | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    date_basis: DateBasis = "posting",
) -> FinanceSummary:
    today = date.today()
    selected_year = year or today.year
    if start_date and end_date:
        period_start, period_end = start_date, end_date
    else:
        period_start, period_end = _period_range(selected_year, month)
    if period_end < period_start:
        period_start, period_end = period_end, period_start

    due_limit = today + timedelta(days=7)
    scope = _entry_scope(company_code, consolidated)
    date_col = _date_column(date_basis)
    period_scope = [*scope, date_col.is_not(None), date_col >= period_start, date_col <= period_end]

    # Saldo acumulado é mantido apenas como dado técnico. Ele depende de saldo inicial
    # e do histórico completo de baixas, portanto não deve ser confundido com o resultado
    # do período filtrado.
    opening_balance = _money(await db.scalar(select(func.sum(FinancialAccount.opening_balance))))
    settled_income_all = _money(await db.scalar(select(func.sum(FinancialEntry.amount)).where(
        *scope, FinancialEntry.entry_type == "income", FinancialEntry.status == "received"
    )))
    settled_expense_all = _money(await db.scalar(select(func.sum(FinancialEntry.amount)).where(
        *scope, FinancialEntry.entry_type == "expense", FinancialEntry.status == "paid"
    )))
    current_balance = opening_balance + settled_income_all - settled_expense_all

    period_rows = await db.execute(
        select(FinancialEntry.entry_type, func.sum(FinancialEntry.amount), func.count(FinancialEntry.id))
        .where(*period_scope)
        .group_by(FinancialEntry.entry_type)
    )
    period_amounts: dict[str, Decimal] = {}
    period_counts: dict[str, int] = {}
    for kind, total, count in period_rows.all():
        period_amounts[str(kind)] = _money(total)
        period_counts[str(kind)] = int(count or 0)
    period_income = period_amounts.get("income", ZERO)
    period_expense = period_amounts.get("expense", ZERO)
    period_result = period_income - period_expense

    settled_rows = await db.execute(
        select(FinancialEntry.entry_type, func.sum(FinancialEntry.amount))
        .where(
            *period_scope,
            ((FinancialEntry.entry_type == "income") & (FinancialEntry.status == "received"))
            | ((FinancialEntry.entry_type == "expense") & (FinancialEntry.status == "paid")),
        )
        .group_by(FinancialEntry.entry_type)
    )
    settled = {str(kind): _money(total) for kind, total in settled_rows.all()}
    settled_income = settled.get("income", ZERO)
    settled_expense = settled.get("expense", ZERO)

    pending_rows = await db.execute(
        select(FinancialEntry.entry_type, func.sum(FinancialEntry.amount))
        .where(*period_scope, FinancialEntry.status == "pending")
        .group_by(FinancialEntry.entry_type)
    )
    pending = {str(kind): _money(total) for kind, total in pending_rows.all()}
    pending_income = pending.get("income", ZERO)
    pending_expense = pending.get("expense", ZERO)

    # Projetado do filtro: realizado líquido + pendências líquidas do mesmo período.
    projected_balance = (settled_income - settled_expense) + (pending_income - pending_expense)

    overdue_count = int(await db.scalar(
        select(func.count()).select_from(FinancialEntry).where(
            *period_scope, FinancialEntry.status == "pending", FinancialEntry.due_date < today
        )
    ) or 0)
    due_soon_count = int(await db.scalar(
        select(func.count()).select_from(FinancialEntry).where(
            *period_scope, FinancialEntry.status == "pending", FinancialEntry.due_date.between(today, due_limit)
        )
    ) or 0)

    entries = (await db.scalars(
        select(FinancialEntry).where(*period_scope)
        .order_by(date_col.asc(), FinancialEntry.id.desc()).limit(500)
    )).all()
    events = [_event(entry, today, due_limit) for entry in entries]
    income_events = [event for event in events if event.entry_type == "income"]
    expense_events = [event for event in events if event.entry_type == "expense"]

    flow_rows = await db.execute(
        select(
            date_col,
            func.sum(case((FinancialEntry.entry_type == "income", FinancialEntry.amount), else_=0)),
            func.sum(case((FinancialEntry.entry_type == "expense", FinancialEntry.amount), else_=0)),
        )
        .where(*period_scope)
        .group_by(date_col)
        .order_by(date_col)
    )
    by_date = {
        day: (_money(income), _money(expense))
        for day, income, expense in flow_rows.all()
        if day is not None
    }
    cash_flow: list[CashFlowPoint] = []
    running = ZERO
    cursor = period_start
    while cursor <= period_end:
        end = min(cursor + timedelta(days=6), period_end)
        income = sum((v[0] for day, v in by_date.items() if cursor <= day <= end), ZERO)
        expense = sum((v[1] for day, v in by_date.items() if cursor <= day <= end), ZERO)
        running += income - expense
        cash_flow.append(CashFlowPoint(
            label=f"{cursor:%d/%m}–{end:%d/%m}", income=float(income), expense=float(expense), balance=float(running)
        ))
        cursor = end + timedelta(days=1)

    basis_labels = {
        "posting": "competência / lançamento",
        "issue": "emissão",
        "due": "vencimento",
        "settlement": "baixa",
    }
    detail = f"{period_start:%d/%m/%Y} a {period_end:%d/%m/%Y} · {basis_labels[date_basis]}"
    return FinanceSummary(
        current_balance=float(current_balance),
        period_income=float(period_income),
        period_expense=float(period_expense),
        period_result=float(period_result),
        settled_income=float(settled_income),
        settled_expense=float(settled_expense),
        pending_income=float(pending_income),
        pending_expense=float(pending_expense),
        period_entry_count=sum(period_counts.values()),
        period_income_count=period_counts.get("income", 0),
        period_expense_count=period_counts.get("expense", 0),
        period_start=period_start,
        period_end=period_end,
        date_basis=date_basis,
        projected_balance=float(projected_balance),
        overdue_count=overdue_count,
        due_soon_count=due_soon_count,
        kpis=[
            FinanceKpi(label="Receitas filtradas", value=float(period_income), detail=f"{period_counts.get('income', 0)} lançamentos", tone="positive"),
            FinanceKpi(label="Saídas filtradas", value=float(period_expense), detail=f"{period_counts.get('expense', 0)} lançamentos", tone="negative"),
            FinanceKpi(label="Resultado filtrado", value=float(period_result), detail=detail, tone="positive" if period_result >= 0 else "negative"),
            FinanceKpi(label="Recebido no filtro", value=float(settled_income), detail="Receitas já baixadas", tone="positive"),
            FinanceKpi(label="Pago no filtro", value=float(settled_expense), detail="Saídas já baixadas", tone="negative"),
            FinanceKpi(label="Em aberto líquido", value=float(pending_income - pending_expense), detail="A receber menos a pagar", tone="warning"),
        ],
        urgent_events=events,
        income_events=income_events,
        expense_events=expense_events,
        cash_flow=cash_flow,
    )
