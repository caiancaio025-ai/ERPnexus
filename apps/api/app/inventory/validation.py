"""Shared catalogue validation for manual creation and purchasing receipts."""
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.commercial.models import CommercialCompanyProfile
from app.inventory.models import (
    InventoryComponentCategory, InventoryComponentFormat, InventoryComponentSubtype,
    InventoryContainer, InventorySlot,
)


async def valid_slot(db: AsyncSession, slot_id: int | None) -> InventorySlot | None:
    if slot_id is None:
        return None
    slot = await db.get(InventorySlot, slot_id)
    if slot is None or not slot.is_active:
        raise HTTPException(422, "Posição de estoque inválida.")
    container = await db.get(InventoryContainer, slot.container_id)
    if container is None or not container.is_active:
        raise HTTPException(422, "Local de estoque inativo.")
    return slot


async def valid_category(db: AsyncSession, category: str) -> None:
    result = await db.scalar(select(InventoryComponentCategory.id).where(
        InventoryComponentCategory.code == category.strip().lower(),
        InventoryComponentCategory.is_active.is_(True),
    ))
    if result is None:
        raise HTTPException(422, "Tipo de componente inexistente. Cadastre-o nas configurações do Estoque.")


async def valid_subtype(db: AsyncSession, subtype_id: int | None, category: str) -> None:
    if subtype_id is None:
        return
    subtype = await db.get(InventoryComponentSubtype, subtype_id)
    if subtype is None or not subtype.is_active or subtype.category != category.strip().lower():
        raise HTTPException(422, "Subtipo incompatível ou inativo para o componente.")


async def valid_format(db: AsyncSession, format_id: int | None, category: str) -> None:
    if format_id is None:
        return
    row = await db.get(InventoryComponentFormat, format_id)
    if row is None or not row.is_active or row.category != category.strip().lower():
        raise HTTPException(422, "Formato não pertence à categoria informada ou está inativo.")


async def valid_company(db: AsyncSession, company_code: str) -> None:
    active_company = await db.scalar(select(CommercialCompanyProfile.id).where(
        CommercialCompanyProfile.company_code == company_code,
        CommercialCompanyProfile.is_active.is_(True),
    ))
    if active_company is None:
        raise HTTPException(422, "Empresa do estoque inválida ou inativa.")
