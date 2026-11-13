from pathlib import Path

from app.commercial.schemas import CompanyProfileInput
from app.laboratory.schemas import WorkOrderInput


API_ROOT = Path(__file__).parents[1]
WEB_ROOT = API_ROOT.parent / "web"
MIGRATION = API_ROOT / "migrations" / "versions" / "20261009_02_config_master_foundation.py"
LAB_MODELS = API_ROOT / "app" / "laboratory" / "models.py"
LAB_ROUTER = API_ROOT / "app" / "laboratory" / "router.py"
LAB_SERVICE = API_ROOT / "app" / "laboratory" / "service.py"
LAB_PDF = API_ROOT / "app" / "laboratory" / "quote_pdf.py"
LAB_DASH = WEB_ROOT / "src" / "features" / "laboratory" / "LaboratoryDashboard.tsx"
MASTER_PANEL = WEB_ROOT / "src" / "features" / "laboratory" / "components" / "ConfigMasterPanel.tsx"
COMMERCIAL_DASH = WEB_ROOT / "src" / "features" / "commercial" / "CommercialDashboard.tsx"


def test_config_master_migration_is_chained_and_additive() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    assert 'down_revision: str | None = "20261009_01"' in source
    assert '"laboratory_areas"' in source
    assert '"laboratory_racks"' in source
    assert '"laboratory_locations"' in source
    assert 'op.add_column("laboratory_quotes", sa.Column("company_snapshot"' in source
    assert '("EXP", "Expedição", 10)' in source
    assert '("LAB", "Laboratório", 20)' in source
    assert '("MEC", "Mecânica", 30)' in source


def test_models_expose_configurable_physical_structure_and_quote_snapshot() -> None:
    source = LAB_MODELS.read_text(encoding="utf-8")
    assert "class LaboratoryArea(Base):" in source
    assert "class LaboratoryRack(Base):" in source
    assert "class LaboratoryLocation(Base):" in source
    assert "company_snapshot: Mapped[str | None]" in source


def test_company_codes_are_no_longer_limited_to_three_literal_values() -> None:
    company = CompanyProfileInput(company_code="nova_empresa", legal_name="Nova Empresa Ltda")
    assert company.company_code == "nova_empresa"
    work_order = WorkOrderInput(
        company_code="nova_empresa",
        customer_name="Cliente",
        reported_defect="Teste",
        storage_location="LAB",
    )
    assert work_order.company_code == "nova_empresa"
    assert work_order.storage_location == "LAB"


def test_lab_exposes_master_company_and_location_configuration_routes() -> None:
    source = LAB_ROUTER.read_text(encoding="utf-8")
    assert '@router.get("/settings/companies"' in source
    assert '@router.post("/settings/companies"' in source
    assert '@router.get("/settings/locations"' in source
    assert '@router.post("/settings/areas"' in source
    assert '@router.post("/settings/racks"' in source


def test_location_service_uses_database_as_source_of_truth() -> None:
    source = LAB_SERVICE.read_text(encoding="utf-8")
    assert "async def active_physical_locations" in source
    assert "LaboratoryLocation.code == normalized" in source
    assert "locations = await active_physical_locations(db)" in source


def test_lab_quote_uses_master_company_profile_and_emission_snapshot() -> None:
    router = LAB_ROUTER.read_text(encoding="utf-8")
    pdf = LAB_PDF.read_text(encoding="utf-8")
    assert "quote.company_snapshot = json.dumps" in router
    assert "json.loads(quote.company_snapshot)" in router
    assert "DEFAULT_COMPANY" in pdf
    assert "COMPANIES =" not in pdf
    assert "company_profile: dict[str, object | None] | None = None" in pdf


def test_frontend_has_config_master_and_dynamic_area_map() -> None:
    dash = LAB_DASH.read_text(encoding="utf-8")
    panel = MASTER_PANEL.read_text(encoding="utf-8")
    commercial = COMMERCIAL_DASH.read_text(encoding="utf-8")
    assert "ConfigMasterPanel" in dash
    assert 'setTab("companies")' in dash
    assert 'setTab("locations")' in dash
    assert "lab-area-tabs" in dash
    assert "Nova ala" in panel
    assert "Nova estante" in panel
    assert "Código interno" in panel
    assert "Object.entries(companyLabels)" not in commercial


def test_config_master_prevents_hiding_occupied_structure() -> None:
    source = LAB_ROUTER.read_text(encoding="utf-8")
    assert "Não é possível inativar uma ala que possui equipamentos localizados." in source
    assert "Não é possível inativar uma estante que possui equipamentos localizados." in source


def test_config_master_ui_allows_activate_and_deactivate_without_deleting_history() -> None:
    panel = MASTER_PANEL.read_text(encoding="utf-8")
    assert "async function toggleArea" in panel
    assert "async function toggleRack" in panel
    assert '"Inativar" : "Reativar"' in panel
