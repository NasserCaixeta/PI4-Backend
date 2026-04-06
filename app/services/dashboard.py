import calendar
import uuid
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.statements import BankStatement, Category, Transaction
from app.schemas.categories import CategoryResponse
from app.schemas.dashboard import (
    ByCategoryResponse,
    CategoryBreakdownItem,
    CategoryComparisonSchema,
    ComparisonSchema,
    PeriodSchema,
    SummaryResponse,
)


def get_period_dates(
    month: int | None, year: int | None, start_date: date | None, end_date: date | None
) -> tuple[date, date]:
    """Returns start and end dates for the period."""
    if month and year:
        last_day = calendar.monthrange(year, month)[1]
        return date(year, month, 1), date(year, month, last_day)
    if start_date and end_date:
        return start_date, end_date
    # Default: current month
    today = date.today()
    last_day = calendar.monthrange(today.year, today.month)[1]
    return date(today.year, today.month, 1), date(today.year, today.month, last_day)


def get_previous_period(start: date, end: date) -> tuple[date, date]:
    """Returns the previous period of same duration."""
    duration = (end - start).days + 1
    prev_end = start - timedelta(days=1)
    prev_start = prev_end - timedelta(days=duration - 1)
    return prev_start, prev_end


async def get_period_totals(
    db: AsyncSession, user_id: uuid.UUID, start: date, end: date
) -> tuple[Decimal, Decimal, int]:
    """Returns (total_income, total_expenses, count) for period."""
    result = await db.execute(
        select(
            func.coalesce(func.sum(Transaction.amount).filter(Transaction.type == "credit"), 0),
            func.coalesce(func.sum(Transaction.amount).filter(Transaction.type == "debit"), 0),
            func.count(Transaction.id),
        )
        .join(BankStatement)
        .where(
            BankStatement.user_id == user_id,
            Transaction.date >= start,
            Transaction.date <= end,
        )
    )
    row = result.one()
    return Decimal(str(row[0])), Decimal(str(row[1])), row[2]


def calc_change_percent(current: Decimal, previous: Decimal) -> float | None:
    """Calculate percentage change."""
    if previous == 0:
        return None
    return round(float((current - previous) / previous * 100), 1)


async def get_summary(
    db: AsyncSession,
    user_id: uuid.UUID,
    month: int | None,
    year: int | None,
    start_date: date | None,
    end_date: date | None,
) -> SummaryResponse:
    start, end = get_period_dates(month, year, start_date, end_date)
    income, expenses, count = await get_period_totals(db, user_id, start, end)

    # Previous period comparison
    prev_start, prev_end = get_previous_period(start, end)
    prev_income, prev_expenses, _ = await get_period_totals(db, user_id, prev_start, prev_end)

    comparison = ComparisonSchema(
        income_change_percent=calc_change_percent(income, prev_income),
        expenses_change_percent=calc_change_percent(expenses, prev_expenses),
        previous_period=PeriodSchema(start=prev_start, end=prev_end),
    )

    return SummaryResponse(
        period=PeriodSchema(start=start, end=end),
        total_income=income,
        total_expenses=expenses,
        balance=income - expenses,
        transaction_count=count,
        comparison=comparison,
    )


async def get_by_category(
    db: AsyncSession,
    user_id: uuid.UUID,
    month: int | None,
    year: int | None,
    start_date: date | None,
    end_date: date | None,
) -> ByCategoryResponse:
    start, end = get_period_dates(month, year, start_date, end_date)
    prev_start, prev_end = get_previous_period(start, end)

    # Current period by category (only expenses/debits)
    result = await db.execute(
        select(
            Transaction.category_id,
            func.sum(Transaction.amount).label("total"),
            func.count(Transaction.id).label("count"),
        )
        .join(BankStatement)
        .where(
            BankStatement.user_id == user_id,
            Transaction.date >= start,
            Transaction.date <= end,
            Transaction.type == "debit",
        )
        .group_by(Transaction.category_id)
    )
    current_data = {row.category_id: (Decimal(str(row.total)), row.count) for row in result}

    # Previous period by category
    prev_result = await db.execute(
        select(
            Transaction.category_id,
            func.sum(Transaction.amount).label("total"),
        )
        .join(BankStatement)
        .where(
            BankStatement.user_id == user_id,
            Transaction.date >= prev_start,
            Transaction.date <= prev_end,
            Transaction.type == "debit",
        )
        .group_by(Transaction.category_id)
    )
    prev_data = {row.category_id: Decimal(str(row.total)) for row in prev_result}

    # Fetch categories
    cat_ids = list(current_data.keys())
    if cat_ids:
        cat_result = await db.execute(select(Category).where(Category.id.in_(cat_ids)))
        categories = {c.id: c for c in cat_result.scalars()}
    else:
        categories = {}

    # Calculate total for percentage
    total_expenses = sum(t[0] for t in current_data.values())

    # Build breakdown
    items = []
    for cat_id, (total, count) in sorted(current_data.items(), key=lambda x: x[1][0], reverse=True):
        cat = categories.get(cat_id)
        prev_total = prev_data.get(cat_id, Decimal("0"))

        items.append(
            CategoryBreakdownItem(
                category=CategoryResponse.model_validate(cat) if cat else None,
                total=total,
                percentage=round(float(total / total_expenses * 100), 1) if total_expenses else 0,
                transaction_count=count,
                comparison=CategoryComparisonSchema(
                    change_percent=calc_change_percent(total, prev_total),
                    previous_total=prev_total,
                ),
            )
        )

    return ByCategoryResponse(
        period=PeriodSchema(start=start, end=end),
        categories=items,
    )
