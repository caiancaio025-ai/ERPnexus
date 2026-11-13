"""Contrato V5: compra tem título próprio, e estoque mantém nome canônico."""
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from app.purchasing.schemas import PurchaseInput
from app.purchasing.stock_names import _purchase_with_canonical_inventory_name

WEB = Path(__file__).parents[2] / "web" / "src" / "features"


def payload(**kw):
    values = dict(company_code="universo_eletronica", supplier_id=1,
                  product_name="Kit promoção 50 resistores", quantity=50,
                  total_amount=Decimal("140"), purchase_date=date(2026, 10, 26),
                  estimated_delivery_date=date(2026, 10, 28))
    values.update(kw)
    return PurchaseInput(**values)


def test_new_stock_item_has_its_own_name_on_delivery():
    purchase = payload(inventory_destination="new", inventory_name="Resistor SMD 10k",
                       status="delivered", inventory_mode="bulk")
    assert purchase.product_name == "Kit promoção 50 resistores"
    assert purchase.inventory_name == "Resistor SMD 10k"
    assert payload().inventory_destination is None
    assert payload(inventory_destination="new").inventory_name is None  # editável antes do recebimento
    with pytest.raises(ValueError, match="nome do item no Estoque"):
        payload(inventory_destination="new", inventory_name="  ", status="delivered")


@pytest.mark.asyncio
async def test_existing_stock_uses_authoritative_catalog_name():
    item = SimpleNamespace(id=12, name="Capacitor eletrolítico 470uF", mode="bulk", is_active=True,
                           company_code="universo_eletronica")
    db = SimpleNamespace(get=AsyncMock(return_value=item))
    base = payload(inventory_destination="existing", inventory_item_id=12,
                   inventory_name="nome inventado no formulario")
    revised = await _purchase_with_canonical_inventory_name(db, base)
    assert revised.product_name == "Kit promoção 50 resistores"
    assert revised.inventory_name == item.name
    assert base.inventory_name == "nome inventado no formulario"  # não mutar entrada original
    item.company_code = "solucoes_eletronica"
    with pytest.raises(HTTPException) as error:
        await _purchase_with_canonical_inventory_name(db, base)
    assert error.value.status_code == 422


def test_editor_always_distinguishes_purchase_title_from_stock_identity():
    src = (WEB / "purchasing" / "PurchasingDashboard.tsx").read_text(encoding="utf-8")
    assert 'label="Título / descrição da compra*"' in src
    assert 'Nome técnico do novo item no Estoque' in src
    assert 'Nome adotado do item já cadastrado' in src
    assert 'selectedStock?.name' in src
    assert 'selected_id=' in src
    assert 'purchase-name-comparison' in src
    picker = (WEB / "inventory" / "PurchaseStockDestination.tsx").read_text(encoding="utf-8")
    assert 'inventory_name: chosen?.name' in picker
    assert 'selected_id=${id}' in picker


def test_stock_map_and_popups_use_dark_blue_surfaces():
    css = (WEB / "inventory" / "inventory.css").read_text(encoding="utf-8")
    assert '.inv-app .inv-map .inv-area' in css
    assert '.inv-quick-filters' in css
    assert '#10283c' in css
    picker_css = (WEB / "inventory" / "purchaseStockDestination.css").read_text(encoding="utf-8")
    assert 'background:#09243a' in picker_css
