from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.finance.schemas import FinancialScheduleUpdate
from app.laboratory.schemas import InactivateWorkOrderInput, WorkOrderInput
from app.laboratory.models import LaboratoryWorkOrder


def test_nf_garantia_campo_separado():
    payload = WorkOrderInput(company_code="universo_eletronica", customer_name="Cliente", reported_defect="Falha", entry_invoice="100", exit_invoice="101", warranty_invoice="102")
    assert (payload.entry_invoice, payload.exit_invoice, payload.warranty_invoice) == ("100", "101", "102")
    assert "warranty_invoice" in LaboratoryWorkOrder.__table__.columns


def test_inativacao_exige_motivo_e_versao():
    with pytest.raises(ValidationError):
        InactivateWorkOrderInput(version=1, reason="Erro")
    assert InactivateWorkOrderInput(version=2, reason="Cadastro duplicado").version == 2
    for name in ("is_inactive", "inactivation_reason", "inactivated_by", "inactivated_at"):
        assert name in LaboratoryWorkOrder.__table__.columns


def _schedule():
    return dict(total_amount=Decimal("150.00"), installments=[
        dict(installment_number=1, due_date=date(2026, 11, 1), amount=Decimal("50.00")),
        dict(installment_number=2, due_date=date(2026, 12, 1), amount=Decimal("100.00")),
    ])


def test_edicao_parcelamento_validada():
    payload = FinancialScheduleUpdate(**_schedule())
    assert len(payload.installments) == 2
    assert payload.total_amount == Decimal("150.00")


def test_parcelas_nao_podem_perder_total_ou_sequencia():
    data = _schedule()
    data["installments"][1]["amount"] = Decimal("90.00")
    with pytest.raises(ValidationError, match="soma das parcelas"):
        FinancialScheduleUpdate(**data)
    data = _schedule()
    data["installments"][1]["installment_number"] = 3
    with pytest.raises(ValidationError, match="sequencial"):
        FinancialScheduleUpdate(**data)


def test_parcela_id_duplicada_e_bloqueada():
    data = _schedule()
    data["installments"][0]["entry_id"] = 25
    data["installments"][1]["entry_id"] = 25
    with pytest.raises(ValidationError, match="parcela não pode aparecer duas vezes"):
        FinancialScheduleUpdate(**data)
