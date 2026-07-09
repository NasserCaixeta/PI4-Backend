import asyncio
import base64
import calendar as cal
import uuid as uuid_mod
from datetime import date as date_type, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.auth import User
from app.models.feedback import SpendingFeedback
from app.models.statements import BankStatement, Category, Transaction
from app.services.billing import consume_analysis_or_raise
from app.services.gemini import extract_transactions
from app.services.spending_insights import generate_spending_analysis
from app.services.statement_processing import StatementProcessingError, process_statement_pdf
from app.workers.celery_app import celery_app


async def process_statement_pdf_payload(
    db: AsyncSession,
    statement_id: str,
    pdf_bytes_b64: str,
    extractor=extract_transactions,
) -> None:
    statement_uuid = uuid_mod.UUID(statement_id)
    result = await db.execute(
        select(BankStatement)
        .options(selectinload(BankStatement.user).selectinload(User.subscription))
        .where(BankStatement.id == statement_uuid)
    )
    statement = result.scalar_one_or_none()
    if statement is None:
        return

    pdf_bytes = base64.b64decode(pdf_bytes_b64)

    try:
        await process_statement_pdf(
            db,
            statement,
            pdf_bytes,
            extractor,
            replace_existing=True,
        )
        await consume_analysis_or_raise(db, statement.user)
    except StatementProcessingError as exc:
        await db.rollback()
        error_result = await db.execute(select(BankStatement).where(BankStatement.id == statement_uuid))
        error_statement = error_result.scalar_one_or_none()
        if error_statement is not None:
            error_statement.status = "error"
            error_statement.error_message = str(exc)
            await db.commit()
        return
    except Exception:
        await db.rollback()
        error_result = await db.execute(select(BankStatement).where(BankStatement.id == statement_uuid))
        error_statement = error_result.scalar_one_or_none()
        if error_statement is not None:
            error_statement.status = "error"
            error_statement.error_message = "Erro inesperado ao processar PDF"
            await db.commit()
        return

    await db.commit()


@celery_app.task
def process_statement(statement_id: str, pdf_bytes_b64: str):
    async def _process():
        engine = create_async_engine(settings.async_database_url, echo=False)
        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async with session_factory() as db:
            await process_statement_pdf_payload(db, statement_id, pdf_bytes_b64)

        await engine.dispose()

    asyncio.run(_process())


async def process_spending_feedback(
    db: AsyncSession,
    feedback_id: str,
    analyzer=generate_spending_analysis,
) -> None:
    feedback_uuid = uuid_mod.UUID(feedback_id)
    result = await db.execute(
        select(SpendingFeedback)
        .options(selectinload(SpendingFeedback.user).selectinload(User.subscription))
        .where(SpendingFeedback.id == feedback_uuid)
    )
    feedback = result.scalar_one_or_none()
    if feedback is None:
        return

    try:
        last_day = cal.monthrange(feedback.year, feedback.month)[1]
        start = date_type(feedback.year, feedback.month, 1)
        end = date_type(feedback.year, feedback.month, last_day)

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
                BankStatement.user_id == feedback.user_id,
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

        analysis = analyzer(transactions)

        feedback.subscriptions = analysis["subscriptions"]
        feedback.reducible_expenses = analysis["reducible_expenses"]
        feedback.highlights = analysis["highlights"]
        feedback.saving_opportunities = analysis["saving_opportunities"]
        feedback.watchlist = analysis["watchlist"]
        feedback.total_potential_saving = analysis["total_potential_saving"]
        feedback.summary = analysis["summary"]
        feedback.status = "completed"
        feedback.error_message = None
        feedback.completed_at = datetime.utcnow()
        await consume_analysis_or_raise(db, feedback.user)
    except Exception as exc:
        await db.rollback()
        error_result = await db.execute(select(SpendingFeedback).where(SpendingFeedback.id == feedback_uuid))
        error_feedback = error_result.scalar_one_or_none()
        if error_feedback is not None:
            error_feedback.status = "error"
            error_feedback.error_message = str(exc) or "Erro inesperado ao gerar feedback"
            await db.commit()
        return

    await db.commit()


@celery_app.task
def generate_spending_feedback(feedback_id: str):
    async def _process():
        engine = create_async_engine(settings.async_database_url, echo=False)
        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async with session_factory() as db:
            await process_spending_feedback(db, feedback_id)

        await engine.dispose()

    asyncio.run(_process())
