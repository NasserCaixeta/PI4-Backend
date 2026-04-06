import base64
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.dependencies import get_current_user
from app.database import get_db
from app.models.auth import FreeUsage, User
from app.models.statements import BankStatement
from app.schemas.statements import StatementDetailResponse, StatementResponse
from app.workers.tasks import process_statement

router = APIRouter(prefix="/statements", tags=["Statements"])


@router.post("/upload", response_model=StatementResponse, status_code=202)
async def upload_statement(
    file: UploadFile,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Valida tipo de arquivo
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Apenas PDFs são aceitos")

    # Verifica paywall (se não tem assinatura ativa)
    has_subscription = user.subscription and user.subscription.status == "active"

    if not has_subscription:
        # Busca ou cria FreeUsage
        result = await db.execute(
            select(FreeUsage).where(FreeUsage.user_id == user.id)
        )
        free_usage = result.scalar_one_or_none()

        if not free_usage:
            free_usage = FreeUsage(user_id=user.id, analyses_used=0)
            db.add(free_usage)

        if free_usage.analyses_used >= settings.FREE_ANALYSES_LIMIT:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail="Limite de análises gratuitas atingido",
            )

        free_usage.analyses_used += 1

    # Lê arquivo
    pdf_bytes = await file.read()
    file_size_kb = len(pdf_bytes) // 1024

    # Cria statement
    statement = BankStatement(
        user_id=user.id,
        filename=file.filename,
        file_size_kb=file_size_kb,
        status="processing",
    )
    db.add(statement)
    await db.commit()
    await db.refresh(statement)

    # Enfileira task
    pdf_b64 = base64.b64encode(pdf_bytes).decode()
    process_statement.delay(str(statement.id), pdf_b64)

    return statement


@router.get("", response_model=list[StatementResponse])
async def list_statements(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(BankStatement)
        .where(BankStatement.user_id == user.id)
        .order_by(BankStatement.uploaded_at.desc())
    )
    return result.scalars().all()


@router.get("/{statement_id}", response_model=StatementDetailResponse)
async def get_statement(
    statement_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(BankStatement)
        .options(selectinload(BankStatement.transactions))
        .where(BankStatement.id == statement_id, BankStatement.user_id == user.id)
    )
    statement = result.scalar_one_or_none()

    if not statement:
        raise HTTPException(status_code=404, detail="Statement não encontrado")

    return statement
