from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.database import get_db
from app.models.auth import User
from app.schemas.dashboard import ByCategoryResponse, SummaryResponse
from app.services import dashboard as dashboard_service

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/summary", response_model=SummaryResponse)
async def get_summary(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    month: int | None = Query(None, ge=1, le=12),
    year: int | None = Query(None, ge=2000, le=2100),
    start_date: date | None = None,
    end_date: date | None = None,
):
    return await dashboard_service.get_summary(db, user.id, month, year, start_date, end_date)


@router.get("/by-category", response_model=ByCategoryResponse)
async def get_by_category(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    month: int | None = Query(None, ge=1, le=12),
    year: int | None = Query(None, ge=2000, le=2100),
    start_date: date | None = None,
    end_date: date | None = None,
):
    return await dashboard_service.get_by_category(db, user.id, month, year, start_date, end_date)
