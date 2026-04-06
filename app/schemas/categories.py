import uuid

from pydantic import BaseModel, ConfigDict


class CategoryCreate(BaseModel):
    name: str
    color: str | None = None
    icon: str | None = None


class CategoryUpdate(BaseModel):
    name: str | None = None
    color: str | None = None
    icon: str | None = None


class CategoryResponse(BaseModel):
    id: uuid.UUID
    name: str
    color: str | None
    icon: str | None
    is_default: bool

    model_config = ConfigDict(from_attributes=True)
