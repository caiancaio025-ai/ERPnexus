"""Encapsulamentos editáveis e origem única para recebimento automático de compras.

Revision ID: 20261022_02
Revises: 20261022_01
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261022_02"
down_revision: str | None = "20261022_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "inventory_component_formats",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("category", sa.String(80), nullable=False),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("category", "code", name="uq_inv_format_category_code"),
    )
    op.create_index("ix_inventory_component_formats_category", "inventory_component_formats", ["category"])
    op.add_column("inventory_items", sa.Column("format_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_inventory_items_format_id", "inventory_items", "inventory_component_formats", ["format_id"], ["id"], ondelete="RESTRICT")
    op.create_index("ix_inventory_items_format_id", "inventory_items", ["format_id"])
    op.add_column("inventory_movements", sa.Column("purchase_order_id", sa.Integer(), nullable=True))
    op.add_column("inventory_movements", sa.Column("material_request_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_inventory_movements_purchase", "inventory_movements", "purchase_orders", ["purchase_order_id"], ["id"], ondelete="RESTRICT")
    op.create_foreign_key("fk_inventory_movements_request", "inventory_movements", "material_requests", ["material_request_id"], ["id"], ondelete="RESTRICT")
    op.create_unique_constraint("uq_inv_movements_purchase_once", "inventory_movements", ["purchase_order_id"])
    op.create_unique_constraint("uq_inv_movements_request_once", "inventory_movements", ["material_request_id"])
    formats = sa.table("inventory_component_formats", sa.column("category", sa.String), sa.column("code", sa.String), sa.column("name", sa.String))
    op.bulk_insert(formats, [
        {"category": "resistor", "code": "pth", "name": "PTH / axial"},
        {"category": "resistor", "code": "smd", "name": "SMD"},
        {"category": "capacitor", "code": "radial", "name": "PTH radial"},
        {"category": "capacitor", "code": "axial", "name": "PTH axial"},
        {"category": "capacitor", "code": "smd", "name": "SMD"},
        {"category": "transistor", "code": "to92", "name": "TO-92"},
        {"category": "transistor", "code": "to220", "name": "TO-220"},
        {"category": "transistor", "code": "to247", "name": "TO-247"},
        {"category": "transistor", "code": "sot23", "name": "SOT-23"},
        {"category": "transistor", "code": "sot223", "name": "SOT-223"},
        {"category": "transistor", "code": "smd", "name": "Outros SMD"},
        {"category": "diodo", "code": "pth", "name": "PTH"},
        {"category": "diodo", "code": "smd", "name": "SMD"},
        {"category": "igbt", "code": "modulo", "name": "Módulo de potência"},
        {"category": "igbt", "code": "to247", "name": "TO-247"},
    ])
    # Uma área padrão apenas quando não há nenhuma; áreas existentes são preservadas.
    op.execute(sa.text("""
        INSERT INTO inventory_areas (code, name, is_active)
        SELECT 'ALM', 'Almoxarifado', TRUE
        WHERE NOT EXISTS (SELECT 1 FROM inventory_areas)
    """))


def downgrade() -> None:
    raise RuntimeError("Downgrade de estoque requer preservar formatos e vínculos de compras.")
