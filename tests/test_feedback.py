import base64
import uuid as uuid_module
from unittest.mock import patch

import pytest

from app.workers.tasks import process_spending_feedback, process_statement_pdf_payload

MOCK_ANALYSIS = {
    "summary": "Seus gastos estão controlados.",
    "highlights": ["Economia potencial estimada de R$ 80,00."],
    "subscriptions": [{"name": "Spotify", "amount": 21.90, "description": "Música"}],
    "reducible_expenses": [{"category": "Alimentação", "description": "Delivery", "amount": 150.0, "suggestion": "Cozinhe mais", "potential_saving": 80.0}],
    "saving_opportunities": [{
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
    }],
    "watchlist": [],
    "total_potential_saving": 80.0,
}


async def _upload_with_tx(client, db, headers, date_str="2026-04-10", pdf_bytes=b"%PDF-feedback"):
    """Helper: accepts async upload and runs the statement worker helper."""
    extraction = {
        "statement_type": "credit_card",
        "transactions": [
            {"date": date_str, "description": "Mercado", "amount": 100, "type": "debit", "category": "Alimentação"}
        ],
    }
    with patch("app.routers.statements.process_statement") as mock:
        mock.delay.return_value = None
        response = await client.post(
            "/statements/upload",
            files={"file": ("extrato.pdf", pdf_bytes, "application/pdf")},
            headers=headers,
        )
    statement_id = response.json()["id"]
    pdf_payload = base64.b64encode(pdf_bytes).decode("ascii")

    def extractor(_pdf_bytes):
        return extraction

    await process_statement_pdf_payload(db, statement_id, pdf_payload, extractor=extractor)


@pytest.mark.anyio
async def test_generate_feedback_requires_auth(client):
    response = await client.post("/feedback/generate", json={"month": 4, "year": 2026})
    assert response.status_code == 401


@pytest.mark.anyio
async def test_generate_feedback_success_enqueues_job(client, auth_headers, db):
    await _upload_with_tx(client, db, auth_headers)

    with (
        patch("app.routers.feedback.generate_spending_feedback") as mock_task,
        patch("app.services.spending_insights.generate_spending_analysis") as mock_analysis,
    ):
        mock_task.delay.return_value = None
        response = await client.post(
            "/feedback/generate",
            json={"month": 4, "year": 2026},
            headers=auth_headers,
        )

    assert response.status_code == 201
    data = response.json()
    assert "feedback_id" in data
    assert data["status"] == "processing"
    mock_task.delay.assert_called_once_with(data["feedback_id"])
    mock_analysis.assert_not_called()


@pytest.mark.anyio
async def test_generate_feedback_does_not_consume_usage_until_worker_succeeds(client, db):
    unique_email = f"fb_async_usage_{uuid_module.uuid4().hex[:8]}@example.com"
    reg = await client.post("/auth/register", json={"email": unique_email, "password": "12345678"})
    token = reg.json()["access_token"]
    user_id = reg.json()["user"]["id"]
    headers = {"Authorization": f"Bearer {token}"}

    await _upload_with_tx(client, db, headers, pdf_bytes=b"%PDF-feedback-async-usage")

    with patch("app.routers.feedback.generate_spending_feedback") as mock_task:
        mock_task.delay.return_value = None
        response = await client.post("/feedback/generate", json={"month": 4, "year": 2026}, headers=headers)

    assert response.status_code == 201

    from sqlalchemy import select
    from app.models.auth import FreeUsage

    result = await db.execute(select(FreeUsage).where(FreeUsage.user_id == uuid_module.UUID(user_id)))
    free_usage = result.scalar_one_or_none()
    assert free_usage is not None
    assert free_usage.analyses_used == 1


@pytest.mark.anyio
async def test_generate_feedback_duplicate_returns_conflict(client, auth_headers, db):
    await _upload_with_tx(client, db, auth_headers)

    with patch("app.routers.feedback.generate_spending_feedback") as mock_task:
        mock_task.delay.return_value = None
        first = await client.post("/feedback/generate", json={"month": 4, "year": 2026}, headers=auth_headers)
        response = await client.post("/feedback/generate", json={"month": 4, "year": 2026}, headers=auth_headers)

    assert first.status_code == 201
    assert first.json()["status"] == "processing"
    assert response.status_code == 409
    assert mock_task.delay.call_count == 1


