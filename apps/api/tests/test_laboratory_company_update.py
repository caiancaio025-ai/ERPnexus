from types import SimpleNamespace

from app.laboratory.service import apply_work_order_update
from app.laboratory.schemas import WorkOrderUpdate


def test_apply_work_order_update_persists_company_change() -> None:
    work_order = SimpleNamespace(
        company_code="universo_eletronica",
        equipment_id=1,
        customer_id=5,
        customer_name="Cliente antigo",
        equipment_serial="OLD",
        priority="normal",
        reported_defect="Defeito antigo",
        entry_condition=None,
        accessories_received=None,
        assigned_technician_id=None,
        entry_invoice=None,
        exit_invoice=None,
        parts_cost=None,
        quoted_value=None,
        approved_value=None,
        internal_notes=None,
        customer_notes=None,
    )
    payload = WorkOrderUpdate(
        company_code="universo_automacao",
        customer_id=5,
        customer_name="Cliente correto",
        serial_number="SERIE-1",
        manufacturer="WEG",
        model="CFW11",
        equipment_type="Inversor",
        power=None,
        voltage=None,
        entry_invoice="123",
        exit_invoice=None,
        assigned_technician_id=None,
        priority="high",
        reported_defect="Defeito atualizado",
        entry_condition="Recebido",
        accessories_received=None,
        parts_cost="10.00",
        quoted_value="20.00",
        approved_value="20.00",
        internal_notes="nota",
        customer_notes=None,
        version=3,
    )

    apply_work_order_update(work_order, payload, equipment_id=99)

    assert work_order.company_code == "universo_automacao"
    assert work_order.equipment_id == 99
    assert work_order.customer_name == "Cliente correto"
    assert work_order.equipment_serial == "SERIE-1"
    assert work_order.priority == "high"
    assert work_order.entry_invoice == "123"
