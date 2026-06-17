"""Add richer spending feedback fields

Revision ID: 007
Revises: 006
Create Date: 2026-06-17

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("spending_feedbacks", sa.Column("highlights", sa.JSON(), nullable=True))
    op.add_column("spending_feedbacks", sa.Column("saving_opportunities", sa.JSON(), nullable=True))
    op.add_column("spending_feedbacks", sa.Column("watchlist", sa.JSON(), nullable=True))
    op.add_column("spending_feedbacks", sa.Column("total_potential_saving", sa.Numeric(12, 2), nullable=True))


def downgrade() -> None:
    op.drop_column("spending_feedbacks", "total_potential_saving")
    op.drop_column("spending_feedbacks", "watchlist")
    op.drop_column("spending_feedbacks", "saving_opportunities")
    op.drop_column("spending_feedbacks", "highlights")
