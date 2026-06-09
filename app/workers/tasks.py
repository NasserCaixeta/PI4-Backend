import asyncio
import base64
import uuid as uuid_mod
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.models.feedback import SpendingFeedback
from app.models.statements import BankStatement, Category, Transaction
from app.services.categories import normalize_transaction_category
from app.services.gemini import analyze_spending, extract_transactions
from app.workers.celery_app import celery_app


@celery_app.task
def process_statement(statement_id: str, pdf_bytes_b64: str):
    """
    Processa o PDF: extrai transações via Gemini e salva no banco.

    Atualiza status:
    - "processing" → "completed" (sucesso)
    - "processing" → "error" (falha)
    """
    pdf_bytes = base64.b64decode(pdf_bytes_b64)

    async def _process():
        engine = create_async_engine(settings.async_database_url, echo=False)
        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        print(f"[DEBUG] Task received - statement_id: {statement_id}")
        print(f"[DEBUG] DB URL: {engine.url}")
        print(f"[DEBUG] PDF bytes length: {len(pdf_bytes)}")

        async with session_factory() as db:
            # Busca statement
            stmt_uuid = uuid_mod.UUID(statement_id)
            print(f"[DEBUG] Querying for UUID: {stmt_uuid}")
            result = await db.execute(
                select(BankStatement).where(BankStatement.id == stmt_uuid)
            )
            statement = result.scalar_one_or_none()
            print(f"[DEBUG] Statement found: {statement}")
            if not statement:
                return

            try:
                # Extrai transações via Gemini
                extraction = extract_transactions(pdf_bytes)
                statement.statement_type = extraction["statement_type"]
                transactions_data = extraction["transactions"]

                # Busca categorias default para mapear por nome
                cat_result = await db.execute(
                    select(Category).where(Category.is_default == True)
                )
                categories = {c.name: c.id for c in cat_result.scalars()}

                # Cria transações
                for tx in transactions_data:
                    category_name = normalize_transaction_category(tx["description"], tx.get("category"))
                    category_id = categories.get(category_name) or categories.get("Outros")
                    tx_date = tx["date"]
                    if isinstance(tx_date, str):
                        tx_date = date.fromisoformat(tx_date)
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
                print(f"[DEBUG] ERROR: {type(e).__name__}: {e}")
                import traceback
                traceback.print_exc()
                statement.status = "error"

            await db.commit()

        await engine.dispose()

    asyncio.run(_process())


@celery_app.task
def generate_spending_feedback(feedback_id: str):
    """
    Gera feedback de gastos via Gemini para um período (mês/ano).

    Atualiza status:
    - "processing" → "completed" (sucesso)
    - "processing" → "error" (falha)
    """

    async def _process():
        engine = create_async_engine(settings.async_database_url, echo=False)
        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async with session_factory() as db:
            feedback_uuid = uuid_mod.UUID(feedback_id)
            result = await db.execute(
                select(SpendingFeedback).where(SpendingFeedback.id == feedback_uuid)
            )
            feedback = result.scalar_one_or_none()
            if not feedback:
                return

            feedback.status = "processing"
            await db.commit()

            try:
                import calendar as cal
                from datetime import date as date_type

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

                analysis = analyze_spending(transactions)

                feedback.subscriptions = analysis["subscriptions"]
                feedback.reducible_expenses = analysis["reducible_expenses"]
                feedback.summary = analysis["summary"]
                feedback.status = "completed"
                feedback.completed_at = datetime.utcnow()

            except Exception as e:
                print(f"[FEEDBACK ERROR] {type(e).__name__}: {e}")
                import traceback
                traceback.print_exc()
                feedback.status = "error"

            await db.commit()

        await engine.dispose()

    asyncio.run(_process())