@pytest.mark.anyio
async def test_generate_feedback_allows_retry_after_error(client, auth_headers, db):
    await _upload_with_tx(client, db, auth_headers)

    with patch("app.routers.feedback.generate_spending_feedback") as mock_task:
        mock_task.delay.side_effect = [
            RuntimeError("redis unavailable"),
            None,
        ]

        failed = await client.post("/feedback/generate", json={"month": 4, "year": 2026}, headers=auth_headers)
        retry = await client.post("/feedback/generate", json={"month": 4, "year": 2026}, headers=auth_headers)

    assert failed.status_code == 503
    assert retry.status_code == 201
    assert retry.json()["status"] == "processing"


@pytest.mark.anyio
async def test_generate_feedback_enqueue_failure_marks_error(client, auth_headers, db):
    await _upload_with_tx(client, db, auth_headers, pdf_bytes=b"%PDF-feedback-enqueue-failure")

    with patch("app.routers.feedback.generate_spending_feedback") as mock_task:
        mock_task.delay.side_effect = RuntimeError("redis unavailable")
        response = await client.post("/feedback/generate", json={"month": 4, "year": 2026}, headers=auth_headers)

    assert response.status_code == 503
    assert "enfileirar" in response.json()["detail"].lower()

    feedbacks = await client.get("/feedback", headers=auth_headers)
    assert feedbacks.status_code == 200
    assert feedbacks.json()[0]["status"] == "error"
    assert feedbacks.json()[0]["error_message"] == "Não foi possível enfileirar o processamento"


@pytest.mark.anyio
async def test_generate_feedback_paywall(client, db):
    unique_email = f"fb_paywall_{uuid_module.uuid4().hex[:8]}@example.com"
    reg = await client.post("/auth/register", json={"email": unique_email, "password": "12345678"})
    token = reg.json()["access_token"]
    user_id = reg.json()["user"]["id"]
    headers = {"Authorization": f"Bearer {token}"}

    from app.core.config import settings
    from app.models.auth import FreeUsage

    db.add(FreeUsage(user_id=uuid_module.UUID(user_id), analyses_used=settings.FREE_ANALYSES_LIMIT))
    await db.commit()

    response = await client.post("/feedback/generate", json={"month": 4, "year": 2026}, headers=headers)
    assert response.status_code == 402


@pytest.mark.anyio
async def test_generate_feedback_request_does_not_consume_usage_when_worker_will_fail(client, db):
    unique_email = f"fb_fail_{uuid_module.uuid4().hex[:8]}@example.com"
    reg = await client.post("/auth/register", json={"email": unique_email, "password": "12345678"})
    token = reg.json()["access_token"]
    user_id = reg.json()["user"]["id"]
    headers = {"Authorization": f"Bearer {token}"}

    await _upload_with_tx(client, db, headers)

    with patch("app.routers.feedback.generate_spending_feedback") as mock_task:
        mock_task.delay.return_value = None
        response = await client.post("/feedback/generate", json={"month": 4, "year": 2026}, headers=headers)

    assert response.status_code == 201
    assert response.json()["status"] == "processing"

    from sqlalchemy import select
    from app.models.auth import FreeUsage

    result = await db.execute(
        select(FreeUsage).where(FreeUsage.user_id == uuid_module.UUID(user_id))
    )
    free_usage = result.scalar_one_or_none()
    assert free_usage is not None
    assert free_usage.analyses_used == 1


