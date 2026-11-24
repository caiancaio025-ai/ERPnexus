"""V31 — intervalo real no SQL, sem elevar permissões nem alterar registros antigos."""
import asyncio
from datetime import date, datetime
from types import SimpleNamespace

import pytest
from sqlalchemy import Column, Date, DateTime, Integer, MetaData, Table, create_engine, insert, select

from app.dashboard.service import (
    DashboardPeriod, build_summary, period_criteria, resolve_dashboard_period,
)


class Rows:
    def all(self):
        return []


class AuditDB:
    def __init__(self):
        self.queries = []

    async def scalar(self, stmt):
        self.queries.append(stmt)
        return 0

    async def scalars(self, stmt):
        self.queries.append(stmt)
        return Rows()


def statements(db, table):
    return [q for q in db.queries if table in str(q)]


def test_calendar_presets_are_based_on_recife_day():
    today = date(2026, 11, 23)
    assert resolve_dashboard_period("mes", today=today).start == date(2026, 11, 1)
    assert resolve_dashboard_period("mes", today=today).end == date(2026, 11, 30)
    assert resolve_dashboard_period("30d", today=today).start == date(2026, 10, 25)
    assert resolve_dashboard_period("90d", today=today).start == date(2026, 8, 26)
    assert resolve_dashboard_period("ano", today=today).start == date(2026, 1, 1)
    assert resolve_dashboard_period("ano", today=today).end == date(2026, 12, 31)
    assert not resolve_dashboard_period("todos", today=today).active


def test_custom_start_only_hides_old_os_without_deleting():
    period = resolve_dashboard_period("personalizado", start=date(2026, 11, 1))
    assert period.start == date(2026, 11, 1)
    assert period.end is None


@pytest.mark.parametrize("preset,start,end", [
    ("personalizado", None, None),
    ("personalizado", date(2026, 11, 25), date(2026, 11, 1)),
    ("malicioso", None, None),
])
def test_invalid_periods_rejected(preset, start, end):
    with pytest.raises(ValueError):
        resolve_dashboard_period(preset, start, end)


def test_real_sql_date_filter_respects_boundaries():
    metadata = MetaData()
    records = Table("records", metadata, Column("id", Integer, primary_key=True), Column("opened_at", Date))
    engine = create_engine("sqlite:///:memory:")
    metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(insert(records), [
            {"id": 1, "opened_at": date(2021, 4, 5)},
            {"id": 2, "opened_at": date(2026, 11, 1)},
            {"id": 3, "opened_at": date(2026, 11, 23)},
            {"id": 4, "opened_at": date(2026, 11, 24)},
        ])
        period = DashboardPeriod(date(2026, 11, 1), date(2026, 11, 23))
        ids = conn.execute(select(records.c.id).where(*period_criteria(records.c.opened_at, period))).scalars().all()
    assert ids == [2, 3]


def test_datetime_end_is_exclusive_next_midnight():
    metadata = MetaData()
    records = Table("records", metadata, Column("id", Integer, primary_key=True), Column("created_at", DateTime(timezone=True)))
    engine = create_engine("sqlite:///:memory:")
    metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(insert(records), [
            {"id": 1, "created_at": datetime(2023, 1, 1)},
            {"id": 2, "created_at": datetime(2026, 11, 1, 0, 0)},
            {"id": 3, "created_at": datetime(2026, 11, 23, 23, 59, 59)},
            {"id": 4, "created_at": datetime(2026, 11, 24, 0, 0)},
        ])
        period = DashboardPeriod(date(2026, 11, 1), date(2026, 11, 23))
        ids = conn.execute(select(records.c.id).where(*period_criteria(records.c.created_at, period, timestamp=True))).scalars().all()
    assert ids == [2, 3]


def test_all_queues_sql_filter_is_shared_by_counts_and_rows():
    user = SimpleNamespace(id=11, role="gestao", modules=[])
    db = AuditDB()
    period = DashboardPeriod(date(2026, 11, 1), date(2026, 11, 23), "Novembro")
    result = asyncio.run(build_summary(user, db, period))
    assert result.filtered_period
    assert result.monthly_equipment_entries.month_label == "Novembro"
    assert {q.section for q in result.work_queues} == {"laboratorio", "orcamentos", "compras", "financeiro"}
    for table, column in [
        ("laboratory_work_orders", "opened_at"),
        ("material_requests", "created_at"),
        ("financial_entries", "due_date"),
        ("purchase_orders", "purchase_date"),
    ]:
        queries = statements(db, table)
        assert queries, f"Sem consultas em {table}"
        matched = [str(q) for q in queries if f"{table}.{column} >= " in str(q) and (
            f"{table}.{column} <= " in str(q) or f"{table}.{column} < " in str(q))]
        assert matched, f"Filtros ausentes em {table}.{column}"
    # O painel filtra inclusive a lista dos faturados, não só a contagem.
    invoice_selects = [str(q) for q in db.queries if "ORDER BY laboratory_work_orders.invoiced_at DESC" in str(q)]
    assert invoice_selects and all("laboratory_work_orders.invoiced_at" in q and " >= " in q for q in invoice_selects)


def test_non_gestao_cannot_read_finance_with_any_date():
    db = AuditDB()
    user = SimpleNamespace(id=14, role="tecnico", modules=["financeiro", "laboratorio"])
    summary = asyncio.run(build_summary(user, db, DashboardPeriod(start=date(2026, 11, 1))))
    assert not any(q.section == "financeiro" for q in summary.work_queues)
    assert all("financial_entries" not in str(q) for q in db.queries)


def test_legacy_unfiltered_mode_remains_compatible():
    db = AuditDB()
    user = SimpleNamespace(id=11, role="gestao", modules=[])
    summary = asyncio.run(build_summary(user, db))
    assert not summary.filtered_period
    assert "de" in summary.monthly_equipment_entries.month_label
