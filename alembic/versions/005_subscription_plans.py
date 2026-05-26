"""Add subscription plan fields

Revision ID: 005
Revises: 004
Create Date: 2026-05-25

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("subscriptions", sa.Column("plan", sa.String(20), nullable=False, server_default="free"))
    op.add_column("subscriptions", sa.Column("analyses_used", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("subscriptions", sa.Column("current_period_start", sa.TIMESTAMP(timezone=True), nullable=True))
    op.alter_column("subscriptions", "plan", server_default=None)
    op.alter_column("subscriptions", "analyses_used", server_default=None)


def downgrade() -> None:
    op.drop_column("subscriptions", "current_period_start")
    op.drop_column("subscriptions", "analyses_used")
    op.drop_column("subscriptions", "plan")
