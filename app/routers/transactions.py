import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.dependencies import get_current_user
from app.database import get_db
from app.models.auth import User
from app.models.statements import BankStatement, Transaction
from app.schemas.transactions import (
    TransactionListResponse,
    TransactionResponse,
    TransactionUpdate,
)

router = APIRouter(prefix="/transactions", tags=["Transactions"])


def get_date_filter(
    month: int | None, year: int | None, start_date: date | None, end_date: date | None
) -> tuple[date | None, date | None]:
    """Returns start and end date based on params. Returns (None, None) if no filter."""
    if month and year:
        import calendar
        last_day = calendar.monthrange(year, month)[1]
        return date(year, month, 1), date(year, month, last_day)
    if start_date and end_date:
        return start_date, end_date
    return None, None


@router.get("", response_model=TransactionListResponse)
async def list_transactions(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    month: int | None = Query(None, ge=1, le=12),
    year: int | None = Query(None, ge=2000, le=2100),
    start_date: date | None = None,
    end_date: date | None = None,
    category_id: uuid.UUID | None = None,
    type: str | None = Query(None, pattern="^(credit|debit)$"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    # Base query: only user's transactions via statement
    base_query = (
        select(Transaction)
        .join(BankStatement)
        .where(BankStatement.user_id == user.id)
        .options(selectinload(Transaction.category))
    )

    # Apply filters
    filters = []
    date_start, date_end = get_date_filter(month, year, start_date, end_date)
    if date_start and date_end:
        filters.append(Transaction.date >= date_start)
        filters.append(Transaction.date <= date_end)
    if category_id:
        filters.append(Transaction.category_id == category_id)
    if type:
        filters.append(Transaction.type == type)

    if filters:
        base_query = base_query.where(and_(*filters))

    # Count total
    count_query = select(func.count()).select_from(
        base_query.with_only_columns(Transaction.id).subquery()
    )
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Paginate
    query = base_query.order_by(Transaction.date.desc()).limit(limit).offset(offset)
    result = await db.execute(query)
    items = result.scalars().all()

    return TransactionListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/{transaction_id}", response_model=TransactionResponse)
async def get_transaction(
    transaction_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Transaction)
        .join(BankStatement)
        .where(Transaction.id == transaction_id, BankStatement.user_id == user.id)
        .options(selectinload(Transaction.category))
    )
    transaction = result.scalar_one_or_none()

    if not transaction:
        raise HTTPException(status_code=404, detail="Transação não encontrada")

    return transaction


@router.patch("/{transaction_id}", response_model=TransactionResponse)
async def update_transaction(
    transaction_id: uuid.UUID,
    data: TransactionUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Transaction)
        .join(BankStatement)
        .where(Transaction.id == transaction_id, BankStatement.user_id == user.id)
        .options(selectinload(Transaction.category))
    )
    transaction = result.scalar_one_or_none()

    if not transaction:
        raise HTTPException(status_code=404, detail="Transação não encontrada")

    if data.category_id is not None:
        transaction.category_id = data.category_id
    if data.description is not None:
        transaction.description = data.description

    await db.commit()
    await db.refresh(transaction, ["category"])
    return transaction


@router.delete("/{transaction_id}", status_code=204)
async def delete_transaction(
    transaction_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Transaction)
        .join(BankStatement)
        .where(Transaction.id == transaction_id, BankStatement.user_id == user.id)
    )
    transaction = result.scalar_one_or_none()

    if not transaction:
        raise HTTPException(status_code=404, detail="Transação não encontrada")

    await db.delete(transaction)
    await db.commit()
