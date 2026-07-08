import uuid as uuid_module
from unittest.mock import patch

import pytest

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


async def _upload_with_tx(client, headers, date_str="2026-04-10"):
    """Helper: faz upload mockado com uma transação."""
    with patch("app.routers.statements.extract_transactions") as mock:
        mock.return_value = {
            "statement_type": "credit_card",
            "transactions": [
                {"date": date_str, "description": "Mercado", "amount": 100, "type": "debit", "category": "Alimentação"}
            ],
        }
        await client.post(
            "/statements/upload",
            files={"file": ("extrato.pdf", b"%PDF-feedback", "application/pdf")},
            headers=headers,
        )


@pytest.mark.anyio
async def test_generate_feedback_requires_auth(client):
    response = await client.post("/feedback/generate", json={"month": 4, "year": 2026})
    assert response.status_code == 401


@pytest.mark.anyio
async def test_generate_feedback_success(client, auth_headers):
    await _upload_with_tx(client, auth_headers)

    with patch("app.routers.feedback.generate_spending_analysis", return_value=MOCK_ANALYSIS):
        response = await client.post(
            "/feedback/generate",
            json={"month": 4, "year": 2026},
            headers=auth_headers,
        )

    assert response.status_code == 201
    data = response.json()
    assert "feedback_id" in data
    assert data["status"] == "completed"


@pytest.mark.anyio
async def test_generate_feedback_duplicate_returns_conflict(client, auth_headers):
    await _upload_with_tx(client, auth_headers)

    with patch("app.routers.feedback.generate_spending_analysis", return_value=MOCK_ANALYSIS):
        await client.post("/feedback/generate", json={"month": 4, "year": 2026}, headers=auth_headers)
        response = await client.post("/feedback/generate", json={"month": 4, "year": 2026}, headers=auth_headers)

    assert response.status_code == 409


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
async def test_generate_feedback_does_not_consume_usage_when_analysis_fails(client, db):
    unique_email = f"fb_fail_{uuid_module.uuid4().hex[:8]}@example.com"
    reg = await client.post("/auth/register", json={"email": unique_email, "password": "12345678"})
    token = reg.json()["access_token"]
    user_id = reg.json()["user"]["id"]
    headers = {"Authorization": f"Bearer {token}"}

    await _upload_with_tx(client, headers)

    with patch("app.routers.feedback.generate_spending_analysis", side_effect=ValueError("analysis failed")):
        response = await client.post("/feedback/generate", json={"month": 4, "year": 2026}, headers=headers)

    assert response.status_code == 201
    assert response.json()["status"] == "error"

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
async def test_list_feedbacks_with_data(client, auth_headers):
    await _upload_with_tx(client, auth_headers)

    with patch("app.routers.feedback.generate_spending_analysis", return_value=MOCK_ANALYSIS):
        await client.post("/feedback/generate", json={"month": 4, "year": 2026}, headers=auth_headers)

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
async def test_get_feedback_success(client, auth_headers):
    await _upload_with_tx(client, auth_headers)

    with patch("app.routers.feedback.generate_spending_analysis", return_value=MOCK_ANALYSIS):
        gen = await client.post("/feedback/generate", json={"month": 4, "year": 2026}, headers=auth_headers)

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
async def test_delete_feedback_success(client, auth_headers):
    await _upload_with_tx(client, auth_headers)

    with patch("app.routers.feedback.generate_spending_analysis", return_value=MOCK_ANALYSIS):
        gen = await client.post("/feedback/generate", json={"month": 4, "year": 2026}, headers=auth_headers)

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

    with patch("app.routers.statements.extract_transactions") as mock_s:
        mock_s.return_value = {
            "statement_type": "credit_card",
            "transactions": [{"date": "2026-04-10", "description": "X", "amount": 10, "type": "debit", "category": "Outros"}],
        }
        await client.post("/statements/upload", files={"file": ("e.pdf", b"%PDF-a", "application/pdf")}, headers=headers_a)

    with patch("app.routers.feedback.generate_spending_analysis", return_value=MOCK_ANALYSIS):
        gen = await client.post("/feedback/generate", json={"month": 4, "year": 2026}, headers=headers_a)

    feedback_id = gen.json()["feedback_id"]
    response = await client.get(f"/feedback/{feedback_id}", headers=headers_b)
    assert response.status_code == 404
