import pytest
from unittest.mock import patch


@pytest.mark.anyio
async def test_upload_requires_auth(client):
    response = await client.post("/statements/upload")
    assert response.status_code == 401


@pytest.mark.anyio
async def test_upload_requires_pdf(client, auth_headers):
    response = await client.post(
        "/statements/upload",
        files={"file": ("test.txt", b"not a pdf", "text/plain")},
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert "PDF" in response.json()["detail"]


@pytest.mark.anyio
async def test_upload_success(client, auth_headers):
    with patch("app.routers.statements.extract_transactions") as mock_extract:
        mock_extract.return_value = {
            "statement_type": "credit_card",
            "transactions": [
                {
                    "date": "2026-04-10",
                    "description": "Fisia Nike Ecommer - Parcela 1/4",
                    "amount": 100,
                    "type": "debit",
                    "category": "Outros",
                }
            ],
        }
        response = await client.post(
            "/statements/upload",
            files={"file": ("extrato.pdf", b"%PDF-fake", "application/pdf")},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["filename"] == "extrato.pdf"
        assert data["statement_type"] == "credit_card"
        mock_extract.assert_called_once()

        detail_response = await client.get(f"/statements/{data['id']}", headers=auth_headers)
        assert detail_response.status_code == 200
        assert detail_response.json()["transactions"][0]["category"]["name"] == "Compras"


@pytest.mark.anyio
async def test_upload_increments_free_usage(client, db):
    import uuid as uuid_module

    with patch("app.routers.statements.extract_transactions") as mock_extract:
        mock_extract.return_value = {"statement_type": "credit_card", "transactions": []}
        # Registra usuário único para este teste
        unique_email = f"free_usage_{uuid_module.uuid4().hex[:8]}@example.com"
        reg_response = await client.post("/auth/register", json={
            "email": unique_email,
            "password": "12345678",
        })
        token = reg_response.json()["access_token"]
        user_id = reg_response.json()["user"]["id"]
        headers = {"Authorization": f"Bearer {token}"}

        # Primeiro upload
        await client.post(
            "/statements/upload",
            files={"file": ("extrato1.pdf", b"%PDF-fake", "application/pdf")},
            headers=headers,
        )

        # Verifica que free_usage foi criado e incrementado
        from sqlalchemy import select
        from app.models.auth import FreeUsage

        result = await db.execute(
            select(FreeUsage).where(FreeUsage.user_id == uuid_module.UUID(user_id))
        )
        free_usage = result.scalar_one_or_none()
        assert free_usage is not None
        assert free_usage.analyses_used == 1


@pytest.mark.anyio
async def test_upload_paywall_limit(client, db):
    import uuid as uuid_module

    # Registra usuário com email único
    unique_email = f"paywall_{uuid_module.uuid4().hex[:8]}@example.com"
    reg_response = await client.post("/auth/register", json={
        "email": unique_email,
        "password": "12345678",
    })
    token = reg_response.json()["access_token"]
    user_id = reg_response.json()["user"]["id"]
    headers = {"Authorization": f"Bearer {token}"}

    # Cria FreeUsage com limite esgotado
    from app.core.config import settings
    from app.models.auth import FreeUsage

    free_usage = FreeUsage(user_id=uuid_module.UUID(user_id), analyses_used=settings.FREE_ANALYSES_LIMIT)
    db.add(free_usage)
    await db.commit()

    with patch("app.routers.statements.extract_transactions") as mock_extract:
        mock_extract.return_value = {"statement_type": "credit_card", "transactions": []}
        response = await client.post(
            "/statements/upload",
            files={"file": ("extrato.pdf", b"%PDF-fake", "application/pdf")},
            headers=headers,
        )
        assert response.status_code == 402


@pytest.mark.anyio
async def test_upload_super_plan_limit(client, db, monkeypatch):
    import uuid as uuid_module

    monkeypatch.setattr("app.services.billing.settings.SUPER_ANALYSES_LIMIT", 1)
    unique_email = f"super_{uuid_module.uuid4().hex[:8]}@example.com"
    reg_response = await client.post("/auth/register", json={
        "email": unique_email,
        "password": "12345678",
    })
    token = reg_response.json()["access_token"]
    user_id = reg_response.json()["user"]["id"]
    headers = {"Authorization": f"Bearer {token}"}

    from app.models.payments import Subscription

    db.add(Subscription(user_id=uuid_module.UUID(user_id), status="active", plan="super", analyses_used=1))
    await db.commit()

    with patch("app.routers.statements.extract_transactions") as mock_extract:
        mock_extract.return_value = {"statement_type": "credit_card", "transactions": []}
        response = await client.post(
            "/statements/upload",
            files={"file": ("extrato.pdf", b"%PDF-super", "application/pdf")},
            headers=headers,
        )
        assert response.status_code == 402


@pytest.mark.anyio
async def test_upload_master_plan_unlimited(client, db):
    import uuid as uuid_module

    unique_email = f"master_{uuid_module.uuid4().hex[:8]}@example.com"
    reg_response = await client.post("/auth/register", json={
        "email": unique_email,
        "password": "12345678",
    })
    token = reg_response.json()["access_token"]
    user_id = reg_response.json()["user"]["id"]
    headers = {"Authorization": f"Bearer {token}"}

    from app.models.payments import Subscription

    db.add(Subscription(user_id=uuid_module.UUID(user_id), status="active", plan="master", analyses_used=999))
    await db.commit()

    with patch("app.routers.statements.extract_transactions") as mock_extract:
        mock_extract.return_value = {"statement_type": "credit_card", "transactions": []}
        response = await client.post(
            "/statements/upload",
            files={"file": ("extrato.pdf", b"%PDF-master", "application/pdf")},
            headers=headers,
        )
        assert response.status_code == 200


@pytest.mark.anyio
async def test_list_statements_empty(client, auth_headers):
    response = await client.get("/statements", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.anyio
async def test_list_statements_with_data(client, auth_headers):
    with patch("app.routers.statements.extract_transactions") as mock_extract:
        mock_extract.return_value = {"statement_type": "credit_card", "transactions": []}
        # Upload um statement
        await client.post(
            "/statements/upload",
            files={"file": ("extrato.pdf", b"%PDF-fake", "application/pdf")},
            headers=auth_headers,
        )

        # Lista statements
        response = await client.get("/statements", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["filename"] == "extrato.pdf"


@pytest.mark.anyio
async def test_get_statement_not_found(client, auth_headers):
    response = await client.get(
        "/statements/00000000-0000-0000-0000-000000000000",
        headers=auth_headers,
    )
    assert response.status_code == 404


@pytest.mark.anyio
async def test_get_statement_success(client, auth_headers):
    with patch("app.routers.statements.extract_transactions") as mock_extract:
        mock_extract.return_value = {"statement_type": "credit_card", "transactions": []}
        # Upload
        upload_response = await client.post(
            "/statements/upload",
            files={"file": ("extrato.pdf", b"%PDF-fake", "application/pdf")},
            headers=auth_headers,
        )
        statement_id = upload_response.json()["id"]

        # Get
        response = await client.get(f"/statements/{statement_id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == statement_id
        assert data["filename"] == "extrato.pdf"


@pytest.mark.anyio
async def test_upload_duplicate_returns_conflict(client, auth_headers):
    with patch("app.routers.statements.extract_transactions") as mock_extract:
        mock_extract.return_value = {"statement_type": "credit_card", "transactions": []}
        await client.post(
            "/statements/upload",
            files={"file": ("extrato.pdf", b"%PDF-duplicate", "application/pdf")},
            headers=auth_headers,
        )

        response = await client.post(
            "/statements/upload",
            files={"file": ("renomeado.pdf", b"%PDF-duplicate", "application/pdf")},
            headers=auth_headers,
        )

        assert response.status_code == 409


@pytest.mark.anyio
async def test_delete_month_removes_only_selected_month(client, auth_headers):
    with patch("app.routers.statements.extract_transactions") as mock_extract:
        mock_extract.return_value = {
            "statement_type": "bank_account",
            "transactions": [
                {
                    "date": "2026-04-10",
                    "description": "Abril",
                    "amount": 100,
                    "type": "debit",
                    "category": "Outros",
                },
                {
                    "date": "2026-05-10",
                    "description": "Maio",
                    "amount": 200,
                    "type": "debit",
                    "category": "Outros",
                },
            ],
        }
        await client.post(
            "/statements/upload",
            files={"file": ("extrato.pdf", b"%PDF-months", "application/pdf")},
            headers=auth_headers,
        )

    response = await client.delete(
        "/statements/month",
        params={"month": 4, "year": 2026},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["deleted_transactions"] == 1

    april = await client.get(
        "/transactions",
        params={"month": 4, "year": 2026},
        headers=auth_headers,
    )
    may = await client.get(
        "/transactions",
        params={"month": 5, "year": 2026},
        headers=auth_headers,
    )
    assert april.json()["total"] == 0
    assert may.json()["total"] == 1
