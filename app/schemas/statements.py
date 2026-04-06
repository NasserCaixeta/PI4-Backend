import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class CategoryResponse(BaseModel):
    id: uuid.UUID
    name: str
    color: str | None
    icon: str | None
    is_default: bool

    model_config = ConfigDict(from_attributes=True)


class TransactionResponse(BaseModel):
    id: uuid.UUID
    date: date
    description: str | None
    amount: Decimal
    type: str
    category: CategoryResponse | None

    model_config = ConfigDict(from_attributes=True)


class StatementResponse(BaseModel):
    id: uuid.UUID
    filename: str | None
    file_size_kb: int | None
    status: str
    uploaded_at: datetime
    processed_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class StatementDetailResponse(StatementResponse):
    transactions: list[TransactionResponse] = []