@pytest.mark.anyio
async def test_list_feedbacks_empty(client, auth_headers):
    response = await client.get("/feedback", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.anyio
async def test_list_feedbacks_includes_error_message(client, auth_headers, db):
    from app.core.security import decode_access_token
    from app.models.feedback import SpendingFeedback

    payload = decode_access_token(auth_headers["Authorization"].replace("Bearer ", ""))
    feedback = SpendingFeedback(
        user_id=uuid_module.UUID(payload["sub"]),
        month=4,
        year=2026,
        status="error",
        error_message="Erro inesperado ao gerar feedback",
    )
    db.add(feedback)
    await db.commit()

    response = await client.get("/feedback", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()[0]["error_message"] == "Erro inesperado ao gerar feedback"


@pytest.mark.anyio
async def test_list_feedbacks_with_data(client, auth_headers, db):
    await _upload_with_tx(client, db, auth_headers)

    with patch("app.routers.feedback.generate_spending_feedback") as mock_task:
        mock_task.delay.return_value = None
        gen = await client.post("/feedback/generate", json={"month": 4, "year": 2026}, headers=auth_headers)

    await process_spending_feedback(db, gen.json()["feedback_id"], analyzer=lambda transactions: MOCK_ANALYSIS)

    response = await client.get("/feedback", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["month"] == 4
    assert data[0]["year"] == 2026


@pytest.mark.anyio
async def test_get_feedback_not_found(client, auth_headers):
    response = await client.get(
        "/feedback/00000000-0000-0000-0000-000000000000",
        headers=auth_headers,
    )
    assert response.status_code == 404


@pytest.mark.anyio
async def test_get_feedback_success(client, auth_headers, db):
    await _upload_with_tx(client, db, auth_headers)

    with patch("app.routers.feedback.generate_spending_feedback") as mock_task:
        mock_task.delay.return_value = None
        gen = await client.post("/feedback/generate", json={"month": 4, "year": 2026}, headers=auth_headers)

    await process_spending_feedback(db, gen.json()["feedback_id"], analyzer=lambda transactions: MOCK_ANALYSIS)

    feedback_id = gen.json()["feedback_id"]
    response = await client.get(f"/feedback/{feedback_id}", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == feedback_id
    assert data["summary"] == MOCK_ANALYSIS["summary"]
    assert data["highlights"] == MOCK_ANALYSIS["highlights"]
    assert data["total_potential_saving"] == 80.0
    assert data["saving_opportunities"][0]["confidence"] == "medium"


@pytest.mark.anyio
async def test_delete_feedback_success(client, auth_headers, db):
    await _upload_with_tx(client, db, auth_headers)

    with patch("app.routers.feedback.generate_spending_feedback") as mock_task:
        mock_task.delay.return_value = None
        gen = await client.post("/feedback/generate", json={"month": 4, "year": 2026}, headers=auth_headers)

    await process_spending_feedback(db, gen.json()["feedback_id"], analyzer=lambda transactions: MOCK_ANALYSIS)

    feedback_id = gen.json()["feedback_id"]
    delete_resp = await client.delete(f"/feedback/{feedback_id}", headers=auth_headers)
    assert delete_resp.status_code == 204

    get_resp = await client.get(f"/feedback/{feedback_id}", headers=auth_headers)
    assert get_resp.status_code == 404


@pytest.mark.anyio
async def test_delete_feedback_not_found(client, auth_headers):
    response = await client.delete(
        "/feedback/00000000-0000-0000-0000-000000000000",
        headers=auth_headers,
    )
    assert response.status_code == 404


@pytest.mark.anyio
async def test_cannot_access_other_user_feedback(client, db):
    """Usuário B não pode acessar feedback do usuário A."""
    email_a = f"fb_a_{uuid_module.uuid4().hex[:8]}@example.com"
    email_b = f"fb_b_{uuid_module.uuid4().hex[:8]}@example.com"

    reg_a = await client.post("/auth/register", json={"email": email_a, "password": "12345678"})
    client.cookies.clear()  # prevent user_a cookie from being overwritten by user_b below
    reg_b = await client.post("/auth/register", json={"email": email_b, "password": "12345678"})
    client.cookies.clear()  # clear accumulated cookies; auth uses only Bearer headers below
    headers_a = {"Authorization": f"Bearer {reg_a.json()['access_token']}"}
    headers_b = {"Authorization": f"Bearer {reg_b.json()['access_token']}"}

    await _upload_with_tx(client, db, headers_a, pdf_bytes=b"%PDF-a")

    with patch("app.routers.feedback.generate_spending_feedback") as mock_task:
        mock_task.delay.return_value = None
        gen = await client.post("/feedback/generate", json={"month": 4, "year": 2026}, headers=headers_a)

    await process_spending_feedback(db, gen.json()["feedback_id"], analyzer=lambda transactions: MOCK_ANALYSIS)

    feedback_id = gen.json()["feedback_id"]
    response = await client.get(f"/feedback/{feedback_id}", headers=headers_b)
    assert response.status_code == 404
