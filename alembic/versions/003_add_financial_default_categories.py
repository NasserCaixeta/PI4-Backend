"""Add financial default categories

Revision ID: 003
Revises: 002
Create Date: 2026-05-13

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

categories_table = sa.table(
    "categories",
    sa.column("name", sa.String),
    sa.column("color", sa.String),
    sa.column("icon", sa.String),
    sa.column("is_default", sa.Boolean),
    sa.column("user_id", sa.String),
)

NEW_DEFAULT_CATEGORIES = [
    {"name": "Compras", "color": "#F59E0B", "icon": "shopping-bag", "is_default": True, "user_id": None},
    {"name": "Assinaturas", "color": "#8B5CF6", "icon": "repeat", "is_default": True, "user_id": None},
    {"name": "Educação", "color": "#3B82F6", "icon": "graduation-cap", "is_default": True, "user_id": None},
    {"name": "Serviços", "color": "#10B981", "icon": "wrench", "is_default": True, "user_id": None},
    {"name": "Transferências", "color": "#64748B", "icon": "arrow-left-right", "is_default": True, "user_id": None},
]


def upgrade() -> None:
    connection = op.get_bind()
    for category in NEW_DEFAULT_CATEGORIES:
        exists = connection.execute(
            sa.text("SELECT 1 FROM categories WHERE name = :name AND user_id IS NULL"),
            {"name": category["name"]},
        ).scalar()
        if not exists:
            op.bulk_insert(categories_table, [category])


def downgrade() -> None:
    names = [category["name"] for category in NEW_DEFAULT_CATEGORIES]
    op.execute(
        sa.text("DELETE FROM categories WHERE user_id IS NULL AND name = ANY(:names)").bindparams(
            sa.bindparam("names", value=names, expanding=False)
        )
    )
