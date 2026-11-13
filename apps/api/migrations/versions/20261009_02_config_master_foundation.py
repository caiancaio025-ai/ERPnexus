"""config master foundation: companies and physical locations

Revision ID: 20261009_02
Revises: 20261009_01
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261009_02"
down_revision: str | None = "20261009_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "laboratory_areas",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=8), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("code", name="uq_laboratory_area_code"),
    )
    op.create_index("ix_laboratory_areas_code", "laboratory_areas", ["code"])
    op.create_index("ix_laboratory_areas_sort_order", "laboratory_areas", ["sort_order"])
    op.create_index("ix_laboratory_areas_is_active", "laboratory_areas", ["is_active"])
    op.create_index("ix_laboratory_areas_created_by", "laboratory_areas", ["created_by"])

    op.create_table(
        "laboratory_racks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("area_id", sa.Integer(), sa.ForeignKey("laboratory_areas.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("code", sa.String(length=12), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("position_prefix", sa.String(length=4), nullable=False),
        sa.Column("rows", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("columns", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("code", name="uq_laboratory_rack_code"),
    )
    op.create_index("ix_laboratory_racks_area_id", "laboratory_racks", ["area_id"])
    op.create_index("ix_laboratory_racks_code", "laboratory_racks", ["code"])
    op.create_index("ix_laboratory_racks_sort_order", "laboratory_racks", ["sort_order"])
    op.create_index("ix_laboratory_racks_is_active", "laboratory_racks", ["is_active"])
    op.create_index("ix_laboratory_racks_created_by", "laboratory_racks", ["created_by"])

    op.create_table(
        "laboratory_locations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("area_id", sa.Integer(), sa.ForeignKey("laboratory_areas.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("rack_id", sa.Integer(), sa.ForeignKey("laboratory_racks.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("code", sa.String(length=8), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("code", name="uq_laboratory_location_code"),
    )
    op.create_index("ix_laboratory_locations_area_id", "laboratory_locations", ["area_id"])
    op.create_index("ix_laboratory_locations_rack_id", "laboratory_locations", ["rack_id"])
    op.create_index("ix_laboratory_locations_code", "laboratory_locations", ["code"])
    op.create_index("ix_laboratory_locations_sort_order", "laboratory_locations", ["sort_order"])
    op.create_index("ix_laboratory_locations_is_active", "laboratory_locations", ["is_active"])
    op.create_index("ix_laboratory_locations_created_by", "laboratory_locations", ["created_by"])

    op.add_column("laboratory_quotes", sa.Column("company_snapshot", sa.Text(), nullable=True))

    conn = op.get_bind()
    user_id = conn.execute(sa.text("SELECT id FROM users ORDER BY id LIMIT 1")).scalar()
    if user_id is None:
        raise RuntimeError("Config Master requer ao menos um usuário existente.")

    companies = [
        ("universo_eletronica", "Empresa Demonstração Industrial", "Empresa Demonstração", "00.000.000/0000-00", "contato@empresa.example"),
        ("universo_automacao", "Empresa Teste Automação", "Empresa Teste", "00.000.000/0000-00", "automacao@empresa.example"),
        ("solucoes_eletronica", "Empresa Laboratório Exemplo", "Empresa Laboratório", "00.000.000/0000-00", "comercial@empresa.example"),
    ]
    for code, legal, trade, document, email in companies:
        conn.execute(sa.text("""
            INSERT INTO commercial_company_profiles
                (company_code, legal_name, trade_name, document, email, phone, address, city, state, is_active, created_by)
            VALUES
                (:code, :legal, :trade, :document, :email, '00 00000-0000',
                 'Rua Exemplo, 100', 'Recife', 'PE', true, :user_id)
            ON CONFLICT (company_code) DO NOTHING
        """), dict(code=code, legal=legal, trade=trade, document=document, email=email, user_id=user_id))

    area_ids = {}
    for code, name, order in [("EXP", "Expedição", 10), ("LAB", "Laboratório", 20), ("MEC", "Mecânica", 30)]:
        area_ids[code] = conn.execute(sa.text("""
            INSERT INTO laboratory_areas (code, name, sort_order, is_active, created_by)
            VALUES (:code, :name, :order, true, :user_id)
            RETURNING id
        """), dict(code=code, name=name, order=order, user_id=user_id)).scalar_one()

    rack_defs = [("E1","Estante 1","A"),("E2","Estante 2","B"),("E3","Estante 3","C"),
                 ("E4","Estante 4","D"),("E5","Estante 5","E"),("E6","Estante 6","F")]
    for order, (rack_code, rack_name, prefix) in enumerate(rack_defs, start=1):
        rack_id = conn.execute(sa.text("""
            INSERT INTO laboratory_racks
                (area_id, code, name, position_prefix, rows, columns, sort_order, is_active, created_by)
            VALUES (:area_id, :code, :name, :prefix, 3, 2, :order, true, :user_id)
            RETURNING id
        """), dict(area_id=area_ids["EXP"], code=rack_code, name=rack_name, prefix=prefix, order=order, user_id=user_id)).scalar_one()
        for slot in range(1, 7):
            code = f"{prefix}{slot}"
            conn.execute(sa.text("""
                INSERT INTO laboratory_locations
                    (area_id, rack_id, code, name, sort_order, is_active, created_by)
                VALUES (:area_id, :rack_id, :code, :name, :slot, true, :user_id)
            """), dict(area_id=area_ids["EXP"], rack_id=rack_id, code=code, name=f"Posição {code}", slot=slot, user_id=user_id))

    for code, name in [("LAB", "Laboratório - Área geral"), ("MEC", "Mecânica - Área geral")]:
        conn.execute(sa.text("""
            INSERT INTO laboratory_locations
                (area_id, rack_id, code, name, sort_order, is_active, created_by)
            VALUES (:area_id, NULL, :code, :name, 1, true, :user_id)
        """), dict(area_id=area_ids[code], code=code, name=name, user_id=user_id))

    # Melhor fotografia histórica possível para orçamentos já emitidos antes desta migration.
    conn.execute(sa.text("""
        UPDATE laboratory_quotes AS q
        SET company_snapshot = json_build_object(
            'company_code', cp.company_code,
            'legal_name', cp.legal_name,
            'trade_name', cp.trade_name,
            'document', cp.document,
            'state_registration', cp.state_registration,
            'email', cp.email,
            'phone', cp.phone,
            'address', cp.address,
            'city', cp.city,
            'state', cp.state
        )::text
        FROM laboratory_work_orders AS wo
        JOIN commercial_company_profiles AS cp ON cp.company_code = wo.company_code
        WHERE q.work_order_id = wo.id
          AND q.emitted_at IS NOT NULL
          AND q.company_snapshot IS NULL
    """))


def downgrade() -> None:
    op.drop_column("laboratory_quotes", "company_snapshot")
    op.drop_table("laboratory_locations")
    op.drop_table("laboratory_racks")
    op.drop_table("laboratory_areas")
