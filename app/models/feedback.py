from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON as GenericJSON

from app.database import Base

if TYPE_CHECKING:
    from app.models.auth import User


class SpendingFeedback(Base):
    __tablename__ = "spending_feedbacks"
    __table_args__ = (UniqueConstraint("user_id", "month", "year", name="uq_feedback_user_month_year"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(default="pending")
    subscriptions: Mapped[dict | None] = mapped_column(GenericJSON, nullable=True)
    reducible_expenses: Mapped[dict | None] = mapped_column(GenericJSON, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)

    user: Mapped[User] = relationship(back_populates="feedbacks")
