import uuid
import calendar
import hashlib
from datetime import date as date_type, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.dependencies import get_current_user
from app.database import get_db
from app.models.auth import User
from app.models.statements import BankStatement, Category, Transaction
from app.schemas.statements import DeleteMonthResponse, StatementDetailResponse, StatementResponse
from app.services.billing import consume_analysis_or_raise
from app.services.categories import normalize_transaction_category
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

    # Lê arquivo e calcula hash antes de cobrar/consumir análise
    pdf_bytes = await file.read()
    file_hash = hashlib.sha256(pdf_bytes).hexdigest()
    file_size_kb = len(pdf_bytes) // 1024

    duplicate_result = await db.execute(
        select(BankStatement).where(
            BankStatement.user_id == user.id,
            BankStatement.file_hash == file_hash,
        )
    )
    if duplicate_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Este extrato já foi enviado anteriormente",
        )

    await consume_analysis_or_raise(db, user)

    # Cria statement
    statement = BankStatement(
        user_id=user.id,
        filename=file.filename,
        file_size_kb=file_size_kb,
        file_hash=file_hash,
        status="processing",
    )
    db.add(statement)
    await db.commit()
    await db.refresh(statement)

    # Processa síncrono
    try:
        extraction = extract_transactions(pdf_bytes)
        statement.statement_type = extraction["statement_type"]
        transactions_data = extraction["transactions"]

        # Busca categorias default para mapear por nome
        cat_result = await db.execute(
            select(Category).where(Category.is_default == True)
        )
        categories = {c.name: c.id for c in cat_result.scalars()}

        for tx in transactions_data:
            category_name = normalize_transaction_category(tx["description"], tx.get("category"))
            category_id = categories.get(category_name) or categories.get("Outros")
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
    except Exception as e:
        import traceback
        print(f"[UPLOAD ERROR] {type(e).__name__}: {e}")
        traceback.print_exc()
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


@router.delete("/month", response_model=DeleteMonthResponse)
async def delete_statement_month(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    month: int = Query(..., ge=1, le=12),
    year: int = Query(..., ge=2000, le=2100),
):
    last_day = calendar.monthrange(year, month)[1]
    start = date_type(year, month, 1)
    end = date_type(year, month, last_day)

    tx_result = await db.execute(
        select(Transaction)
        .join(BankStatement)
        .where(
            BankStatement.user_id == user.id,
            Transaction.date >= start,
            Transaction.date <= end,
        )
    )
    transactions = tx_result.scalars().all()
    statement_ids = {tx.statement_id for tx in transactions}

    for transaction in transactions:
        await db.delete(transaction)

    await db.flush()

    deleted_empty_statements = 0
    for statement_id in statement_ids:
        count_result = await db.execute(
            select(func.count(Transaction.id)).where(Transaction.statement_id == statement_id)
        )
        if count_result.scalar_one() == 0:
            statement_result = await db.execute(
                select(BankStatement).where(
                    BankStatement.id == statement_id,
                    BankStatement.user_id == user.id,
                )
            )
            statement = statement_result.scalar_one_or_none()
            if statement:
                await db.delete(statement)
                deleted_empty_statements += 1

    await db.commit()

    return DeleteMonthResponse(
        deleted_transactions=len(transactions),
        deleted_empty_statements=deleted_empty_statements,
    )


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
