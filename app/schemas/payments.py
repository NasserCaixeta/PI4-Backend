import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CheckoutRequest(BaseModel):
    plan: str


class CheckoutResponse(BaseModel):
    checkout_url: str


class PortalResponse(BaseModel):
    portal_url: str


class BillingStatusResponse(BaseModel):
    plan: str
    status: str
    analyses_used: int
    analyses_limit: int | None
    analyses_remaining: int | None
    current_period_end: datetime | None


class SubscriptionResponse(BaseModel):
    id: uuid.UUID
    status: str
    plan: str
    analyses_used: int
    current_period_start: datetime | None
    current_period_end: datetime | None

    model_config = ConfigDict(from_attributes=True)
