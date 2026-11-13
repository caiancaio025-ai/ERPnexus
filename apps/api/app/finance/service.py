from datetime import date, timedelta
from decimal import Decimal
from typing import Literal, cast

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.finance.alerts import finance_alert_fingerprint
from app.finance.models import FinancialAccount, FinancialAlertAcknowledgment, FinancialEntry
from app.finance.schemas import (
    AgingBucket,
    CashFlowPoint,
    CompanyCode,
    DateBasis,
    EntryType,
    FinanceEvent,
    FinanceKpi,
    FinanceSummary,
    ForecastItem,
    ForecastPoint,
    MonthlyFlowPoint,
    WeeklyForecastPoint,
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
    selected_year = year or (start_date.year if start_date else today.year)
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
    # do período filtrado. Quando há empresa selecionada, o saldo inicial precisa respeitar
    # o mesmo escopo; no consolidado, todas as contas do grupo são consideradas.
    opening_balance_query = select(func.sum(FinancialAccount.opening_balance))
    if company_code and not consolidated:
        opening_balance_query = opening_balance_query.where(
            FinancialAccount.company_code == company_code
        )
    opening_balance_sq = opening_balance_query.scalar_subquery()
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

    pending_rows = (
        await db.execute(
            select(
                FinancialEntry.id,
                FinancialEntry.due_date,
                FinancialEntry.entry_type,
                FinancialEntry.counterparty_name,
                FinancialEntry.description,
                FinancialEntry.amount,
                FinancialEntry.company_code,
                FinancialEntry.bank_name,
            )
            .where(
                *_entry_scope(company_code, consolidated),
                FinancialEntry.status == "pending",
            )
            .order_by(FinancialEntry.due_date, FinancialEntry.id)
        )
    ).all()

    pending_ids = [int(row[0]) for row in pending_rows]
    acknowledged: set[tuple[int, str]] = set()
    if pending_ids:
        ack_rows = (
            await db.execute(
                select(
                    FinancialAlertAcknowledgment.entry_id,
                    FinancialAlertAcknowledgment.fingerprint,
                ).where(FinancialAlertAcknowledgment.entry_id.in_(pending_ids))
            )
        ).all()
        acknowledged = {(int(entry_id), str(fingerprint)) for entry_id, fingerprint in ack_rows}

    pending_by_date_map: dict[date, tuple[Decimal, Decimal, int]] = {}
    forecast_items_by_date: dict[date, list[ForecastItem]] = {}
    urgent_events: list[FinanceEvent] = []

    for (
        entry_id,
        due_date,
        entry_type,
        counterparty_name,
        description,
        amount,
        entry_company_code,
        bank_name,
    ) in pending_rows:
        if due_date is None:
            continue

        money_amount = _money(amount)
        income, expense, count = pending_by_date_map.get(
            due_date,
            (ZERO, ZERO, 0),
        )
        if entry_type == "income":
            income += money_amount
        else:
            expense += money_amount
        pending_by_date_map[due_date] = (income, expense, count + 1)

        if period_start <= due_date <= period_end:
            forecast_items_by_date.setdefault(due_date, []).append(
                ForecastItem(
                    id=int(entry_id),
                    entry_type=cast(EntryType, entry_type),
                    counterparty_name=str(counterparty_name),
                    description=str(description),
                    amount=float(money_amount),
                )
            )

        if due_date < today:
            days = (today - due_date).days
            event_status: FinanceEventStatus = "overdue"
            due_label = f"Atrasado há {days} dia{'s' if days != 1 else ''}"
        elif due_date <= due_limit:
            days = (due_date - today).days
            event_status = "due_soon"
            due_label = (
                "Vence hoje"
                if days == 0
                else f"Vence em {days} dia{'s' if days != 1 else ''}"
            )
        else:
            event_status = "on_time"
            due_label = "Dentro do prazo"

        fingerprint = finance_alert_fingerprint(
            due_date=due_date,
            amount=money_amount,
            status="pending",
        )
        if event_status in {"overdue", "due_soon"} and (int(entry_id), fingerprint) not in acknowledged:
            urgent_events.append(
                FinanceEvent(
                    id=int(entry_id),
                    description=str(description),
                    amount=float(money_amount),
                    due_date=due_date,
                    due_label=due_label,
                    entry_type=cast(EntryType, entry_type),
                    status=event_status,
                    company_code=cast(CompanyCode, entry_company_code),
                    bank_name=str(bank_name) if bank_name is not None else None,
                    counterparty_name=str(counterparty_name),
                )
            )

    pending_by_date = [
        (due_date, income, expense, count)
        for due_date, (income, expense, count) in sorted(
            pending_by_date_map.items(),
            key=lambda item: item[0],
        )
    ]

    forecast_flow = [
        ForecastPoint(
            date=due_date,
            income=float(income),
            expense=float(expense),
            net=float(income - expense),
            items=forecast_items_by_date.get(due_date, []),
        )
        for due_date, income, expense, _ in pending_by_date
        if period_start <= due_date <= period_end
    ]

    pending_income_all = sum((income for _, income, _, _ in pending_by_date), ZERO)
    pending_expense_all = sum((expense for _, _, expense, _ in pending_by_date), ZERO)
    projected_balance = current_balance + pending_income_all - pending_expense_all

    aging_specs = [
        ("overdue_90_plus", "Vencido há mais de 90 dias", lambda days: days <= -91),
        ("overdue_61_90", "Vencido há 61–90 dias", lambda days: -90 <= days <= -61),
        ("overdue_31_60", "Vencido há 31–60 dias", lambda days: -60 <= days <= -31),
        ("overdue_1_30", "Vencido há 1–30 dias", lambda days: -30 <= days <= -1),
        ("due_today", "Vence hoje", lambda days: days == 0),
        ("due_1_7", "Vence em 1–7 dias", lambda days: 1 <= days <= 7),
        ("due_8_30", "Vence em 8–30 dias", lambda days: 8 <= days <= 30),
        ("due_31_plus", "Vence após 30 dias", lambda days: days >= 31),
    ]
    aging: list[AgingBucket] = []
    for key, label, matches in aging_specs:
        bucket_income = ZERO
        bucket_expense = ZERO
        bucket_count = 0
        for due_date, income, expense, count in pending_by_date:
            days = (due_date - today).days
            if matches(days):
                bucket_income += income
                bucket_expense += expense
                bucket_count += count
        aging.append(
            AgingBucket(
                key=key,
                label=label,
                income=float(bucket_income),
                expense=float(bucket_expense),
                count=bucket_count,
            )
        )

    overdue_pending_income = sum(
        (income for due_date, income, _, _ in pending_by_date if due_date < today),
        ZERO,
    )
    overdue_pending_expense = sum(
        (expense for due_date, _, expense, _ in pending_by_date if due_date < today),
        ZERO,
    )
    overdue_pending_count = sum(
        count for due_date, _, _, count in pending_by_date if due_date < today
    )

    weekly_forecast_13w: list[WeeklyForecastPoint] = []
    running_balance = current_balance
    week_start = today
    for week_number in range(1, 14):
        week_end = week_start + timedelta(days=6)
        week_income = sum(
            (
                income
                for due_date, income, _, _ in pending_by_date
                if week_start <= due_date <= week_end
            ),
            ZERO,
        )
        week_expense = sum(
            (
                expense
                for due_date, _, expense, _ in pending_by_date
                if week_start <= due_date <= week_end
            ),
            ZERO,
        )
        week_count = sum(
            count for due_date, _, _, count in pending_by_date if week_start <= due_date <= week_end
        )
        carried_income = overdue_pending_income if week_number == 1 else ZERO
        carried_expense = overdue_pending_expense if week_number == 1 else ZERO
        carried_count = overdue_pending_count if week_number == 1 else 0
        opening = running_balance
        net = carried_income + week_income - carried_expense - week_expense
        running_balance += net
        weekly_forecast_13w.append(
            WeeklyForecastPoint(
                week_number=week_number,
                start_date=week_start,
                end_date=week_end,
                opening_balance=float(opening),
                income=float(week_income),
                expense=float(week_expense),
                overdue_income=float(carried_income),
                overdue_expense=float(carried_expense),
                net=float(net),
                closing_balance=float(running_balance),
                entry_count=week_count + carried_count,
            )
        )
        week_start = week_end + timedelta(days=1)

    annual_start = date(selected_year, 1, 1)
    annual_end = date(selected_year, 12, 31)
    monthly_rows = (
        await db.execute(
            select(
                func.extract("month", date_col).label("month"),
                func.coalesce(
                    func.sum(
                        case((FinancialEntry.entry_type == "income", FinancialEntry.amount), else_=0)
                    ),
                    0,
                ),
                func.coalesce(
                    func.sum(
                        case((FinancialEntry.entry_type == "expense", FinancialEntry.amount), else_=0)
                    ),
                    0,
                ),
                func.coalesce(
                    func.sum(
                        case(
                            (
                                (FinancialEntry.entry_type == "income")
                                & (FinancialEntry.status == "received"),
                                FinancialEntry.amount,
                            ),
                            else_=0,
                        )
                    ),
                    0,
                ),
                func.coalesce(
                    func.sum(
                        case(
                            (
                                (FinancialEntry.entry_type == "expense")
                                & (FinancialEntry.status == "paid"),
                                FinancialEntry.amount,
                            ),
                            else_=0,
                        )
                    ),
                    0,
                ),
                func.coalesce(
                    func.sum(
                        case(
                            (
                                (FinancialEntry.entry_type == "income")
                                & (FinancialEntry.status == "pending"),
                                FinancialEntry.amount,
                            ),
                            else_=0,
                        )
                    ),
                    0,
                ),
                func.coalesce(
                    func.sum(
                        case(
                            (
                                (FinancialEntry.entry_type == "expense")
                                & (FinancialEntry.status == "pending"),
                                FinancialEntry.amount,
                            ),
                            else_=0,
                        )
                    ),
                    0,
                ),
            )
            .where(
                *_entry_scope(company_code, consolidated),
                date_col.is_not(None),
                date_col >= annual_start,
                date_col <= annual_end,
            )
            .group_by(func.extract("month", date_col))
            .order_by(func.extract("month", date_col))
        )
    ).all()
    monthly_map = {
        int(month): (
            _money(income),
            _money(expense),
            _money(settled_income_month),
            _money(settled_expense_month),
            _money(pending_income_month),
            _money(pending_expense_month),
        )
        for (
            month,
            income,
            expense,
            settled_income_month,
            settled_expense_month,
            pending_income_month,
            pending_expense_month,
        ) in monthly_rows
        if month is not None
    }
    month_labels = [
        "Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
        "Jul", "Ago", "Set", "Out", "Nov", "Dez",
    ]
    monthly_flow: list[MonthlyFlowPoint] = []
    for month_number in range(1, 13):
        (
            month_income,
            month_expense,
            month_settled_income,
            month_settled_expense,
            month_pending_income,
            month_pending_expense,
        ) = monthly_map.get(month_number, (ZERO, ZERO, ZERO, ZERO, ZERO, ZERO))
        monthly_flow.append(
            MonthlyFlowPoint(
                month=month_number,
                label=f"{month_labels[month_number - 1]}/{selected_year}",
                income=float(month_income),
                expense=float(month_expense),
                settled_income=float(month_settled_income),
                settled_expense=float(month_settled_expense),
                pending_income=float(month_pending_income),
                pending_expense=float(month_pending_expense),
                result=float(month_income - month_expense),
            )
        )

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
        urgent_events=urgent_events,
        income_events=income_events,
        expense_events=expense_events,
        cash_flow=cash_flow,
        forecast_flow=forecast_flow,
        weekly_forecast_13w=weekly_forecast_13w,
        aging=aging,
        monthly_flow=monthly_flow,
    )
