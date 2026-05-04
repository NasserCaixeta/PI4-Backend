import uuid
from datetime import date as date_type, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.dependencies import get_current_user
from app.database import get_db
from app.models.auth import FreeUsage, User
from app.models.statements import BankStatement, Category, Transaction
from app.schemas.statements import StatementDetailResponse, StatementResponse
from app.services.gemini import extract_transactions

router = APIRouter(prefix="/statements", tags=["Statements"])


@router.post("/upload", response_model=StatementResponse, status_code=200)
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

    # Processa síncrono
    try:
        transactions_data = extract_transactions(pdf_bytes)

        # Busca categorias default para mapear por nome
        cat_result = await db.execute(
            select(Category).where(Category.is_default == True)
        )
        categories = {c.name: c.id for c in cat_result.scalars()}

        for tx in transactions_data:
            category_id = categories.get(tx.get("category"))
            tx_date = tx["date"]
            if isinstance(tx_date, str):
                tx_date = date_type.fromisoformat(tx_date)
            transaction = Transaction(
                statement_id=statement.id,
                date=tx_date,
                description=tx["description"],
                amount=Decimal(str(tx["amount"])),
                type=tx["type"],
                category_id=category_id,
            )
            db.add(transaction)

        statement.status = "completed"
        statement.processed_at = datetime.utcnow()
    except Exception:
        statement.status = "error"

    await db.commit()
    await db.refresh(statement)

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
    from sqlalchemy.orm import selectinload as _sel
    from app.models.statements import Transaction

    result = await db.execute(
        select(BankStatement)
        .options(
            _sel(BankStatement.transactions).selectinload(Transaction.category)
        )
        .where(BankStatement.id == statement_id, BankStatement.user_id == user.id)
    )
    statement = result.scalar_one_or_none()

    if not statement:
        raise HTTPException(status_code=404, detail="Statement não encontrado")

    return statement
