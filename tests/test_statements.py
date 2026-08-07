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
async def test_upload_invalid_magic_bytes(client, auth_headers):
    """Arquivo com content-type PDF mas conteúdo não é PDF real (magic bytes inválidos)."""
    response = await client.post(
        "/statements/upload",
        files={"file": ("fake.pdf", b"PK\x03\x04fake zip content", "application/pdf")},
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert "inválido" in response.json()["detail"].lower()


@pytest.mark.anyio
async def test_upload_file_too_large(client, auth_headers):
    """Arquivo PDF maior que 10 MB deve ser rejeitado."""
    big_content = b"%PDF-" + b"x" * (10 * 1024 * 1024 + 1)
    response = await client.post(
        "/statements/upload",
        files={"file": ("grande.pdf", big_content, "application/pdf")},
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert "grande" in response.json()["detail"].lower()


@pytest.mark.anyio
async def test_statement_isolation_between_users(client, db):
    """Usuário B não pode acessar statement do usuário A."""
    import uuid as uuid_module

    email_a = f"iso_a_{uuid_module.uuid4().hex[:8]}@example.com"
    email_b = f"iso_b_{uuid_module.uuid4().hex[:8]}@example.com"

    reg_a = await client.post("/auth/register", json={"email": email_a, "password": "12345678"})
    client.cookies.clear()  # prevent user_a cookie from being overwritten by user_b below
    reg_b = await client.post("/auth/register", json={"email": email_b, "password": "12345678"})
    client.cookies.clear()  # clear accumulated cookies; auth uses only Bearer headers below
    headers_a = {"Authorization": f"Bearer {reg_a.json()['access_token']}"}
    headers_b = {"Authorization": f"Bearer {reg_b.json()['access_token']}"}

    with patch("app.routers.statements.process_statement") as mock_task:
        mock_task.delay.return_value = None
        upload = await client.post(
            "/statements/upload",
            files={"file": ("extrato.pdf", b"%PDF-isolation", "application/pdf")},
            headers=headers_a,
        )
    statement_id = upload.json()["id"]

    response = await client.get(f"/statements/{statement_id}", headers=headers_b)
    assert response.status_code == 404


@pytest.mark.anyio
async def test_upload_success_enqueues_processing_job(client, auth_headers):
    with (
        patch("app.routers.statements.process_statement") as mock_task,
        patch("app.services.gemini.extract_transactions") as mock_extract,
    ):
        mock_task.delay.return_value = None
        response = await client.post(
            "/statements/upload",
            files={"file": ("extrato.pdf", b"%PDF-fake", "application/pdf")},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "processing"
        assert data["filename"] == "extrato.pdf"
        assert data["statement_type"] is None
        mock_task.delay.assert_called_once()
        statement_id, pdf_payload = mock_task.delay.call_args.args
        assert statement_id == data["id"]
        assert isinstance(pdf_payload, str)
        mock_extract.assert_not_called()


@pytest.mark.anyio
async def test_upload_does_not_increment_free_usage_until_worker_succeeds(client, db):
    import uuid as uuid_module

    unique_email = f"free_usage_{uuid_module.uuid4().hex[:8]}@example.com"
    reg_response = await client.post("/auth/register", json={
        "email": unique_email,
        "password": "12345678",
    })
    token = reg_response.json()["access_token"]
    user_id = reg_response.json()["user"]["id"]
    headers = {"Authorization": f"Bearer {token}"}

    with patch("app.routers.statements.process_statement") as mock_task:
        mock_task.delay.return_value = None
        response = await client.post(
            "/statements/upload",
            files={"file": ("extrato1.pdf", b"%PDF-fake", "application/pdf")},
            headers=headers,
        )

    assert response.status_code == 200

    from sqlalchemy import select
    from app.models.auth import FreeUsage

    result = await db.execute(
        select(FreeUsage).where(FreeUsage.user_id == uuid_module.UUID(user_id))
    )
    assert result.scalar_one_or_none() is None


@pytest.mark.anyio
async def test_upload_enqueue_failure_marks_statement_error(client, auth_headers):
    with patch("app.routers.statements.process_statement") as mock_task:
        mock_task.delay.side_effect = RuntimeError("redis unavailable")
        response = await client.post(
            "/statements/upload",
            files={"file": ("extrato.pdf", b"%PDF-enqueue-fails", "application/pdf")},
            headers=auth_headers,
    )

    assert response.status_code == 503
    assert "enfileirar" in response.json()["detail"].lower()


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

    with patch("app.routers.statements.process_statement") as mock_task:
        mock_task.delay.return_value = None
        response = await client.post(
            "/statements/upload",
            files={"file": ("extrato.pdf", b"%PDF-paywall", "application/pdf")},
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

    with patch("app.routers.statements.process_statement") as mock_task:
        mock_task.delay.return_value = None
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

    with patch("app.routers.statements.process_statement") as mock_task:
        mock_task.delay.return_value = None
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
    with patch("app.routers.statements.process_statement") as mock_task:
        mock_task.delay.return_value = None
        # Upload um statement
        await client.post(
            "/statements/upload",
            files={"file": ("extrato.pdf", b"%PDF-list-data", "application/pdf")},
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
        mock_task.delay.return_value = None
        # Upload
        upload_response = await client.post(
            "/statements/upload",
            files={"file": ("extrato.pdf", b"%PDF-get-success", "application/pdf")},
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
    with patch("app.routers.statements.process_statement") as mock_task:
        mock_task.delay.return_value = None
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
        assert mock_task.delay.call_count == 1


@pytest.mark.anyio
async def test_upload_allows_retry_after_failed_same_pdf(client, auth_headers):
    with patch("app.routers.statements.process_statement") as mock_task:
        mock_task.delay.side_effect = [
            RuntimeError("redis unavailable"),
            None,
        ]

        failed = await client.post(
            "/statements/upload",
            files={"file": ("extrato.pdf", b"%PDF-retry-after-error", "application/pdf")},
            headers=auth_headers,
        )
        retry = await client.post(
            "/statements/upload",
            files={"file": ("extrato.pdf", b"%PDF-retry-after-error", "application/pdf")},
            headers=auth_headers,
        )

    assert failed.status_code == 503
    assert retry.status_code == 200
    assert retry.json()["status"] == "processing"


@pytest.mark.anyio
async def test_delete_month_removes_only_selected_month(client, auth_headers, db):
    from datetime import date
    from decimal import Decimal
    import uuid

    from app.models.statements import Transaction

    with patch("app.routers.statements.process_statement") as mock_task:
        mock_task.delay.return_value = None
        upload = await client.post(
            "/statements/upload",
            files={"file": ("extrato.pdf", b"%PDF-months", "application/pdf")},
            headers=auth_headers,
        )
    statement_id = uuid.UUID(upload.json()["id"])

    db.add_all(
        [
            Transaction(
                statement_id=statement_id,
                date=date(2026, 4, 10),
                description="Abril",
                amount=Decimal("100"),
                type="debit",
            ),
            Transaction(
                statement_id=statement_id,
                date=date(2026, 5, 10),
                description="Maio",
                amount=Decimal("200"),
                type="debit",
            ),
        ]
    )
    await db.commit()

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
