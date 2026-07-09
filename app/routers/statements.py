import uuid
import base64
import calendar
import hashlib
from datetime import date as date_type

from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.database import get_db
from app.models.auth import User
from app.models.statements import BankStatement, Transaction
from app.schemas.statements import DeleteMonthResponse, StatementDetailResponse, StatementResponse
from app.services.billing import ensure_analysis_available_or_raise
from app.workers.tasks import process_statement

limiter = Limiter(key_func=get_remote_address)

MAX_PDF_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB

router = APIRouter(prefix="/statements", tags=["Statements"])


@router.post("/upload", response_model=StatementResponse, status_code=200)
@limiter.limit("10/minute")
async def upload_statement(
    request: Request,
    file: UploadFile,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Valida tipo de arquivo pelo header
    if file.content_type not in ("application/pdf", "application/octet-stream"):
        raise HTTPException(status_code=400, detail="Apenas PDFs são aceitos")

    # Valida tamanho antes de ler tudo na memória
    if file.size is not None and file.size > MAX_PDF_SIZE_BYTES:
        raise HTTPException(status_code=400, detail="Arquivo muito grande. Limite: 10 MB")

    # Lê arquivo e calcula hash antes de cobrar/consumir análise
    pdf_bytes = await file.read()

    # Valida tamanho real após leitura (caso file.size não estivesse disponível)
    if len(pdf_bytes) > MAX_PDF_SIZE_BYTES:
        raise HTTPException(status_code=400, detail="Arquivo muito grande. Limite: 10 MB")

    # Valida magic bytes reais do PDF
    if not pdf_bytes.startswith(b"%PDF-"):
        raise HTTPException(status_code=400, detail="Arquivo inválido. Apenas PDFs reais são aceitos")
    file_hash = hashlib.sha256(pdf_bytes).hexdigest()
    file_size_kb = len(pdf_bytes) // 1024

    existing_result = await db.execute(
        select(BankStatement).where(
            BankStatement.user_id == user.id,
            BankStatement.file_hash == file_hash,
        )
    )
    existing_statement = existing_result.scalar_one_or_none()
    if existing_statement and existing_statement.status in {"processing", "completed"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Este extrato já foi enviado anteriormente",
        )

    await ensure_analysis_available_or_raise(db, user)

    if existing_statement:
        statement = existing_statement
        statement.filename = file.filename
        statement.file_size_kb = file_size_kb
        statement.statement_type = None
        statement.status = "processing"
        statement.error_message = None
        statement.processed_at = None
    else:
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

    pdf_payload = base64.b64encode(pdf_bytes).decode("ascii")
    try:
        process_statement.delay(str(statement.id), pdf_payload)
    except Exception as exc:
        statement.status = "error"
        statement.error_message = "Não foi possível enfileirar o processamento"
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Não foi possível enfileirar o processamento do PDF",
        ) from exc

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
