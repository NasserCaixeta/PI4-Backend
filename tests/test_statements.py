import pytest
from unittest.mock import MagicMock, patch


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
    with patch("app.routers.statements.process_statement") as mock_task:
        mock_task.delay = MagicMock()

        response = await client.post(
            "/statements/upload",
            files={"file": ("extrato.pdf", b"%PDF-fake", "application/pdf")},
            headers=auth_headers,
        )

        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "processing"
        assert data["filename"] == "extrato.pdf"
        mock_task.delay.assert_called_once()


@pytest.mark.anyio
async def test_upload_increments_free_usage(client, db):
    import uuid as uuid_module

    with patch("app.routers.statements.process_statement") as mock_task:
        mock_task.delay = MagicMock()

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
    from app.models.auth import FreeUsage

    free_usage = FreeUsage(user_id=uuid_module.UUID(user_id), analyses_used=3)
    db.add(free_usage)
    await db.commit()

    with patch("app.routers.statements.process_statement"):
        response = await client.post(
            "/statements/upload",
            files={"file": ("extrato.pdf", b"%PDF-fake", "application/pdf")},
            headers=headers,
        )
        assert response.status_code == 402


@pytest.mark.anyio
async def test_list_statements_empty(client, auth_headers):
    response = await client.get("/statements", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.anyio
async def test_list_statements_with_data(client, auth_headers):
    with patch("app.routers.statements.process_statement") as mock_task:
        mock_task.delay = MagicMock()

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
    with patch("app.routers.statements.process_statement") as mock_task:
        mock_task.delay = MagicMock()

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
