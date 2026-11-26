"""Minimal catalogues for isolated stock receipt tests without Alembic seeds."""
from app.commercial.models import CommercialCompanyProfile
from app.inventory.models import InventoryComponentCategory


def receipt_catalog_rows(*, user_id=1):
    return [
        CommercialCompanyProfile(company_code="universo_eletronica", legal_name="Empresa de testes", created_by=user_id),
        *[InventoryComponentCategory(code=code, name=code) for code in ("componentes", "modulo", "resistor", "capacitor", "outros")],
    ]
