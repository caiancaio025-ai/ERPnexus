"""Garantias múltiplas com pesquisa e persistência independentes."""
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from app.laboratory.models import LaboratoryWorkOrder
from app.laboratory.schemas import WorkOrderInput, WorkOrderOutput


def test_tres_nfs_independentes_e_campo_historico_preservado():
    payload = WorkOrderInput(company_code="universo_eletronica", customer_name="Cliente", reported_defect="Defeito", warranty_invoice="100", warranty_invoice_2="200", warranty_invoice_3="300")
    assert (payload.warranty_invoice, payload.warranty_invoice_2, payload.warranty_invoice_3) == ("100", "200", "300")
    for column in ("warranty_invoice", "warranty_invoice_2", "warranty_invoice_3"):
        assert column in LaboratoryWorkOrder.__table__.columns
        assert column in WorkOrderOutput.model_fields


def test_campos_podem_ficar_vazios_ate_o_retorno():
    payload = WorkOrderInput(company_code="universo_eletronica", customer_name="Cliente", reported_defect="Defeito")
    assert payload.warranty_invoice is None
    assert payload.warranty_invoice_2 is None
    assert payload.warranty_invoice_3 is None


def test_indices_de_pesquisa_gerados_no_postgresql():
    for key in ("warranty_invoice", "warranty_invoice_2", "warranty_invoice_3"):
        stmt = select(LaboratoryWorkOrder).where(getattr(LaboratoryWorkOrder,key).ilike("%NF-123%"))
        sql = str(stmt.compile(dialect=postgresql.dialect()))
        assert key in sql


def test_campos_conectados_ao_frontend_e_ao_backend():
    root = Path(__file__).resolve().parents[2]
    service = (root / "api/app/laboratory/service.py").read_text()
    router = (root / "api/app/laboratory/router.py").read_text()
    frontend = (root / "web/src/features/laboratory/LaboratoryDashboard.tsx").read_text()
    for name in ("warranty_invoice", "warranty_invoice_2", "warranty_invoice_3"):
        assert f"work_order.{name} = payload.{name}" in service
        assert f"LaboratoryWorkOrder.{name}.ilike(term)" in service
        assert f"{name}=work_order.{name}" in router
        assert f"{name}=payload.{name}" in router
        assert name in frontend
    for i in (1,2,3):
        assert f'NF de garantia {i}' in frontend
