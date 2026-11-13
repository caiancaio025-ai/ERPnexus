"""individualize commercial assets and add patrimony locations

Revision ID: 20261013_02
Revises: 20261013_01
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261013_02"
down_revision: str | None = "20261013_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("commercial_equipment", sa.Column("patrimony_code", sa.String(length=20), nullable=True))
    op.add_column("commercial_equipment", sa.Column("manufacturer_serial", sa.String(length=120), nullable=True))

    op.create_table(
        "commercial_asset_areas",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=12), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("code", name="uq_commercial_asset_area_code"),
    )
    op.create_index("ix_commercial_asset_areas_code", "commercial_asset_areas", ["code"])
    op.create_index("ix_commercial_asset_areas_sort_order", "commercial_asset_areas", ["sort_order"])
    op.create_index("ix_commercial_asset_areas_is_active", "commercial_asset_areas", ["is_active"])
    op.create_index("ix_commercial_asset_areas_created_by", "commercial_asset_areas", ["created_by"])

    op.create_table(
        "commercial_asset_racks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("area_id", sa.Integer(), sa.ForeignKey("commercial_asset_areas.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("code", sa.String(length=12), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("position_prefix", sa.String(length=6), nullable=False),
        sa.Column("rows", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("columns", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("layout_row", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("layout_column", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("layout_span", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("code", name="uq_commercial_asset_rack_code"),
    )
    op.create_index("ix_commercial_asset_racks_area_id", "commercial_asset_racks", ["area_id"])
    op.create_index("ix_commercial_asset_racks_code", "commercial_asset_racks", ["code"])
    op.create_index("ix_commercial_asset_racks_sort_order", "commercial_asset_racks", ["sort_order"])
    op.create_index("ix_commercial_asset_racks_is_active", "commercial_asset_racks", ["is_active"])
    op.create_index("ix_commercial_asset_racks_created_by", "commercial_asset_racks", ["created_by"])

    op.create_table(
        "commercial_asset_locations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("area_id", sa.Integer(), sa.ForeignKey("commercial_asset_areas.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("rack_id", sa.Integer(), sa.ForeignKey("commercial_asset_racks.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("code", sa.String(length=16), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("code", name="uq_commercial_asset_location_code"),
    )
    op.create_index("ix_commercial_asset_locations_area_id", "commercial_asset_locations", ["area_id"])
    op.create_index("ix_commercial_asset_locations_rack_id", "commercial_asset_locations", ["rack_id"])
    op.create_index("ix_commercial_asset_locations_code", "commercial_asset_locations", ["code"])
    op.create_index("ix_commercial_asset_locations_sort_order", "commercial_asset_locations", ["sort_order"])
    op.create_index("ix_commercial_asset_locations_is_active", "commercial_asset_locations", ["is_active"])
    op.create_index("ix_commercial_asset_locations_created_by", "commercial_asset_locations", ["created_by"])

    op.add_column(
        "commercial_equipment",
        sa.Column(
            "asset_location_id",
            sa.Integer(),
            sa.ForeignKey("commercial_asset_locations.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_commercial_equipment_asset_location_id", "commercial_equipment", ["asset_location_id"])

    op.create_table(
        "commercial_asset_location_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("equipment_id", sa.Integer(), sa.ForeignKey("commercial_equipment.id", ondelete="CASCADE"), nullable=False),
        sa.Column("location_code", sa.String(length=16), nullable=False),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("changed_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
    )
    op.create_index("ix_commercial_asset_history_equipment", "commercial_asset_location_history", ["equipment_id"])
    op.create_index("ix_commercial_asset_history_location", "commercial_asset_location_history", ["location_code"])
    op.create_index("ix_commercial_asset_history_changed_by", "commercial_asset_location_history", ["changed_by"])

    conn = op.get_bind()

    # A auditoria confirmou que não existem equipamentos comerciais cadastrados
    # no banco local. Ainda assim, o backfill abaixo protege ambientes que tenham
    # registros individuais válidos.
    invalid = conn.execute(sa.text(
        "SELECT COUNT(*) FROM commercial_equipment WHERE quantity IS NULL OR quantity <> 1"
    )).scalar_one()
    if invalid:
        raise RuntimeError(
            "Existem equipamentos comerciais com quantidade diferente de 1. "
            "Individualize esses registros antes de aplicar esta migration."
        )

    conn.execute(sa.text("""
        UPDATE commercial_equipment
        SET patrimony_code = 'PAT-' || LPAD(id::text, 6, '0')
        WHERE patrimony_code IS NULL
    """))

    op.alter_column("commercial_equipment", "patrimony_code", nullable=False)
    op.create_unique_constraint(
        "uq_commercial_equipment_patrimony_code",
        "commercial_equipment",
        ["patrimony_code"],
    )
    op.create_index(
        "ix_commercial_equipment_patrimony_code",
        "commercial_equipment",
        ["patrimony_code"],
    )
    op.create_index(
        "ix_commercial_equipment_manufacturer_serial",
        "commercial_equipment",
        ["manufacturer_serial"],
    )
    op.create_check_constraint(
        "ck_commercial_equipment_quantity_one",
        "commercial_equipment",
        "quantity = 1",
    )

    user_id = conn.execute(sa.text("SELECT id FROM users ORDER BY id LIMIT 1")).scalar()
    if user_id is None:
        raise RuntimeError("Patrimônio requer ao menos um usuário existente.")

    area_id = conn.execute(sa.text("""
        INSERT INTO commercial_asset_areas
            (code, name, sort_order, is_active, created_by)
        VALUES
            ('PAT', 'Estoque Patrimonial', 10, true, :user_id)
        RETURNING id
    """), {"user_id": user_id}).scalar_one()

    rack_defs = [
        ("PE1", "Estante Patrimônio 1", "PA", 1, 1),
        ("PE2", "Estante Patrimônio 2", "PB", 1, 2),
        ("PE3", "Estante Patrimônio 3", "PC", 2, 1),
        ("PE4", "Estante Patrimônio 4", "PD", 2, 2),
        ("PE5", "Estante Patrimônio 5", "PE", 3, 1),
        ("PE6", "Estante Patrimônio 6", "PF", 3, 2),
    ]
    for order, (rack_code, rack_name, prefix, layout_row, layout_column) in enumerate(rack_defs, start=1):
        rack_id = conn.execute(sa.text("""
            INSERT INTO commercial_asset_racks
                (area_id, code, name, position_prefix, rows, columns,
                 layout_row, layout_column, layout_span, sort_order,
                 is_active, created_by)
            VALUES
                (:area_id, :code, :name, :prefix, 3, 2,
                 :layout_row, :layout_column, 1, :sort_order,
                 true, :user_id)
            RETURNING id
        """), {
            "area_id": area_id,
            "code": rack_code,
            "name": rack_name,
            "prefix": prefix,
            "layout_row": layout_row,
            "layout_column": layout_column,
            "sort_order": order,
            "user_id": user_id,
        }).scalar_one()

        for slot in range(1, 7):
            code = f"{prefix}{slot}"
            conn.execute(sa.text("""
                INSERT INTO commercial_asset_locations
                    (area_id, rack_id, code, name, sort_order, is_active, created_by)
                VALUES
                    (:area_id, :rack_id, :code, :name, :slot, true, :user_id)
            """), {
                "area_id": area_id,
                "rack_id": rack_id,
                "code": code,
                "name": f"Posição {code}",
                "slot": slot,
                "user_id": user_id,
            })


def downgrade() -> None:
    op.drop_constraint("ck_commercial_equipment_quantity_one", "commercial_equipment", type_="check")
    op.drop_index("ix_commercial_equipment_manufacturer_serial", table_name="commercial_equipment")
    op.drop_index("ix_commercial_equipment_patrimony_code", table_name="commercial_equipment")
    op.drop_constraint("uq_commercial_equipment_patrimony_code", "commercial_equipment", type_="unique")
    op.drop_table("commercial_asset_location_history")
    op.drop_index("ix_commercial_equipment_asset_location_id", table_name="commercial_equipment")
    op.drop_column("commercial_equipment", "asset_location_id")
    op.drop_table("commercial_asset_locations")
    op.drop_table("commercial_asset_racks")
    op.drop_table("commercial_asset_areas")
    op.drop_column("commercial_equipment", "manufacturer_serial")
    op.drop_column("commercial_equipment", "patrimony_code")
