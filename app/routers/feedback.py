import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.database import get_db
from app.models.auth import User
from app.models.feedback import SpendingFeedback
from app.schemas.feedback import (
    FeedbackDetailResponse,
    FeedbackGenerateRequest,
    FeedbackGenerateResponse,
    FeedbackListItem,
)
from app.services.billing import ensure_analysis_available_or_raise
from app.workers.tasks import generate_spending_feedback

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

    existing_result = await db.execute(
        select(SpendingFeedback).where(
            SpendingFeedback.user_id == user.id,
            SpendingFeedback.month == data.month,
            SpendingFeedback.year == data.year,
        )
    )
    feedback = existing_result.scalar_one_or_none()
    if feedback and feedback.status in {"processing", "completed"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Já existe um feedback para este mês. Delete-o antes de gerar novamente.",
        )

    await ensure_analysis_available_or_raise(db, user)

    if feedback:
        feedback.status = "processing"
        feedback.error_message = None
        feedback.subscriptions = None
        feedback.reducible_expenses = None
        feedback.highlights = None
        feedback.saving_opportunities = None
        feedback.watchlist = None
        feedback.total_potential_saving = None
        feedback.summary = None
        feedback.completed_at = None
    else:
        feedback = SpendingFeedback(
            user_id=user.id,
            month=data.month,
            year=data.year,
            status="processing",
        )
        db.add(feedback)

    await db.commit()
    await db.refresh(feedback)

    try:
        generate_spending_feedback.delay(str(feedback.id))
    except Exception as exc:
        feedback.status = "error"
        feedback.error_message = "Não foi possível enfileirar o processamento"
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Não foi possível enfileirar o processamento do feedback",
        ) from exc

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
