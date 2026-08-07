import base64
import uuid

import pytest
from sqlalchemy import select

from app.models.auth import User
from app.models.statements import BankStatement, Transaction
from app.workers.tasks import process_statement_pdf_payload


async def _create_user(db):
    user = User(
        id=uuid.uuid4(),
        email=f"worker_{uuid.uuid4().hex[:8]}@example.com",
        auth_provider="email",
    )
    db.add(user)
    await db.flush()
    return user


@pytest.mark.anyio
async def test_process_statement_pdf_payload_completes_statement(db):
    user = await _create_user(db)
    statement = BankStatement(
        user_id=user.id,
        filename="worker.pdf",
        file_size_kb=1,
        file_hash="worker-success",
        status="processing",
    )
    db.add(statement)
    await db.commit()
    await db.refresh(statement)

    pdf_payload = base64.b64encode(b"%PDF-worker").decode("ascii")

    def extractor(_pdf_bytes):
        return {
            "statement_type": "credit_card",
            "transactions": [
                {
                    "date": "2026-04-10",
                    "description": "Fisia Nike Ecommer",
                    "amount": 100,
                    "type": "debit",
                    "category": "Outros",
                }
            ],
        }

    await process_statement_pdf_payload(db, str(statement.id), pdf_payload, extractor=extractor)

    await db.refresh(statement)
    assert statement.status == "completed"
    assert statement.error_message is None
    assert statement.processed_at is not None

    tx_result = await db.execute(select(Transaction).where(Transaction.statement_id == statement.id))
    transactions = tx_result.scalars().all()
    assert len(transactions) == 1
    assert transactions[0].description == "Fisia Nike Ecommer"


@pytest.mark.anyio
async def test_process_statement_pdf_payload_marks_error_without_transactions(db):
    user = await _create_user(db)
    statement = BankStatement(
        user_id=user.id,
        filename="worker-error.pdf",
        file_size_kb=1,
        file_hash="worker-error",
        status="processing",
    )
    db.add(statement)
    await db.commit()
    await db.refresh(statement)

    pdf_payload = base64.b64encode(b"%PDF-worker-error").decode("ascii")

    def extractor(_pdf_bytes):
        raise ValueError("Gemini failed")

    await process_statement_pdf_payload(db, str(statement.id), pdf_payload, extractor=extractor)

    await db.refresh(statement)
    assert statement.status == "error"
    assert statement.error_message == "Could not extract transactions from PDF"

    tx_result = await db.execute(select(Transaction).where(Transaction.statement_id == statement.id))
    assert tx_result.scalars().all() == []


@pytest.mark.anyio
async def test_process_statement_pdf_payload_consumes_usage_on_success(db):
    user = await _create_user(db)
    statement = BankStatement(
        user_id=user.id,
        filename="worker-billing.pdf",
        file_size_kb=1,
        file_hash="worker-billing",
        status="processing",
    )
    db.add(statement)
    await db.commit()
    await db.refresh(statement)

    pdf_payload = base64.b64encode(b"%PDF-worker-billing").decode("ascii")

    def extractor(_pdf_bytes):
        return {"statement_type": "credit_card", "transactions": []}

    await process_statement_pdf_payload(db, str(statement.id), pdf_payload, extractor=extractor)

    from app.models.auth import FreeUsage

    usage_result = await db.execute(select(FreeUsage).where(FreeUsage.user_id == user.id))
    free_usage = usage_result.scalar_one_or_none()
    assert free_usage is not None
    assert free_usage.analyses_used == 1


@pytest.mark.anyio
async def test_process_statement_pdf_payload_does_not_consume_usage_on_failure(db):
    user = await _create_user(db)
    user_id = user.id
    statement = BankStatement(
        user_id=user.id,
        filename="worker-no-billing.pdf",
        file_size_kb=1,
        file_hash="worker-no-billing",
        status="processing",
    )
    db.add(statement)
    await db.commit()
    await db.refresh(statement)

    pdf_payload = base64.b64encode(b"%PDF-worker-no-billing").decode("ascii")

    def extractor(_pdf_bytes):
        raise ValueError("Gemini failed")

    await process_statement_pdf_payload(db, str(statement.id), pdf_payload, extractor=extractor)

    from app.models.auth import FreeUsage

    usage_result = await db.execute(select(FreeUsage).where(FreeUsage.user_id == user_id))
    assert usage_result.scalar_one_or_none() is None
