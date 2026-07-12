from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.encryption import decrypt_text, encrypt_text
from app.database import Base

if TYPE_CHECKING:
    from app.models.auth import User


class BankStatement(Base):
    __tablename__ = "bank_statements"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    _filename: Mapped[str | None] = mapped_column("filename", String(255))
    filename_encrypted: Mapped[str | None] = mapped_column(Text)
    file_size_kb: Mapped[int | None]
    file_hash: Mapped[str | None] = mapped_column(String(64))
    statement_type: Mapped[str | None] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="reading")
    error_message: Mapped[str | None] = mapped_column(Text)
    uploaded_at: Mapped[datetime] = mapped_column(default=func.now())
    processed_at: Mapped[datetime | None]

    user: Mapped[User] = relationship(back_populates="statements")
    transactions: Mapped[list[Transaction]] = relationship(back_populates="statement", cascade="all, delete-orphan")

    @property
    def filename(self) -> str | None:
        if self.filename_encrypted:
            return decrypt_text(self.filename_encrypted)
        return self._filename

    @filename.setter
    def filename(self, value: str | None) -> None:
        self._filename = None
        self.filename_encrypted = encrypt_text(value)


class Category(Base):
    __tablename__ = "categories"
    __table_args__ = (UniqueConstraint("name", "user_id", name="uq_category_name_user"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    color: Mapped[str | None] = mapped_column(String(7))
    icon: Mapped[str | None] = mapped_column(String(50))
    is_default: Mapped[bool] = mapped_column(default=False)

    user: Mapped[User | None] = relationship(back_populates="categories")
    transactions: Mapped[list[Transaction]] = relationship(back_populates="category")


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    statement_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bank_statements.id", ondelete="CASCADE"))
    category_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("categories.id"))
    date: Mapped[date] = mapped_column(nullable=False)
    billing_date: Mapped[date] = mapped_column(nullable=False)
    purchase_date: Mapped[date | None]
    _description: Mapped[str | None] = mapped_column("description", Text)
    description_encrypted: Mapped[str | None] = mapped_column(Text)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    type: Mapped[str] = mapped_column(String(10))

    statement: Mapped[BankStatement] = relationship(back_populates="transactions")
    category: Mapped[Category | None] = relationship(back_populates="transactions")

    def __init__(self, **kwargs):
        if kwargs.get("billing_date") is None and kwargs.get("date") is not None:
            kwargs["billing_date"] = kwargs["date"]
        super().__init__(**kwargs)

    @property
    def description(self) -> str | None:
        if self.description_encrypted:
            return decrypt_text(self.description_encrypted)
        return self._description

    @description.setter
    def description(self, value: str | None) -> None:
        self._description = None
        self.description_encrypted = encrypt_text(value)
