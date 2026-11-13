from pathlib import Path


ROOT = Path(__file__).parents[1]
REPORT = ROOT / "app" / "laboratory" / "production_report.py"
MATERIAL_SERVICE = ROOT / "app" / "purchasing" / "material_service.py"


def test_technician_report_uses_canonical_work_order_parts_cost() -> None:
    source = REPORT.read_text(encoding="utf-8")
    assert 'LaboratoryWorkOrder.parts_cost.label("canonical_parts_cost")' in source
    assert "parts_cost = _money(row.canonical_parts_cost)" in source
    assert "PurchaseOrder" not in source
    assert "purchase_orders" not in source


def test_material_requests_define_canonical_cost_from_real_purchased_states() -> None:
    source = MATERIAL_SERVICE.read_text(encoding="utf-8")
    assert 'MATERIAL_COST_STATUSES = {"purchased", "in_transit", "received", "delivered_to_lab"}' in source
    assert "MaterialRequest.unit_cost * MaterialRequest.quantity" in source
    assert "MaterialRequest.status.in_(MATERIAL_COST_STATUSES)" in source
    assert "work_order.parts_cost = value" in source


def test_requests_not_yet_purchased_do_not_enter_canonical_cost() -> None:
    source = MATERIAL_SERVICE.read_text(encoding="utf-8")
    statuses = source.split("MATERIAL_COST_STATUSES =", 1)[1].split("}", 1)[0]
    assert '"awaiting_approval"' not in statuses
    assert '"approved"' not in statuses
    assert '"purchasing"' not in statuses
    assert '"cancelled"' not in statuses
