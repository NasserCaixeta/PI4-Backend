"""Add statement type and file hash

Revision ID: 002
Revises: 001
Create Date: 2026-05-13

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("bank_statements", sa.Column("file_hash", sa.String(64), nullable=True))
    op.add_column("bank_statements", sa.Column("statement_type", sa.String(20), nullable=True))
    op.create_unique_constraint(
        "uq_bank_statements_user_file_hash",
        "bank_statements",
        ["user_id", "file_hash"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_bank_statements_user_file_hash", "bank_statements", type_="unique")
    op.drop_column("bank_statements", "statement_type")
    op.drop_column("bank_statements", "file_hash")
