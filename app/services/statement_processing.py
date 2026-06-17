from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.statements import BankStatement, Category, Transaction
from app.services.categories import normalize_transaction_category
from app.services.gemini import normalize_statement_type


class StatementProcessingError(Exception):
    """Raised when a PDF cannot be converted into valid transactions."""


class ExtractedTransaction(BaseModel):
    date: date
    description: str = Field(min_length=1)
    amount: Decimal = Field(gt=0)
    type: Literal["credit", "debit"]
    category: str | None = None

    model_config = ConfigDict(str_strip_whitespace=True)

    @field_validator("description")
    @classmethod
    def description_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("description cannot be blank")
        return value


class ExtractedStatement(BaseModel):
    statement_type: Literal["bank_account", "credit_card"] = "credit_card"
    transactions: list[ExtractedTransaction] = Field(default_factory=list)

    @field_validator("statement_type", mode="before")
    @classmethod
    def normalize_type(cls, value: str | None) -> str:
        return normalize_statement_type(value)


def validate_extraction(raw_extraction: dict | list) -> ExtractedStatement:
    if isinstance(raw_extraction, list):
        raw_extraction = {"statement_type": "credit_card", "transactions": raw_extraction}
    try:
        return ExtractedStatement.model_validate(raw_extraction)
    except ValidationError as exc:
        raise StatementProcessingError("Gemini returned invalid transaction data") from exc


async def process_statement_pdf(
    db: AsyncSession,
    statement: BankStatement,
    pdf_bytes: bytes,
    extractor: Callable[[bytes], dict],
) -> None:
    try:
        extraction = validate_extraction(extractor(pdf_bytes))
    except Exception as exc:
        if isinstance(exc, StatementProcessingError):
            raise
        raise StatementProcessingError("Could not extract transactions from PDF") from exc

    statement.statement_type = extraction.statement_type

    cat_result = await db.execute(select(Category).where(Category.is_default == True))
    categories = {category.name: category.id for category in cat_result.scalars()}

    for tx in extraction.transactions:
        category_name = normalize_transaction_category(tx.description, tx.category)
        category_id = categories.get(category_name) or categories.get("Outros")
        db.add(
            Transaction(
                statement_id=statement.id,
                date=tx.date,
                description=tx.description,
                amount=tx.amount,
                type=tx.type,
                category_id=category_id,
            )
        )

    statement.status = "completed"
    statement.error_message = None
    statement.processed_at = datetime.utcnow()
