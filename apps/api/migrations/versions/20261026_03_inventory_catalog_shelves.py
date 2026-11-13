"""Categorias e subtipos técnicos editáveis, preservando Estoque V5.

Revision ID: 20261026_03
Revises: 20261026_02
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261026_03"
down_revision: str | None = "20261026_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


DEFAULT_CATEGORIES = [
    ("componentes", "Componentes diversos"), ("capacitor", "Capacitor"),
    ("resistor", "Resistor"), ("transistor", "Transistor"),
    ("igbt", "IGBT"), ("diodo", "Diodo"), ("tiristor", "Tiristor"),
    ("placa_disparo", "Placa de disparo"), ("placa_potencia", "Placa de potência"),
    ("placa_controle", "Placa de controle"), ("placa", "Placa eletrônica"),
    ("ventilador", "Fan / Cooler"),
    ("fonte", "Fonte"), ("fusivel", "Fusível"),
    ("equipamento", "Equipamento"), ("outros", "Outros"),
]


def upgrade() -> None:
    op.create_table(
        "inventory_component_categories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(80), nullable=False, unique=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index("ix_inventory_component_categories_code", "inventory_component_categories", ["code"])
    op.create_table(
        "inventory_component_subtypes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("category", sa.String(80), nullable=False),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("category", "code", name="uq_inv_subtype_category_code"),
    )
    op.create_index("ix_inventory_component_subtypes_category", "inventory_component_subtypes", ["category"])
    op.add_column("inventory_items", sa.Column("subtype_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_inventory_items_subtype_id", "inventory_items", "inventory_component_subtypes", ["subtype_id"], ["id"], ondelete="RESTRICT")
    op.create_index("ix_inventory_items_subtype_id", "inventory_items", ["subtype_id"])
    categories = sa.table("inventory_component_categories", sa.column("code", sa.String), sa.column("name", sa.String))
    op.bulk_insert(categories, [{"code": code, "name": name} for code, name in DEFAULT_CATEGORIES])
    # Preservar categorias personalizadas existentes em itens e formatos da V5.
    op.execute(sa.text("""
        INSERT INTO inventory_component_categories (code, name, is_active)
        SELECT DISTINCT src.code, initcap(replace(src.code, '_', ' ')), TRUE
        FROM (
            SELECT lower(trim(category)) AS code FROM inventory_items
            UNION
            SELECT lower(trim(category)) AS code FROM inventory_component_formats
        ) src
        WHERE src.code <> '' AND NOT EXISTS (
            SELECT 1 FROM inventory_component_categories c WHERE c.code = src.code
        )
    """))
    subtypes = sa.table("inventory_component_subtypes", sa.column("category", sa.String), sa.column("code", sa.String), sa.column("name", sa.String))
    op.bulk_insert(subtypes, [
        {"category": "capacitor", "code": "eletrolitico", "name": "Eletrolítico"},
        {"category": "capacitor", "code": "poliester", "name": "Poliéster"},
        {"category": "capacitor", "code": "ceramico", "name": "Cerâmico"},
        {"category": "capacitor", "code": "filme", "name": "Filme"},
        {"category": "resistor", "code": "fixo", "name": "Fixo"},
        {"category": "resistor", "code": "potencia", "name": "Potência"},
        {"category": "transistor", "code": "bjt", "name": "BJT"},
        {"category": "transistor", "code": "mosfet", "name": "MOSFET"},
    ])
    # Formatos técnicos adicionais para categorias que ainda não os possuíam.
    op.execute(sa.text("""
        INSERT INTO inventory_component_formats (category, code, name, is_active)
        SELECT f.category, f.code, f.name, TRUE
        FROM (VALUES
            ('igbt','to263','TO-263 / D2PAK'),('igbt','smd','SMD'),
            ('transistor','to263','TO-263 / D2PAK'),('transistor','pth','PTH'),
            ('capacitor','pth','PTH'),('capacitor','to263','TO-263'),
            ('placa_disparo','modulo','Módulo / placa'),('placa_potencia','modulo','Módulo / placa'),
            ('placa_controle','modulo','Módulo / placa'),('ventilador','axial','Axial'),
            ('ventilador','radial','Radial'),
            ('resistor','to263','TO-263 / D2PAK')
        ) AS f(category,code,name)
        WHERE NOT EXISTS (
            SELECT 1 FROM inventory_component_formats x WHERE x.category = f.category AND x.code = f.code
        )
    """))


def downgrade() -> None:
    raise RuntimeError("Downgrade do catálogo exige preservar subtipos e itens associados.")
