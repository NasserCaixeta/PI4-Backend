import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.schemas.categories import CategoryResponse


class TransactionUpdate(BaseModel):
    category_id: uuid.UUID | None = None
    description: str | None = None


class TransactionResponse(BaseModel):
    id: uuid.UUID
    date: date
    description: str | None
    amount: Decimal
    type: str
    category: CategoryResponse | None

    model_config = ConfigDict(from_attributes=True)


class TransactionListResponse(BaseModel):
    items: list[TransactionResponse]
    total: int
    limit: int
    offset: int
