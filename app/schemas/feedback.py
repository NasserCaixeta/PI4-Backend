import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SubscriptionItem(BaseModel):
    name: str
    description: str | None = None
    amount: float


class ReducibleExpenseItem(BaseModel):
    category: str
    description: str | None = None
    amount: float
    suggestion: str
    potential_saving: float


class FeedbackGenerateRequest(BaseModel):
    month: int
    year: int


class FeedbackListItem(BaseModel):
    id: uuid.UUID
    month: int
    year: int
    status: str
    created_at: datetime
    completed_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class FeedbackDetailResponse(BaseModel):
    id: uuid.UUID
    month: int
    year: int
    status: str
    subscriptions: list[SubscriptionItem] | None = None
    reducible_expenses: list[ReducibleExpenseItem] | None = None
    summary: str | None = None
    created_at: datetime
    completed_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class FeedbackGenerateResponse(BaseModel):
    feedback_id: uuid.UUID
    status: str
