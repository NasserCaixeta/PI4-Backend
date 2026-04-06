import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SubscriptionResponse(BaseModel):
    id: uuid.UUID
    status: str
    current_period_end: datetime | None

    model_config = ConfigDict(from_attributes=True)
