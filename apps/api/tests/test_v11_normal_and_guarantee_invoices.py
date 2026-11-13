"""Regressão: NFs normais separadas de três pares de NFs de garantia (V11)."""
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from app.laboratory.models import LaboratoryWorkOrder
from app.laboratory.schemas import WorkOrderInput, WorkOrderOutput
from app.laboratory.service import apply_work_order_update, list_work_orders_page

ROOT = Path(__file__).resolve().parents[2]
GUARANTEE = tuple(f"warranty_{kind}_invoice_{n}" for kind in ("entry", "exit") for n in (1, 2, 3))
LEGACY = ("entry_invoice_2", "entry_invoice_3", "exit_invoice_2", "exit_invoice_3", "warranty_invoice", "warranty_invoice_2", "warranty_invoice_3")


def test_normal_invoices_and_guarantee_independent():
    data = {key: f"NF-{key}" for key in GUARANTEE}
    payload = WorkOrderInput(company_code="universo_eletronica", customer_name="Cliente", reported_defect="Falha", entry_invoice="NORMAL-ENT", exit_invoice="NORMAL-SAI", **data)
    assert payload.entry_invoice == "NORMAL-ENT"
    assert payload.exit_invoice == "NORMAL-SAI"
    assert all(getattr(payload, key) == value for key, value in data.items())
    assert all(getattr(payload, key) is None for key in LEGACY)
    for key in GUARANTEE:
        assert key in LaboratoryWorkOrder.__table__.columns
        assert key in WorkOrderOutput.model_fields


def test_can_fill_guarantee_return_later_without_replacing_normal_invoices():
    payload = WorkOrderInput(company_code="universo_eletronica", customer_name="Cliente", reported_defect="Falha", entry_invoice="E-100", exit_invoice="S-200")
    assert all(getattr(payload, key) is None for key in GUARANTEE)
    updated = payload.model_copy(update={"warranty_entry_invoice_2":"E-G2", "warranty_exit_invoice_2":"S-G2"})
    instance = SimpleNamespace()
    apply_work_order_update(instance, updated, equipment_id=12)
    assert instance.entry_invoice == "E-100"
    assert instance.exit_invoice == "S-200"
    assert instance.warranty_entry_invoice_2 == "E-G2"
    assert instance.warranty_exit_invoice_2 == "S-G2"


def test_search_includes_guarantee_and_keeps_other_filters():
    import inspect
    src = inspect.getsource(list_work_orders_page)
    for key in GUARANTEE:
        query = select(LaboratoryWorkOrder).where(getattr(LaboratoryWorkOrder, key).ilike("%44%"))
        assert key in str(query.compile(dialect=postgresql.dialect()))
        assert f"LaboratoryWorkOrder.{key}.ilike(term)" in src
    assert "LaboratoryWorkOrder.entry_invoice.ilike(term)" in src
    assert "LaboratoryWorkOrder.exit_invoice.ilike(term)" in src
    assert "opened_from" in src and "opened_before" in src and "company_code" in src and "status" in src


def test_api_frontend_and_outputs_carry_every_guarantee_field():
    router = (ROOT / "api/app/laboratory/router.py").read_text()
    tsx = (ROOT / "web/src/features/laboratory/LaboratoryDashboard.tsx").read_text()
    ts = (ROOT / "web/src/features/laboratory/types.ts").read_text()
    for key in GUARANTEE:
        assert f"{key}=payload.{key}" in router
        assert f"{key}=work_order.{key}" in router
        assert key in ts
        assert f"form.{key}" in tsx
    assert '<StandardInvoices values={form}' in tsx
    assert '<WarrantyInvoices values={form}' in tsx
    assert '<StandardInvoices values={detail}' in tsx
    assert '<WarrantyInvoices values={detail}' in tsx
    assert '<HistoricalInvoiceNotes values={detail}' in tsx
    assert 'NF de entrada"' in tsx and 'NF de saída"' in tsx
    assert 'NF de entrada ${round}' in tsx and 'NF de saída ${round}' in tsx
    assert 'Garantia — retornos do equipamento' in tsx


def test_migration_preserves_legacy_and_installer_revision():
    migration = (ROOT / "api/migrations/versions/20261027_04_separate_warranty_entry_exit_invoices.py").read_text()
    installer = (ROOT.parent.parent / "INSTALAR_SENTICO_DEV.ps1").read_text(encoding="utf-8-sig")
    assert 'down_revision: str | None = "20261027_03"' in migration
    assert 'for kind in ("entry", "exit"):' in migration
    assert 'for number in (1, 2, 3):' in migration
    assert "op.add_column" in migration and "op.drop_column" not in migration
    assert "20261027_04" in installer
    for key in LEGACY:
        assert key in LaboratoryWorkOrder.__table__.columns
