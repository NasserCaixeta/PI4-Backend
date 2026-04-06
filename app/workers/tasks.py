import asyncio
import base64
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select

from app.database import async_session
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
        async with async_session() as db:
            # Busca statement
            result = await db.execute(
                select(BankStatement).where(BankStatement.id == statement_id)
            )
            statement = result.scalar_one_or_none()
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
                    transaction = Transaction(
                        statement_id=statement.id,
                        date=tx["date"],
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

    asyncio.run(_process())
