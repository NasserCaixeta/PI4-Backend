from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.feedback import SpendingFeedback
    from app.models.payments import Subscription
    from app.models.statements import BankStatement, Category


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String(255))
    avatar_url: Mapped[str | None] = mapped_column(Text)
    auth_provider: Mapped[str | None] = mapped_column(String(50))
    password_hash: Mapped[str | None] = mapped_column(Text)
    email_verified_at: Mapped[datetime | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(default=func.now())

    statements: Mapped[list[BankStatement]] = relationship(back_populates="user")
    categories: Mapped[list[Category]] = relationship(back_populates="user")
    subscription: Mapped[Subscription | None] = relationship(back_populates="user")
    free_usage: Mapped[FreeUsage | None] = relationship(back_populates="user")
    feedbacks: Mapped[list[SpendingFeedback]] = relationship(back_populates="user")
    email_verification_codes: Mapped[list[EmailVerificationCode]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )

    @property
    def is_email_verified(self) -> bool:
        return self.email_verified_at is not None


class EmailVerificationCode(Base):
    __tablename__ = "email_verification_codes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    sent_to_email: Mapped[str] = mapped_column(String(255), nullable=False)
    code_hash: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column()
    attempt_count: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(default=func.now())

    user: Mapped[User] = relationship(back_populates="email_verification_codes")


class FreeUsage(Base):
    __tablename__ = "free_usage"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), unique=True)
    analyses_used: Mapped[int] = mapped_column(default=0)
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())

    user: Mapped[User] = relationship(back_populates="free_usage")
