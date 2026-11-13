"""Inventario com localizacao fisica, serie/lote, consumo e fotos.

Revision ID: 20261022_01
Revises: 20261013_02
"""
from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "20261022_01"
down_revision: str | None = "20261013_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table("inventory_location_types",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("code", sa.String(32), nullable=False, unique=True),
        sa.Column("name", sa.String(90), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
    )
    op.create_table("inventory_areas",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("code", sa.String(24), nullable=False, unique=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
    )
    op.create_table("inventory_containers",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("area_id", sa.Integer, sa.ForeignKey("inventory_areas.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("type_id", sa.Integer, sa.ForeignKey("inventory_location_types.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("parent_id", sa.Integer, sa.ForeignKey("inventory_containers.id", ondelete="RESTRICT")),
        sa.Column("code", sa.String(40), nullable=False, unique=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("rows", sa.Integer, nullable=False, server_default="1"),
        sa.Column("columns", sa.Integer, nullable=False, server_default="1"),
        sa.Column("layout_row", sa.Integer, nullable=False, server_default="1"),
        sa.Column("layout_column", sa.Integer, nullable=False, server_default="1"),
        sa.Column("layout_span", sa.Integer, nullable=False, server_default="1"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.CheckConstraint("rows > 0 AND columns > 0", name="ck_inventory_container_shape"),
    )
    op.create_table("inventory_slots",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("container_id", sa.Integer, sa.ForeignKey("inventory_containers.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("code", sa.String(52), nullable=False, unique=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("row", sa.Integer, nullable=False),
        sa.Column("column", sa.Integer, nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("container_id", "row", "column", name="uq_inv_slot_coordinate"),
    )
    op.create_table("inventory_items",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("stock_code", sa.String(30), nullable=False, unique=True),
        sa.Column("company_code", sa.String(40), nullable=False),
        sa.Column("name", sa.String(220), nullable=False),
        sa.Column("category", sa.String(80), nullable=False, server_default="outros"),
        sa.Column("manufacturer", sa.String(120)),
        sa.Column("model", sa.String(120)),
        sa.Column("mode", sa.String(12), nullable=False),
        sa.Column("manufacturer_serial", sa.String(120)),
        sa.Column("serial_normalized", sa.String(120)),
        sa.Column("unit", sa.String(12), nullable=False, server_default="UN"),
        sa.Column("quantity", sa.Integer, nullable=False, server_default="0"),
        sa.Column("unit_cost", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("slot_id", sa.Integer, sa.ForeignKey("inventory_slots.id", ondelete="RESTRICT")),
        sa.Column("notes", sa.Text),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("company_code", "serial_normalized", name="uq_inv_company_serial"),
        sa.CheckConstraint("quantity >= 0", name="ck_inv_nonnegative_quantity"),
        sa.CheckConstraint("mode != 'serialized' OR quantity <= 1", name="ck_inv_serial_single_unit"),
        sa.CheckConstraint("mode IN ('serialized','bulk')", name="ck_inv_item_mode"),
    )
    op.create_table("inventory_movements",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("item_id", sa.Integer, sa.ForeignKey("inventory_items.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("work_order_id", sa.Integer, sa.ForeignKey("laboratory_work_orders.id", ondelete="RESTRICT")),
        sa.Column("reversal_of_id", sa.Integer, sa.ForeignKey("inventory_movements.id", ondelete="RESTRICT")),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("quantity", sa.Integer, nullable=False),
        sa.Column("unit_cost", sa.Numeric(14, 2), nullable=False),
        sa.Column("note", sa.String(500)),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("quantity > 0", name="ck_inv_movement_qty_positive"),
        sa.CheckConstraint("kind IN ('receipt','issue','return')", name="ck_inv_movement_kind"),
    )
    op.create_table("inventory_photos",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("item_id", sa.Integer, sa.ForeignKey("inventory_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("filename", sa.String(120), nullable=False),
        sa.Column("mime_type", sa.String(40), nullable=False),
        sa.Column("created_by", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table("inventory_location_history",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("item_id", sa.Integer, sa.ForeignKey("inventory_items.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("previous_slot_id", sa.Integer, sa.ForeignKey("inventory_slots.id", ondelete="RESTRICT")),
        sa.Column("new_slot_id", sa.Integer, sa.ForeignKey("inventory_slots.id", ondelete="RESTRICT")),
        sa.Column("moved_by", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    for table, columns in {
        "inventory_containers": ["area_id", "type_id", "parent_id"],
        "inventory_slots": ["container_id"],
        "inventory_items": ["company_code", "name", "stock_code", "slot_id"],
        "inventory_movements": ["item_id", "work_order_id", "reversal_of_id"],
        "inventory_photos": ["item_id"],
        "inventory_location_history": ["item_id"],
    }.items():
        for column in columns:
            op.create_index(f"ix_{table}_{column}", table, [column])
    types = sa.table("inventory_location_types", sa.column("code", sa.String), sa.column("name", sa.String))
    op.bulk_insert(types, [
        {"code": "estante", "name": "Estante"},
        {"code": "gaveta", "name": "Gaveta"},
        {"code": "caixa", "name": "Caixa"},
        {"code": "galeria", "name": "Galeria"},
        {"code": "armario", "name": "Armário"},
        {"code": "prateleira", "name": "Prateleira"},
        {"code": "bancada", "name": "Bancada"},
    ])


def downgrade() -> None:
    # Impedir perda acidental de movimentacoes historicas por downgrade automatico.
    raise RuntimeError("Downgrade de estoque exige plano de preservacao e migracao dos dados.")
