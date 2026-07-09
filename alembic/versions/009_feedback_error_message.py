"""Add feedback error message

Revision ID: 009
Revises: 008
Create Date: 2026-07-08

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("spending_feedbacks", sa.Column("error_message", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("spending_feedbacks", "error_message")
