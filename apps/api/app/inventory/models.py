"""Modelos de estoque independentes do patrimônio comercial e do laboratório."""
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models import Base


class InventoryLocationType(Base):
    __tablename__ = "inventory_location_types"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(90))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class InventoryComponentCategory(Base):
    """Tipos de componentes configuráveis, sem alterar os códigos históricos."""
    __tablename__ = "inventory_component_categories"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class InventoryComponentSubtype(Base):
    """Ex.: capacitor eletrolítico, cerâmico ou poliéster."""
    __tablename__ = "inventory_component_subtypes"
    __table_args__ = (UniqueConstraint("category", "code", name="uq_inv_subtype_category_code"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    category: Mapped[str] = mapped_column(String(80), index=True)
    code: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(120))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class InventoryComponentFormat(Base):
    """Encapsulamento/formato pesquisável e extensível por categoria técnica."""
    __tablename__ = "inventory_component_formats"
    __table_args__ = (UniqueConstraint("category", "code", name="uq_inv_format_category_code"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    category: Mapped[str] = mapped_column(String(80), index=True)
    code: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(120))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class InventoryArea(Base):
    __tablename__ = "inventory_areas"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(24), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class InventoryContainer(Base):
    __tablename__ = "inventory_containers"
    __table_args__ = (CheckConstraint("rows > 0 AND columns > 0", name="ck_inventory_container_shape"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    area_id: Mapped[int] = mapped_column(ForeignKey("inventory_areas.id", ondelete="RESTRICT"), index=True)
    type_id: Mapped[int] = mapped_column(ForeignKey("inventory_location_types.id", ondelete="RESTRICT"), index=True)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("inventory_containers.id", ondelete="RESTRICT"), index=True)
    code: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    rows: Mapped[int] = mapped_column(Integer, default=1)
    columns: Mapped[int] = mapped_column(Integer, default=1)
    layout_row: Mapped[int] = mapped_column(Integer, default=1)
    layout_column: Mapped[int] = mapped_column(Integer, default=1)
    layout_span: Mapped[int] = mapped_column(Integer, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class InventorySlot(Base):
    __tablename__ = "inventory_slots"
    __table_args__ = (UniqueConstraint("container_id", "row", "column", name="uq_inv_slot_coordinate"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    container_id: Mapped[int] = mapped_column(ForeignKey("inventory_containers.id", ondelete="RESTRICT"), index=True)
    code: Mapped[str] = mapped_column(String(52), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    row: Mapped[int] = mapped_column(Integer)
    column: Mapped[int] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class InventoryItem(Base):
    __tablename__ = "inventory_items"
    __table_args__ = (
        UniqueConstraint("company_code", "serial_normalized", name="uq_inv_company_serial"),
        CheckConstraint("quantity >= 0", name="ck_inv_nonnegative_quantity"),
        CheckConstraint("mode != 'serialized' OR quantity <= 1", name="ck_inv_serial_single_unit"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    stock_code: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    company_code: Mapped[str] = mapped_column(String(40), index=True)
    name: Mapped[str] = mapped_column(String(220), index=True)
    category: Mapped[str] = mapped_column(String(80), default="outros")
    subtype_id: Mapped[int | None] = mapped_column(ForeignKey("inventory_component_subtypes.id", ondelete="RESTRICT"), index=True)
    format_id: Mapped[int | None] = mapped_column(ForeignKey("inventory_component_formats.id", ondelete="RESTRICT"), index=True)
    manufacturer: Mapped[str | None] = mapped_column(String(120))
    model: Mapped[str | None] = mapped_column(String(120))
    mode: Mapped[str] = mapped_column(String(12))  # serialized | bulk
    manufacturer_serial: Mapped[str | None] = mapped_column(String(120))
    serial_normalized: Mapped[str | None] = mapped_column(String(120))
    unit: Mapped[str] = mapped_column(String(12), default="UN")
    quantity: Mapped[int] = mapped_column(Integer, default=0)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    slot_id: Mapped[int | None] = mapped_column(ForeignKey("inventory_slots.id", ondelete="RESTRICT"), index=True)
    notes: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class InventoryMovement(Base):
    __tablename__ = "inventory_movements"
    __table_args__ = (CheckConstraint("quantity > 0", name="ck_inv_movement_qty_positive"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("inventory_items.id", ondelete="RESTRICT"), index=True)
    work_order_id: Mapped[int | None] = mapped_column(ForeignKey("laboratory_work_orders.id", ondelete="RESTRICT"), index=True)
    reversal_of_id: Mapped[int | None] = mapped_column(ForeignKey("inventory_movements.id", ondelete="RESTRICT"), index=True)
    purchase_order_id: Mapped[int | None] = mapped_column(ForeignKey("purchase_orders.id", ondelete="RESTRICT"), unique=True)
    material_request_id: Mapped[int | None] = mapped_column(ForeignKey("material_requests.id", ondelete="RESTRICT"), unique=True)
    kind: Mapped[str] = mapped_column(String(20))  # receipt | issue | return
    quantity: Mapped[int] = mapped_column(Integer)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(14, 2))  # fotografia historica
    note: Mapped[str | None] = mapped_column(String(500))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class InventoryPhoto(Base):
    __tablename__ = "inventory_photos"
    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("inventory_items.id", ondelete="CASCADE"), index=True)
    filename: Mapped[str] = mapped_column(String(120))
    mime_type: Mapped[str] = mapped_column(String(40))
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class InventoryLocationHistory(Base):
    """Audita mudanças de posição sem reaproveitar o histórico de OS do laboratório."""
    __tablename__ = "inventory_location_history"
    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("inventory_items.id", ondelete="RESTRICT"), index=True)
    previous_slot_id: Mapped[int | None] = mapped_column(ForeignKey("inventory_slots.id", ondelete="RESTRICT"))
    new_slot_id: Mapped[int | None] = mapped_column(ForeignKey("inventory_slots.id", ondelete="RESTRICT"))
    # Capturas textuais permitem excluir a posição física sem apagar o histórico.
    previous_slot_code: Mapped[str | None] = mapped_column(String(52))
    new_slot_code: Mapped[str | None] = mapped_column(String(52))
    moved_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
