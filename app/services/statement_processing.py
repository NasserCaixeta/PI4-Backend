from __future__ import annotations

import calendar
import re
from collections import Counter
from collections.abc import Callable
from datetime import date as date_type, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.statements import BankStatement, Category, Transaction
from app.services.categories import normalize_transaction_category
from app.services.gemini import normalize_statement_type


class StatementProcessingError(Exception):
    """Raised when a PDF cannot be converted into valid transactions."""


class ExtractedTransaction(BaseModel):
    date: date_type | None = None
    billing_date: date_type | None = None
    purchase_date: date_type | None = None
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

    @model_validator(mode="after")
    def resolve_dates(self) -> ExtractedTransaction:
        if self.billing_date is None:
            self.billing_date = self.date
        if self.date is None:
            self.date = self.billing_date
        if self.billing_date is None or self.date is None:
            raise ValueError("billing_date or date is required")
        return self


class ExtractedStatement(BaseModel):
    statement_type: Literal["bank_account", "credit_card"] = "credit_card"
    statement_reference_date: date_type | None = None
    statement_month: str | None = None
    transactions: list[ExtractedTransaction] = Field(default_factory=list)

    @field_validator("statement_type", mode="before")
    @classmethod
    def normalize_type(cls, value: str | None) -> str:
        return normalize_statement_type(value)


_INSTALLMENT_RE = re.compile(
    r"(?i)(?:parcela\s*)?\b([1-9]\d{0,2})\s*(?:/|de)\s*([1-9]\d{0,2})\b"
)


def _is_installment(description: str) -> bool:
    match = _INSTALLMENT_RE.search(description)
    if not match:
        return False
    current = int(match.group(1))
    total = int(match.group(2))
    return 1 <= current <= total and total > 1


def _month_key(value: date_type) -> tuple[int, int]:
    return value.year, value.month


def _parse_statement_month(value: str | None) -> tuple[int, int] | None:
    if not value:
        return None
    match = re.fullmatch(r"(\d{4})-(\d{2})", value.strip())
    if not match:
        return None
    year = int(match.group(1))
    month = int(match.group(2))
    if not 1 <= month <= 12:
        return None
    return year, month


def _date_in_month(value: date_type, month: tuple[int, int]) -> date_type:
    year, month_number = month
    last_day = calendar.monthrange(year, month_number)[1]
    return date_type(year, month_number, min(value.day, last_day))


def _infer_statement_month(extraction: ExtractedStatement) -> tuple[int, int] | None:
    if extraction.statement_reference_date is not None:
        return _month_key(extraction.statement_reference_date)

    parsed_month = _parse_statement_month(extraction.statement_month)
    if parsed_month is not None:
        return parsed_month

    non_installment_dates = [
        tx.billing_date for tx in extraction.transactions if not _is_installment(tx.description)
    ]
    if non_installment_dates:
        months = Counter(_month_key(value) for value in non_installment_dates if value is not None)
        if months:
            return months.most_common(1)[0][0]

    if extraction.transactions:
        months = Counter(_month_key(tx.billing_date) for tx in extraction.transactions if tx.billing_date is not None)
        if months:
            return months.most_common(1)[0][0]

    return None


def normalize_credit_card_installment_dates(extraction: ExtractedStatement) -> None:
    if extraction.statement_type != "credit_card":
        return

    statement_month = _infer_statement_month(extraction)
    if statement_month is None:
        return

    for tx in extraction.transactions:
        if tx.billing_date is None:
            continue
        if _is_installment(tx.description) and _month_key(tx.billing_date) != statement_month:
            tx.purchase_date = tx.purchase_date or tx.billing_date
            tx.billing_date = _date_in_month(tx.billing_date, statement_month)
            tx.date = tx.billing_date


def validate_extraction(raw_extraction: dict | list) -> ExtractedStatement:
    if isinstance(raw_extraction, list):
        raw_extraction = {"statement_type": "credit_card", "transactions": raw_extraction}
    try:
        extraction = ExtractedStatement.model_validate(raw_extraction)
    except ValidationError as exc:
        raise StatementProcessingError("Gemini returned invalid transaction data") from exc
    normalize_credit_card_installment_dates(extraction)
    return extraction


async def process_statement_pdf(
    db: AsyncSession,
    statement: BankStatement,
    pdf_bytes: bytes,
    extractor: Callable[[bytes], dict],
    *,
    replace_existing: bool = False,
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

    if replace_existing:
        await db.execute(delete(Transaction).where(Transaction.statement_id == statement.id))

    for tx in extraction.transactions:
        category_name = normalize_transaction_category(tx.description, tx.category)
        category_id = categories.get(category_name) or categories.get("Outros")
        db.add(
            Transaction(
                statement_id=statement.id,
                date=tx.billing_date,
                billing_date=tx.billing_date,
                purchase_date=tx.purchase_date,
                description=tx.description,
                amount=tx.amount,
                type=tx.type,
                category_id=category_id,
            )
        )

    statement.status = "completed"
    statement.error_message = None
    statement.processed_at = datetime.utcnow()
