"""Seis notas fiscais por OS, sem perda das notas legadas da V9."""
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from app.laboratory.models import LaboratoryWorkOrder
from app.laboratory.schemas import WorkOrderInput, WorkOrderOutput
from app.laboratory.service import apply_work_order_update, list_work_orders_page

ROOT = Path(__file__).resolve().parents[2]
NEW_FIELDS = ("entry_invoice_2", "entry_invoice_3", "exit_invoice_2", "exit_invoice_3")
ALL_INVOICES = ("entry_invoice", "entry_invoice_2", "entry_invoice_3", "exit_invoice", "exit_invoice_2", "exit_invoice_3")


def test_input_accepts_six_independent_invoices_and_preserves_legacy():
    data = {field: f"NF-{index}" for index, field in enumerate(ALL_INVOICES, 1)}
    payload = WorkOrderInput(company_code="universo_eletronica", customer_name="Cliente", reported_defect="Falha", **data)
    assert tuple(getattr(payload, key) for key in ALL_INVOICES) == tuple(data.values())
    assert payload.warranty_invoice is None
    for key in ALL_INVOICES:
        assert key in LaboratoryWorkOrder.__table__.columns
        assert key in WorkOrderOutput.model_fields


def test_future_cycles_can_be_filled_later_without_changing_original():
    first = WorkOrderInput(company_code="universo_eletronica", customer_name="Cliente", reported_defect="Falha", entry_invoice="entrada-1", exit_invoice="saida-1")
    assert all(getattr(first, key) is None for key in NEW_FIELDS)
    second = first.model_copy(update={"entry_invoice_2": "entrada-2", "exit_invoice_2": "saida-2"})
    assert second.entry_invoice == "entrada-1"
    assert second.exit_invoice == "saida-1"
    work_order = SimpleNamespace()
    apply_work_order_update(work_order, second, equipment_id=42)
    assert work_order.entry_invoice == "entrada-1"
    assert work_order.exit_invoice_2 == "saida-2"
    assert work_order.equipment_id == 42


def test_postgresql_queries_can_filter_all_invoice_fields():
    for key in ALL_INVOICES:
        stmt = select(LaboratoryWorkOrder).where(getattr(LaboratoryWorkOrder, key).ilike("%987%"))
        assert key in str(stmt.compile(dialect=postgresql.dialect()))
    import inspect
    source = inspect.getsource(list_work_orders_page)
    for key in ALL_INVOICES:
        assert f"LaboratoryWorkOrder.{key}.ilike(term)" in source


def test_router_input_output_and_frontend_are_complete():
    router = (ROOT / "api/app/laboratory/router.py").read_text()
    frontend = (ROOT / "web/src/features/laboratory/LaboratoryDashboard.tsx").read_text()
    types = (ROOT / "web/src/features/laboratory/types.ts").read_text()
    for key in ALL_INVOICES:
        assert f"{key}=payload.{key}" in router
        assert f"{key}=work_order.{key}" in router
        assert key in types
        assert f"form.{key}" in frontend
    assert "NF de entrada ${round}" in frontend
    assert "NF de saída ${round}" in frontend
    # V11 manteve os quatro campos extras da V10 como historico, sem usá-los como garantia.
    assert "<StandardInvoices values={form}" in frontend
    assert "<WarrantyInvoices values={form}" in frontend
    assert "<HistoricalInvoiceNotes values={detail}" in frontend


def test_migration_is_incremental_and_non_destructive():
    code = (ROOT / "api/migrations/versions/20261027_03_three_entry_exit_invoices.py").read_text()
    assert 'down_revision: str | None = "20261027_02"' in code
    for key in NEW_FIELDS:
        assert key in LaboratoryWorkOrder.__table__.columns
    assert "op.drop_column" not in code
    assert "op.add_column" in code
