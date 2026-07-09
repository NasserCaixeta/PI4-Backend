import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.auth import FreeUsage, User
from app.models.feedback import SpendingFeedback
from app.models.statements import BankStatement, Transaction
from app.workers.tasks import process_spending_feedback


MOCK_ANALYSIS = {
    "summary": "Seus gastos estão controlados.",
    "highlights": ["Economia potencial estimada de R$ 80,00."],
    "subscriptions": [{"name": "Spotify", "amount": 21.90, "description": "Música"}],
    "reducible_expenses": [
        {
            "category": "Alimentação",
            "description": "Delivery",
            "amount": 150.0,
            "suggestion": "Cozinhe mais",
            "potential_saving": 80.0,
        }
    ],
    "saving_opportunities": [
        {
            "title": "Delivery concentrado no mês",
            "category": "Alimentação",
            "type": "reduce",
            "amount": 150.0,
            "description": "Delivery",
            "suggestion": "Cozinhe mais",
            "potential_saving": 80.0,
            "confidence": "medium",
            "priority": 80,
            "reason": "Foram 3 transações somando R$ 150,00.",
            "evidence": ["IFOOD - R$ 50.00"],
        }
    ],
    "watchlist": [],
    "total_potential_saving": 80.0,
}


async def _create_user(db):
    user = User(
        id=uuid.uuid4(),
        email=f"feedback_worker_{uuid.uuid4().hex[:8]}@example.com",
        auth_provider="email",
    )
    db.add(user)
    await db.flush()
    return user


async def _create_feedback_with_transaction(db):
    user = await _create_user(db)
    statement = BankStatement(
        user_id=user.id,
        filename="feedback-worker.pdf",
        file_size_kb=1,
        file_hash=f"feedback-worker-{uuid.uuid4()}",
        status="completed",
        statement_type="credit_card",
    )
    db.add(statement)
    await db.flush()

    db.add(
        Transaction(
            statement_id=statement.id,
            date=date(2026, 4, 10),
            description="Mercado",
            amount=Decimal("100"),
            type="debit",
        )
    )
    feedback = SpendingFeedback(
        user_id=user.id,
        month=4,
        year=2026,
        status="processing",
    )
    db.add(feedback)
    await db.commit()
    await db.refresh(feedback)
    return user, feedback


@pytest.mark.anyio
async def test_process_spending_feedback_completes_and_consumes_usage(db):
    user, feedback = await _create_feedback_with_transaction(db)

    def analyzer(transactions):
        assert len(transactions) == 1
        assert transactions[0]["description"] == "Mercado"
        return MOCK_ANALYSIS

    await process_spending_feedback(db, str(feedback.id), analyzer=analyzer)

    await db.refresh(feedback)
    assert feedback.status == "completed"
    assert feedback.error_message is None
    assert feedback.completed_at is not None
    assert feedback.summary == MOCK_ANALYSIS["summary"]
    assert feedback.highlights == MOCK_ANALYSIS["highlights"]
    assert feedback.saving_opportunities == MOCK_ANALYSIS["saving_opportunities"]

    usage_result = await db.execute(select(FreeUsage).where(FreeUsage.user_id == user.id))
    free_usage = usage_result.scalar_one_or_none()
    assert free_usage is not None
    assert free_usage.analyses_used == 1


@pytest.mark.anyio
async def test_process_spending_feedback_marks_error_without_consuming_usage(db):
    user, feedback = await _create_feedback_with_transaction(db)
    user_id = user.id

    def analyzer(_transactions):
        raise ValueError("analysis failed")

    await process_spending_feedback(db, str(feedback.id), analyzer=analyzer)

    await db.refresh(feedback)
    assert feedback.status == "error"
    assert feedback.error_message == "analysis failed"

    usage_result = await db.execute(select(FreeUsage).where(FreeUsage.user_id == user_id))
    assert usage_result.scalar_one_or_none() is None


@pytest.mark.anyio
async def test_process_spending_feedback_ignores_missing_feedback(db):
    await process_spending_feedback(db, str(uuid.uuid4()), analyzer=lambda transactions: MOCK_ANALYSIS)


@pytest.mark.anyio
async def test_process_spending_feedback_filters_user_month_year_and_debit(db):
    user, feedback = await _create_feedback_with_transaction(db)
    other_user = await _create_user(db)

    own_statement = BankStatement(
        user_id=user.id,
        filename="own-extra.pdf",
        file_size_kb=1,
        file_hash=f"own-extra-{uuid.uuid4()}",
        status="completed",
    )
    other_statement = BankStatement(
        user_id=other_user.id,
        filename="other.pdf",
        file_size_kb=1,
        file_hash=f"other-{uuid.uuid4()}",
        status="completed",
    )
    db.add_all([own_statement, other_statement])
    await db.flush()
    db.add_all(
        [
            Transaction(
                statement_id=own_statement.id,
                date=date(2026, 4, 12),
                description="Credito ignorado",
                amount=Decimal("10"),
                type="credit",
            ),
            Transaction(
                statement_id=own_statement.id,
                date=date(2026, 5, 1),
                description="Mes ignorado",
                amount=Decimal("20"),
                type="debit",
            ),
            Transaction(
                statement_id=other_statement.id,
                date=date(2026, 4, 10),
                description="Outro usuario ignorado",
                amount=Decimal("30"),
                type="debit",
            ),
        ]
    )
    await db.commit()

    seen_descriptions = []

    def analyzer(transactions):
        seen_descriptions.extend(tx["description"] for tx in transactions)
        return MOCK_ANALYSIS

    await process_spending_feedback(db, str(feedback.id), analyzer=analyzer)

    assert seen_descriptions == ["Mercado"]
