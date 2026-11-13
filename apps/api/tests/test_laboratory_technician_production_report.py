from pathlib import Path


ROOT = Path(__file__).parents[1]
ROUTER = ROOT / "app" / "laboratory" / "router.py"
SCHEMAS = ROOT / "app" / "laboratory" / "schemas.py"
REPORT = ROOT / "app" / "laboratory" / "production_report.py"


def test_report_endpoint_uses_release_period_and_sensitive_permission() -> None:
    router = ROUTER.read_text(encoding="utf-8")
    assert '@router.get("/reports/technician-production"' in router
    assert "start_date: date = Query(...)" in router
    assert "end_date: date = Query(...)" in router
    assert "user_can_view_sensitive_values(user.role)" in router


def test_report_uses_latest_release_per_work_order_without_losing_event_count() -> None:
    source = REPORT.read_text(encoding="utf-8")
    assert "func.row_number()" in source
    assert "partition_by=LaboratoryReleaseEvent.work_order_id" in source
    assert "ranked_releases.c.release_rank == 1" in source
    assert "release_event_count" in source


def test_finance_uses_installment_entries_once_and_ignores_cancelled_deleted_rows() -> None:
    source = REPORT.read_text(encoding="utf-8")
    assert 'FinancialEntry.entry_type == "income"' in source
    assert "FinancialEntry.is_deleted.is_(False)" in source
    assert 'FinancialEntry.status != "cancelled"' in source
    assert 'FinancialEntry.status == "received"' in source
    assert 'FinancialEntry.status == "pending"' in source
    assert "FinancialObligation" not in source


def test_parts_cost_uses_canonical_work_order_value() -> None:
    source = REPORT.read_text(encoding="utf-8")
    assert 'LaboratoryWorkOrder.parts_cost.label("canonical_parts_cost")' in source
    assert "parts_cost = _money(row.canonical_parts_cost)" in source
    assert "PurchaseOrder" not in source


def test_material_requests_are_used_only_for_itemized_part_details() -> None:
    source = REPORT.read_text(encoding="utf-8")
    assert "from app.purchasing.material_models import MaterialRequest" in source
    assert "MaterialRequest.status.in_(MATERIAL_COST_STATUSES)" in source
    assert "subtotal=unit_cost * quantity" in source
    assert "parts=parts_by_work_order.get(wo_id, [])" in source
    assert "parts_cost = sum(" not in source
    assert "parts_cost += " not in source


def test_sensitive_values_are_not_queried_for_unauthorized_roles() -> None:
    source = REPORT.read_text(encoding="utf-8")
    marker = "if include_sensitive_values and work_order_ids:"
    assert marker in source
    before, after = source.split(marker, 1)
    assert "FinancialEntry.work_order_id.in_(work_order_ids)" not in before
    assert "FinancialEntry.work_order_id.in_(work_order_ids)" in after


def test_report_schema_keeps_money_nullable() -> None:
    source = SCHEMAS.read_text(encoding="utf-8")
    assert "class TechnicianProductionReport(BaseModel):" in source
    assert "sensitive_values_visible: bool" in source
    assert "invoiced_total: Decimal | None = None" in source
    assert "parts_cost_total: Decimal | None = None" in source
