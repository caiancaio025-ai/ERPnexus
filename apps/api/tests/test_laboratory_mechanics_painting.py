from pathlib import Path

import pytest
from pydantic import ValidationError

from app.laboratory.schemas import PaintingDispatchCreate


API_ROOT = Path(__file__).parents[1]
WEB_ROOT = API_ROOT.parent / "web"

MIGRATION = API_ROOT / "migrations" / "versions" / "20261009_04_lab_mechanics_painting.py"
MODELS = API_ROOT / "app" / "laboratory" / "models.py"
SCHEMAS = API_ROOT / "app" / "laboratory" / "schemas.py"
ROUTER = API_ROOT / "app" / "laboratory" / "router.py"
DASHBOARD = WEB_ROOT / "src" / "features" / "laboratory" / "LaboratoryDashboard.tsx"
MECHANICS = WEB_ROOT / "src" / "features" / "laboratory" / "components" / "MechanicsPanel.tsx"
TYPES = WEB_ROOT / "src" / "features" / "laboratory" / "types.ts"
CSS = WEB_ROOT / "src" / "features" / "laboratory" / "laboratory.css"
DOC_PANEL = WEB_ROOT / "src" / "features" / "laboratory" / "components" / "EquipmentDocumentsPanel.tsx"


def test_migration_is_chained_after_configurable_map() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    assert 'revision: str = "20261009_04"' in source
    assert 'down_revision: str | None = "20261009_03"' in source
    assert '"laboratory_mechanical_painting_dispatches"' in source
    assert '"laboratory_mechanical_painting_items"' in source
    assert '"laboratory_mechanical_painting_photos"' in source


def test_models_preserve_external_painting_chain_of_custody() -> None:
    source = MODELS.read_text(encoding="utf-8")
    assert "class LaboratoryMechanicalPaintingDispatch(Base):" in source
    assert "sent_at: Mapped[datetime | None]" in source
    assert "returned_at: Mapped[datetime | None]" in source
    assert "class LaboratoryMechanicalPaintingItem(Base):" in source
    assert "returned: Mapped[bool]" in source
    assert "class LaboratoryMechanicalPaintingPhoto(Base):" in source
    assert 'phase: Mapped[str] = mapped_column(String(20), default="outbound"' in source


def test_painting_create_accepts_free_form_items_and_rejects_empty_checklist() -> None:
    payload = PaintingDispatchCreate(
        provider="Pintura Externa Teste",
        notes="Azul industrial",
        items=["Tampa frontal", " Flange ", ""],
    )
    assert payload.items == ["Tampa frontal", "Flange"]

    with pytest.raises(ValidationError):
        PaintingDispatchCreate(items=["", "   "])


def test_mechanics_routes_cover_draft_evidence_send_return_checklist_and_return() -> None:
    source = ROUTER.read_text(encoding="utf-8")
    assert '"/work-orders/{work_order_id}/mechanics/painting"' in source
    assert "async def list_mechanics_painting" in source
    assert "async def create_mechanics_painting" in source
    assert '"/mechanics/painting/{dispatch_id}/photos"' in source
    assert '"/mechanics/painting/{dispatch_id}/send"' in source
    assert '"/mechanics/painting/items/{item_id}"' in source
    assert '"/mechanics/painting/{dispatch_id}/return"' in source


def test_send_requires_outbound_photo_and_return_requires_all_items_checked() -> None:
    source = ROUTER.read_text(encoding="utf-8")
    assert "Anexe ao menos uma foto do material antes de confirmar a saída para pintura." in source
    assert "Existem {pending} item(ns) sem conferência de retorno." in source
    assert 'dispatch.status = "sent"' in source
    assert 'dispatch.status = "returned"' in source
    assert 'action="painting_dispatch_sent"' in source
    assert 'action="painting_dispatch_returned"' in source


def test_painting_photos_use_existing_laboratory_document_storage_safely() -> None:
    source = ROUTER.read_text(encoding="utf-8")
    schemas = SCHEMAS.read_text(encoding="utf-8")
    assert 'category="pintura"' in source
    assert "commit_laboratory_document" in source
    assert "Fotos da saída só podem ser anexadas antes do envio." in source
    assert "Fotos do retorno só podem ser anexadas enquanto a pintura aguarda retorno." in source
    assert "delete_laboratory_document_storage" in source
    assert 'DocumentCategory = Literal["entrada", "analise", "reparo", "testes", "saida", "pintura", "general"]' in schemas
    assert 'document.category !== "pintura"' in DOC_PANEL.read_text(encoding="utf-8")


def test_mechanics_tab_is_immediately_before_history() -> None:
    source = DASHBOARD.read_text(encoding="utf-8")
    mechanics = source.index('onClick={() => onTab("mechanics")}>Mecânica</TabButton>')
    history = source.index('onClick={() => onTab("history")}>Histórico</TabButton>')
    assert mechanics < history
    assert 'tab === "mechanics" && <MechanicsPanel workOrderId={detail.id}' in source


def test_mechanics_ui_has_free_checklist_photo_departure_and_return_confirmation() -> None:
    source = MECHANICS.read_text(encoding="utf-8")
    assert "Checklist do que vai sair" in source
    assert "Criar controle de pintura" in source
    assert "Evidência da saída" in source
    assert "Anexe ao menos uma foto" in source
    assert "Conferência de retorno" in source
    assert "Confirmar retorno completo" in source
    assert "CameraCapture" in source


def test_location_history_is_exposed_with_dwell_time_and_shown_in_history_tab() -> None:
    router = ROUTER.read_text(encoding="utf-8")
    dash = DASHBOARD.read_text(encoding="utf-8")
    types = TYPES.read_text(encoding="utf-8")
    assert '"/work-orders/{work_order_id}/location-history"' in router
    assert "duration_seconds = max(0, int((end - history.assigned_at).total_seconds()))" in router
    assert "export type LocationHistory" in types
    assert "Movimentação física" in dash
    assert "permanência {formatDuration(item.duration_seconds)}" in dash
    assert 'if (nextTab === "history")' in dash


def test_mechanics_styles_are_scoped_to_laboratory_module() -> None:
    source = CSS.read_text(encoding="utf-8")
    assert "/* -------------------------------------------------------------- Mechanics */" in source
    assert ".lab-mechanics" in source
    assert ".lab-paint-card" in source
    assert ".lab-history-grid" in source
