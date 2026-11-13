"""Reconcile the commercial label with the canonical inventory item name."""
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.inventory.models import InventoryItem
from app.purchasing.schemas import PurchaseInput

async def _purchase_with_canonical_inventory_name(
    db: AsyncSession, payload: PurchaseInput
) -> PurchaseInput:
    """Stock identity is authoritative; never trust a custom name for a linked SKU."""
    if payload.inventory_destination != "existing" or payload.inventory_item_id is None:
        return payload
    item = await db.get(InventoryItem, payload.inventory_item_id)
    if item is None or not item.is_active or item.company_code != payload.company_code or item.mode != "bulk":
        raise HTTPException(422, "Item de estoque inexistente, de outra empresa ou não acumulável.")
    return payload.model_copy(update={"inventory_name": item.name})


