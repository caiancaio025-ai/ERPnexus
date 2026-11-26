"""Optional stock metadata saved while a purchase is still being arranged."""
from pydantic import BaseModel, ConfigDict, Field, field_validator


class InventoryItemDetails(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subtype_id: int | None = Field(default=None, gt=0)
    manufacturer: str | None = Field(default=None, max_length=120)
    model: str | None = Field(default=None, max_length=120)
    unit: str = Field(default="UN", max_length=12)
    slot_id: int | None = Field(default=None, gt=0)
    notes: str | None = Field(default=None, max_length=4000)

    @field_validator("manufacturer", "model", "notes")
    @classmethod
    def optional_text(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None

    @field_validator("unit")
    @classmethod
    def unit_label(cls, value: str) -> str:
        return value.strip() or "UN"


def canonical_inventory_details(value: InventoryItemDetails | dict | None) -> dict:
    if isinstance(value, InventoryItemDetails):
        return value.model_dump()
    return InventoryItemDetails.model_validate(value or {}).model_dump()


def merge_inventory_details(
    current: dict | None, incoming: InventoryItemDetails | None, *, supplied: bool,
) -> dict | None:
    """Omission preserves saved fields; explicit null clears a pending plan."""
    if not supplied:
        return current
    if incoming is None:
        return None
    values = {**(current or {}), **incoming.model_dump(exclude_unset=True)}
    return canonical_inventory_details(values)
