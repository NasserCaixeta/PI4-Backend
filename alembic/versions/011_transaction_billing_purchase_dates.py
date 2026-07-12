"""Add transaction billing and purchase dates

Revision ID: 011
Revises: 010
Create Date: 2026-07-10

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("transactions", sa.Column("billing_date", sa.Date(), nullable=True))
    op.add_column("transactions", sa.Column("purchase_date", sa.Date(), nullable=True))
    op.execute("UPDATE transactions SET billing_date = date WHERE billing_date IS NULL")
    op.alter_column("transactions", "billing_date", nullable=False)


def downgrade() -> None:
    op.drop_column("transactions", "purchase_date")
    op.drop_column("transactions", "billing_date")
