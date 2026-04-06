from datetime import date
from decimal import Decimal

from pydantic import BaseModel

from app.schemas.categories import CategoryResponse


class PeriodSchema(BaseModel):
    start: date
    end: date


class ComparisonSchema(BaseModel):
    income_change_percent: float | None
    expenses_change_percent: float | None
    previous_period: PeriodSchema


class SummaryResponse(BaseModel):
    period: PeriodSchema
    total_income: Decimal
    total_expenses: Decimal
    balance: Decimal
    transaction_count: int
    comparison: ComparisonSchema | None


class CategoryComparisonSchema(BaseModel):
    change_percent: float | None
    previous_total: Decimal


class CategoryBreakdownItem(BaseModel):
    category: CategoryResponse | None
    total: Decimal
    percentage: float
    transaction_count: int
    comparison: CategoryComparisonSchema | None


class ByCategoryResponse(BaseModel):
    period: PeriodSchema
    categories: list[CategoryBreakdownItem]
