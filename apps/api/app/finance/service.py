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
    ForecastPoint,
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
    # do período filtrado. O saldo inicial preserva a semântica histórica: soma todas as
    # contas cadastradas, enquanto as baixas respeitam o escopo da empresa selecionada.
    opening_balance_sq = select(func.sum(FinancialAccount.opening_balance)).scalar_subquery()
    global_row = (await db.execute(
        select(
            opening_balance_sq.label("opening_balance"),
            func.sum(case(
                ((FinancialEntry.entry_type == "income") & (FinancialEntry.status == "received"), FinancialEntry.amount),
                else_=0,
            )).label("settled_income_all"),
            func.sum(case(
                ((FinancialEntry.entry_type == "expense") & (FinancialEntry.status == "paid"), FinancialEntry.amount),
                else_=0,
            )).label("settled_expense_all"),
        ).where(*scope)
    )).one()
    opening_balance = _money(global_row.opening_balance)
    settled_income_all = _money(global_row.settled_income_all)
    settled_expense_all = _money(global_row.settled_expense_all)
    current_balance = opening_balance + settled_income_all - settled_expense_all

    # Todos os KPIs do período são calculados em uma única agregação. Isso preserva
    # exatamente os mesmos filtros, mas elimina vários round-trips sequenciais ao banco.
    period_row = (await db.execute(
        select(
            func.sum(case((FinancialEntry.entry_type == "income", FinancialEntry.amount), else_=0)).label("period_income"),
            func.sum(case((FinancialEntry.entry_type == "expense", FinancialEntry.amount), else_=0)).label("period_expense"),
            func.count(FinancialEntry.id).label("period_entry_count"),
            func.sum(case((FinancialEntry.entry_type == "income", 1), else_=0)).label("period_income_count"),
            func.sum(case((FinancialEntry.entry_type == "expense", 1), else_=0)).label("period_expense_count"),
            func.sum(case(
                ((FinancialEntry.entry_type == "income") & (FinancialEntry.status == "received"), FinancialEntry.amount),
                else_=0,
            )).label("settled_income"),
            func.sum(case(
                ((FinancialEntry.entry_type == "expense") & (FinancialEntry.status == "paid"), FinancialEntry.amount),
                else_=0,
            )).label("settled_expense"),
            func.sum(case(
                ((FinancialEntry.entry_type == "income") & (FinancialEntry.status == "pending"), FinancialEntry.amount),
                else_=0,
            )).label("pending_income"),
            func.sum(case(
                ((FinancialEntry.entry_type == "expense") & (FinancialEntry.status == "pending"), FinancialEntry.amount),
                else_=0,
            )).label("pending_expense"),
            func.sum(case(
                (
                    (FinancialEntry.entry_type == "income")
                    & (FinancialEntry.status == "pending")
                    & (FinancialEntry.due_date < today),
                    FinancialEntry.amount,
                ),
                else_=0,
            )).label("overdue_income"),
            func.sum(case(
                (
                    (FinancialEntry.entry_type == "expense")
                    & (FinancialEntry.status == "pending")
                    & (FinancialEntry.due_date < today),
                    FinancialEntry.amount,
                ),
                else_=0,
            )).label("overdue_expense"),
            func.sum(case(
                ((FinancialEntry.status == "pending") & (FinancialEntry.due_date < today), 1),
                else_=0,
            )).label("overdue_count"),
            func.sum(case(
                (
                    (FinancialEntry.status == "pending")
                    & (FinancialEntry.due_date >= today)
                    & (FinancialEntry.due_date <= due_limit),
                    1,
                ),
                else_=0,
            )).label("due_soon_count"),
        ).where(*period_scope)
    )).one()

    period_income = _money(period_row.period_income)
    period_expense = _money(period_row.period_expense)
    period_result = period_income - period_expense
    period_entry_count = int(period_row.period_entry_count or 0)
    period_income_count = int(period_row.period_income_count or 0)
    period_expense_count = int(period_row.period_expense_count or 0)
    settled_income = _money(period_row.settled_income)
    settled_expense = _money(period_row.settled_expense)
    pending_income = _money(period_row.pending_income)
    pending_expense = _money(period_row.pending_expense)
    overdue_income = _money(period_row.overdue_income)
    overdue_expense = _money(period_row.overdue_expense)
    overdue_count = int(period_row.overdue_count or 0)
    due_soon_count = int(period_row.due_soon_count or 0)

    # Projetado do filtro: realizado líquido + pendências líquidas do mesmo período.
    projected_balance = (settled_income - settled_expense) + (pending_income - pending_expense)

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

    forecast_rows = (
        await db.execute(
            select(
                FinancialEntry.due_date,
                func.coalesce(func.sum(case((FinancialEntry.entry_type == "income", FinancialEntry.amount), else_=0)), 0),
                func.coalesce(func.sum(case((FinancialEntry.entry_type == "expense", FinancialEntry.amount), else_=0)), 0),
            )
            .where(
                *_entry_scope(company_code, consolidated),
                FinancialEntry.status == "pending",
                FinancialEntry.due_date >= period_start,
                FinancialEntry.due_date <= period_end,
            )
            .group_by(FinancialEntry.due_date)
            .order_by(FinancialEntry.due_date)
        )
    ).all()
    forecast_flow = [
        ForecastPoint(
            date=due_date,
            income=float(_money(income)),
            expense=float(_money(expense)),
            net=float(_money(income) - _money(expense)),
        )
        for due_date, income, expense in forecast_rows
        if due_date is not None
    ]

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
        overdue_income=float(overdue_income),
        overdue_expense=float(overdue_expense),
        period_entry_count=period_entry_count,
        period_income_count=period_income_count,
        period_expense_count=period_expense_count,
        period_start=period_start,
        period_end=period_end,
        date_basis=date_basis,
        projected_balance=float(projected_balance),
        overdue_count=overdue_count,
        due_soon_count=due_soon_count,
        kpis=[
            FinanceKpi(label="Receitas filtradas", value=float(period_income), detail=f"{period_income_count} lançamentos", tone="positive"),
            FinanceKpi(label="Saídas filtradas", value=float(period_expense), detail=f"{period_expense_count} lançamentos", tone="negative"),
            FinanceKpi(label="Resultado filtrado", value=float(period_result), detail=detail, tone="positive" if period_result >= 0 else "negative"),
            FinanceKpi(label="Recebido no filtro", value=float(settled_income), detail="Receitas já baixadas", tone="positive"),
            FinanceKpi(label="Pago no filtro", value=float(settled_expense), detail="Saídas já baixadas", tone="negative"),
            FinanceKpi(label="Em aberto líquido", value=float(pending_income - pending_expense), detail="A receber menos a pagar", tone="warning"),
        ],
        urgent_events=events,
        income_events=income_events,
        expense_events=expense_events,
        cash_flow=cash_flow,
        forecast_flow=forecast_flow,
    )
