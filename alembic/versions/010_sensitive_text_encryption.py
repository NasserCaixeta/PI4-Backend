"""Add encrypted sensitive text columns

Revision ID: 010
Revises: 009
Create Date: 2026-07-10

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("bank_statements", sa.Column("filename_encrypted", sa.Text(), nullable=True))
    op.add_column("transactions", sa.Column("description_encrypted", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("transactions", "description_encrypted")
    op.drop_column("bank_statements", "filename_encrypted")
