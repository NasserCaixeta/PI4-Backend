import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SubscriptionItem(BaseModel):
    name: str
    description: str | None = None
    amount: float
    confidence: str | None = None
    reason: str | None = None
    evidence: list[str] | None = None


class ReducibleExpenseItem(BaseModel):
    category: str
    description: str | None = None
    amount: float
    suggestion: str
    potential_saving: float
    title: str | None = None
    type: str | None = None
    confidence: str | None = None
    priority: int | None = None
    reason: str | None = None
    evidence: list[str] | None = None


class SpendingInsightItem(BaseModel):
    title: str
    category: str | None = None
    type: str
    amount: float
    description: str | None = None
    potential_saving: float | None = None
    confidence: str
    priority: int
    reason: str
    suggestion: str
    evidence: list[str] | None = None


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
    highlights: list[str] | None = None
    saving_opportunities: list[SpendingInsightItem] | None = None
    watchlist: list[SpendingInsightItem] | None = None
    total_potential_saving: float | None = None
    summary: str | None = None
    created_at: datetime
    completed_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class FeedbackGenerateResponse(BaseModel):
    feedback_id: uuid.UUID
    status: str
