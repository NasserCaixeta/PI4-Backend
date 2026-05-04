import asyncio
import base64
import uuid as uuid_mod
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.models.statements import BankStatement, Category, Transaction
from app.services.gemini import extract_transactions
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
                transactions_data = extract_transactions(pdf_bytes)

                # Busca categorias default para mapear por nome
                cat_result = await db.execute(
                    select(Category).where(Category.is_default == True)
                )
                categories = {c.name: c.id for c in cat_result.scalars()}

                # Cria transações
                for tx in transactions_data:
                    category_id = categories.get(tx["category"])
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
