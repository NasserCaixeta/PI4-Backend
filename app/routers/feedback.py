import calendar as cal
import uuid
from datetime import date as date_type, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.database import get_db
from app.models.auth import User
from app.models.feedback import SpendingFeedback
from app.models.statements import BankStatement, Category, Transaction
from app.schemas.feedback import (
    FeedbackDetailResponse,
    FeedbackGenerateRequest,
    FeedbackGenerateResponse,
    FeedbackListItem,
)
from app.services.billing import consume_analysis_or_raise, ensure_analysis_available_or_raise
from app.services.spending_insights import generate_spending_analysis

limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/feedback", tags=["Feedback"])


@router.post("/generate", response_model=FeedbackGenerateResponse, status_code=201)
@limiter.limit("5/minute")
async def generate_feedback(
    request: Request,
    data: FeedbackGenerateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not (1 <= data.month <= 12):
        raise HTTPException(status_code=422, detail="Mês inválido")
    if not (2000 <= data.year <= 2100):
        raise HTTPException(status_code=422, detail="Ano inválido")

    existing = await db.execute(
        select(SpendingFeedback).where(
            SpendingFeedback.user_id == user.id,
            SpendingFeedback.month == data.month,
            SpendingFeedback.year == data.year,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Já existe um feedback para este mês. Delete-o antes de gerar novamente.",
        )

    await ensure_analysis_available_or_raise(db, user)

    feedback = SpendingFeedback(
        user_id=user.id,
        month=data.month,
        year=data.year,
        status="processing",
    )
    db.add(feedback)
    await db.commit()
    await db.refresh(feedback)

    # ── Processamento síncrono (igual ao statements.py) ──────────────────────
    try:
        last_day = cal.monthrange(data.year, data.month)[1]
        start = date_type(data.year, data.month, 1)
        end = date_type(data.year, data.month, last_day)

        tx_result = await db.execute(
            select(
                Transaction.date,
                Transaction.description,
                Transaction.amount,
                Transaction.type,
                Category.name.label("category"),
            )
            .join(BankStatement, Transaction.statement_id == BankStatement.id)
            .outerjoin(Category, Transaction.category_id == Category.id)
            .where(
                BankStatement.user_id == user.id,
                Transaction.date >= start,
                Transaction.date <= end,
                Transaction.type == "debit",
            )
        )
        transactions = [
            {
                "date": str(row.date),
                "description": row.description,
                "amount": float(row.amount),
                "type": row.type,
                "category": row.category or "Outros",
            }
            for row in tx_result
        ]

        analysis = generate_spending_analysis(transactions)

        feedback.subscriptions = analysis["subscriptions"]
        feedback.reducible_expenses = analysis["reducible_expenses"]
        feedback.highlights = analysis["highlights"]
        feedback.saving_opportunities = analysis["saving_opportunities"]
        feedback.watchlist = analysis["watchlist"]
        feedback.total_potential_saving = analysis["total_potential_saving"]
        feedback.summary = analysis["summary"]
        feedback.status = "completed"
        feedback.completed_at = datetime.utcnow()
        await consume_analysis_or_raise(db, user)

    except Exception as e:
        import traceback
        print(f"[FEEDBACK ERROR] {type(e).__name__}: {e}")
        traceback.print_exc()
        feedback.status = "error"

    await db.commit()
    await db.refresh(feedback)

    return FeedbackGenerateResponse(feedback_id=feedback.id, status=feedback.status)


@router.get("", response_model=list[FeedbackListItem])
async def list_feedbacks(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SpendingFeedback)
        .where(SpendingFeedback.user_id == user.id)
        .order_by(SpendingFeedback.year.desc(), SpendingFeedback.month.desc())
    )
    return result.scalars().all()


@router.get("/{feedback_id}", response_model=FeedbackDetailResponse)
async def get_feedback(
    feedback_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SpendingFeedback).where(
            SpendingFeedback.id == feedback_id,
            SpendingFeedback.user_id == user.id,
        )
    )
    feedback = result.scalar_one_or_none()
    if not feedback:
        raise HTTPException(status_code=404, detail="Feedback não encontrado")
    return feedback


@router.delete("/{feedback_id}", status_code=204)
async def delete_feedback(
    feedback_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SpendingFeedback).where(
            SpendingFeedback.id == feedback_id,
            SpendingFeedback.user_id == user.id,
        )
    )
    feedback = result.scalar_one_or_none()
    if not feedback:
        raise HTTPException(status_code=404, detail="Feedback não encontrado")
    await db.delete(feedback)
    await db.commit()
