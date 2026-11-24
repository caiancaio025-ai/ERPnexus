"""V36: garantia de 3 pares de chave NF-e, sem alterar as NFs existentes."""
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from sqlalchemy.dialects import postgresql
from sqlalchemy import select

from app.laboratory.models import LaboratoryWorkOrder
from app.laboratory.schemas import WorkOrderInput, WorkOrderOutput
from app.laboratory.service import apply_work_order_update

ROOT = Path(__file__).resolve().parents[3]
APP = ROOT / "apps/api/app/laboratory"
WEB = ROOT / "apps/web/src/features/laboratory"
MIGRATION = ROOT / "apps/api/migrations/versions/20261123_01_warranty_invoice_access_keys.py"
KEYS = tuple(f"warranty_{kind}_invoice_access_key_{n}" for kind in ("entry", "exit") for n in (1, 2, 3))


def _payload(**changes):
    return WorkOrderInput(
        company_code="universo_eletronica",
        customer_name="Cliente de teste",
        reported_defect="Equipamento com avarias",
        **changes,
    )


def test_seis_campos_opcionais_na_modelagem_e_na_resposta():
    empty = _payload()
    for name in KEYS:
        assert getattr(empty, name) is None
        assert name in LaboratoryWorkOrder.__table__.columns
        assert LaboratoryWorkOrder.__table__.columns[name].type.length == 44
        assert name in WorkOrderOutput.model_fields


def test_seis_chaves_normalizadas_e_validadas_independentemente():
    key = "1" * 44
    for name in KEYS:
        data = _payload(**{name: " ".join([key[:22], key[22:]])})
        assert getattr(data, name) == key
        with pytest.raises(ValidationError, match="44 dígitos"):
            _payload(**{name: "12345"})
    assert _payload(warranty_entry_invoice_access_key_1="").warranty_entry_invoice_access_key_1 is None


def test_salvar_e_alterar_chaves_nao_altera_nfs_existentes():
    values = {name: str(index) * 44 for index, name in enumerate(KEYS, start=1)}
    data = _payload(
        entry_invoice="NF-E-100", exit_invoice="NF-S-200",
        entry_invoice_access_key="7" * 44, exit_invoice_access_key="8" * 44,
        warranty_entry_invoice_1="NF-G1-E", warranty_exit_invoice_1="NF-G1-S",
        **values,
    )
    model = SimpleNamespace()
    apply_work_order_update(model, data, equipment_id=99)
    for name, value in values.items():
        assert getattr(model, name) == value
    assert model.entry_invoice == "NF-E-100"
    assert model.exit_invoice == "NF-S-200"
    assert model.warranty_entry_invoice_1 == "NF-G1-E"
    assert model.warranty_exit_invoice_1 == "NF-G1-S"
    assert model.entry_invoice_access_key == "7" * 44
    assert model.exit_invoice_access_key == "8" * 44
    # Limpar apenas a chave da entrada G2, sem tocar nas outras NFs/chaves.
    modified = data.model_copy(update={"warranty_entry_invoice_access_key_2": None})
    apply_work_order_update(model, modified, equipment_id=99)
    assert model.warranty_entry_invoice_access_key_2 is None
    assert model.warranty_exit_invoice_access_key_2 == "5" * 44
    assert model.warranty_entry_invoice_1 == "NF-G1-E"


def test_pesquisa_e_api_carregam_os_seis_campos():
    src = (APP / "service.py").read_text()
    router = (APP / "router.py").read_text()
    form = (WEB / "LaboratoryDashboard.tsx").read_text()
    schema = (WEB / "types.ts").read_text()
    for name in KEYS:
        assert f"LaboratoryWorkOrder.{name}.ilike(term)" in src
        assert f"{name}=work_order.{name}" in router
        assert f"{name}=payload.{name}" in router
        assert f"form.{name}" in form
        assert f"order.{name}" in form
        assert name in schema
        query = select(LaboratoryWorkOrder).where(getattr(LaboratoryWorkOrder, name).ilike("%123%"))
        assert name in str(query.compile(dialect=postgresql.dialect()))


def test_chaves_normais_estao_dentro_do_quadro_e_garantias_individuais():
    text = (WEB / "LaboratoryDashboard.tsx").read_text()
    standard = text.split("function StandardInvoices(",1)[1].split("const warrantyCycles",1)[0]
    warranty = text.split("function WarrantyInvoices(",1)[1].split("// Dados já gravados",1)[0]
    for key in ("entry_invoice_access_key", "exit_invoice_access_key"):
        assert f"values.{key}" in standard
    assert "Chave NF entrada (44 dígitos)" not in text
    assert "Chave NF saída (44 dígitos)" not in text
    assert "entryKey" in warranty and "exitKey" in warranty
    assert "Chave NF de entrada ${round}" in warranty
    assert "Chave NF de saída ${round}" in warranty


def test_migracao_adiciona_chaves_sem_apagar_documentos():
    import importlib.util
    src = MIGRATION.read_text()
    assert 'down_revision = "20261117_01"' in src
    assert 'revision = "20261123_01"' in src
    assert 'op.add_column("laboratory_work_orders"' in src
    assert 'op.drop_column' not in src
    spec=importlib.util.spec_from_file_location('mig_v36',MIGRATION)
    module=importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    assert set(module.COLUMNS) == set(KEYS)
    assert all(name in src for name in KEYS)


def test_migracao_em_banco_de_ensaio_preserva_notas_existentes():
    """Valida o SQL ALTER TABLE em SQLite descartavel, sem tocar no PostgreSQL real."""
    import importlib.util
    from sqlalchemy import create_engine, inspect, text
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    engine=create_engine('sqlite:///:memory:')
    with engine.begin() as conn:
        conn.execute(text('CREATE TABLE laboratory_work_orders (id INTEGER PRIMARY KEY, entry_invoice VARCHAR(80), warranty_entry_invoice_1 VARCHAR(80))'))
        conn.execute(text("INSERT INTO laboratory_work_orders (id,entry_invoice,warranty_entry_invoice_1) VALUES (1,'NF-ORIGINAL','NF-G1')"))
        spec=importlib.util.spec_from_file_location('mig_v36_sqlite',MIGRATION)
        migration=importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(migration)
        migration.op=Operations(MigrationContext.configure(conn))
        migration.upgrade()
        cols={c['name'] for c in inspect(conn).get_columns('laboratory_work_orders')}
        assert set(KEYS).issubset(cols)
        row=conn.execute(text('SELECT entry_invoice, warranty_entry_invoice_1 FROM laboratory_work_orders WHERE id=1')).one()
        assert row==('NF-ORIGINAL','NF-G1')
        conn.execute(text('UPDATE laboratory_work_orders SET warranty_entry_invoice_access_key_1=:key WHERE id=1'), {'key':'9'*44})
        found=conn.execute(text('SELECT warranty_entry_invoice_access_key_1 FROM laboratory_work_orders WHERE id=1')).scalar_one()
        assert found=='9'*44
    engine.dispose()
