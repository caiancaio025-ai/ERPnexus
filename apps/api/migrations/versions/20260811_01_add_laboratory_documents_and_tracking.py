"""add laboratory documents, tracking token and invoiced_at

Revision ID: 20260811_01
Revises: 20260731_01
Create Date: 2026-08-11

IMPORTANTE: isto substitui o arquivo 20260810_01_create_laboratory_foundation.py
que existia antes -- apague-o. Aquele arquivo tentava recriar as tabelas do
Laboratório com um desenho diferente (items[] por O.S.) que nunca bateu com o
schema real criado por 20260729_01/20260730_01/20260731_01 (1 equipamento por
O.S., via laboratory_equipment + laboratory_work_orders.equipment_id) nem com
o frontend em produção. Por isso o Alembic acusava "Multiple head revisions"
e, mesmo corrigido, teria colidido com tabelas já existentes.

Esta migration parte do head real (20260731_01) e adiciona só o que
realmente falta:
  - laboratory_documents: fotos/PDFs anexados à O.S. (a área "Fotos e PDFs de
    entrada" que hoje é só um placeholder no formulário).
  - laboratory_work_orders.tracking_token: token opaco e estável usado na URL
    pública do QR da etiqueta (/e/{token}). Nullable e preenchido sob
    demanda na primeira emissão da etiqueta -- nunca recalculado, para que
    etiquetas já impressas não fiquem órfãs.
  - laboratory_work_orders.invoiced_at: quando a O.S. foi de fato faturada
    (distinto de delivered_at, que já existe e marca a entrega física).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260811_01"
down_revision: str | None = "20260731_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "laboratory_documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "work_order_id",
            sa.Integer(),
            sa.ForeignKey("laboratory_work_orders.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("category", sa.String(length=40), nullable=False, server_default="general"),
        sa.Column("original_name", sa.String(length=255), nullable=False),
        sa.Column("storage_path", sa.String(length=1000), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=False),
        sa.Column("uploaded_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    for column in ("work_order_id", "category", "checksum_sha256", "uploaded_by"):
        op.create_index(
            f"ix_laboratory_documents_{column}",
            "laboratory_documents",
            [column],
        )

    op.add_column(
        "laboratory_work_orders",
        sa.Column("tracking_token", sa.String(length=32), nullable=True),
    )
    op.create_unique_constraint(
        "uq_laboratory_work_orders_tracking_token",
        "laboratory_work_orders",
        ["tracking_token"],
    )
    op.create_index(
        "ix_laboratory_work_orders_tracking_token",
        "laboratory_work_orders",
        ["tracking_token"],
    )

    op.add_column(
        "laboratory_work_orders",
        sa.Column("invoiced_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_laboratory_work_orders_invoiced_at", "laboratory_work_orders", ["invoiced_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_laboratory_work_orders_invoiced_at", table_name="laboratory_work_orders")
    op.drop_column("laboratory_work_orders", "invoiced_at")
    op.drop_index("ix_laboratory_work_orders_tracking_token", table_name="laboratory_work_orders")
    op.drop_constraint(
        "uq_laboratory_work_orders_tracking_token", "laboratory_work_orders", type_="unique"
    )
    op.drop_column("laboratory_work_orders", "tracking_token")
    op.drop_table("laboratory_documents")
