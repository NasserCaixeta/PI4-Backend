import pytest


@pytest.mark.anyio
async def test_list_transactions_empty(client, auth_headers):
    response = await client.get("/transactions", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0


@pytest.mark.anyio
async def test_list_transactions_with_filters(client, auth_headers):
    # Without data, filters should still work and return empty
    response = await client.get(
        "/transactions",
        params={"month": 4, "year": 2026, "type": "debit"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []


@pytest.mark.anyio
async def test_cannot_access_other_user_transaction(client, auth_headers):
    # Try to access a non-existent transaction (simulates other user's)
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = await client.get(f"/transactions/{fake_id}", headers=auth_headers)
    assert response.status_code == 404


@pytest.mark.anyio
async def test_update_transaction_not_found(client, auth_headers):
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = await client.patch(
        f"/transactions/{fake_id}",
        json={"description": "Updated"},
        headers=auth_headers,
    )
    assert response.status_code == 404


@pytest.mark.anyio
async def test_delete_transaction_not_found(client, auth_headers):
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = await client.delete(f"/transactions/{fake_id}", headers=auth_headers)
    assert response.status_code == 404


@pytest.mark.anyio
async def test_update_transaction_success(client, auth_headers):
    from unittest.mock import patch

    with patch("app.routers.statements.extract_transactions") as mock_extract:
        mock_extract.return_value = {
            "statement_type": "credit_card",
            "transactions": [
                {"date": "2026-04-01", "description": "Compra Original", "amount": 50, "type": "debit", "category": "Outros"}
            ],
        }
        await client.post(
            "/statements/upload",
            files={"file": ("extrato.pdf", b"%PDF-txupdate", "application/pdf")},
            headers=auth_headers,
        )

    txs = await client.get("/transactions", headers=auth_headers)
    tx_id = txs.json()["items"][0]["id"]

    cats = await client.get("/categories", headers=auth_headers)
    alimentacao_id = next(c["id"] for c in cats.json() if c["name"] == "Alimentação")

    response = await client.patch(
        f"/transactions/{tx_id}",
        json={"category_id": alimentacao_id, "description": "Compra Atualizada"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["description"] == "Compra Atualizada"
    assert data["category"]["name"] == "Alimentação"


@pytest.mark.anyio
async def test_update_transaction_rejects_unknown_category(client, auth_headers):
    from unittest.mock import patch

    with patch("app.routers.statements.extract_transactions") as mock_extract:
        mock_extract.return_value = {
            "statement_type": "credit_card",
            "transactions": [
                {
                    "date": "2026-04-01",
                    "description": "Compra Original",
                    "amount": 50,
                    "type": "debit",
                    "category": "Outros",
                }
            ],
        }
        await client.post(
            "/statements/upload",
            files={"file": ("extrato_invalid_category.pdf", b"%PDF-invalid-category", "application/pdf")},
            headers=auth_headers,
        )

    txs = await client.get("/transactions", headers=auth_headers)
    tx_id = txs.json()["items"][0]["id"]

    response = await client.patch(
        f"/transactions/{tx_id}",
        json={"category_id": "00000000-0000-0000-0000-000000000000"},
        headers=auth_headers,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Categoria não encontrada"


@pytest.mark.anyio
async def test_delete_transaction_success(client, auth_headers):
    from unittest.mock import patch

    with patch("app.routers.statements.extract_transactions") as mock_extract:
        mock_extract.return_value = {
            "statement_type": "credit_card",
            "transactions": [
                {"date": "2026-05-01", "description": "Para Deletar", "amount": 30, "type": "debit", "category": "Outros"}
            ],
        }
        await client.post(
            "/statements/upload",
            files={"file": ("extrato2.pdf", b"%PDF-txdelete", "application/pdf")},
            headers=auth_headers,
        )

    txs = await client.get("/transactions", headers=auth_headers)
    tx_id = txs.json()["items"][0]["id"]

    delete_resp = await client.delete(f"/transactions/{tx_id}", headers=auth_headers)
    assert delete_resp.status_code == 204

    get_resp = await client.get(f"/transactions/{tx_id}", headers=auth_headers)
    assert get_resp.status_code == 404


@pytest.mark.anyio
async def test_list_transactions_pagination(client, auth_headers):
    from unittest.mock import patch

    transactions = [
        {"date": f"2026-06-{str(i).zfill(2)}", "description": f"TX {i}", "amount": i * 10, "type": "debit", "category": "Outros"}
        for i in range(1, 8)
    ]
    with patch("app.routers.statements.extract_transactions") as mock_extract:
        mock_extract.return_value = {"statement_type": "credit_card", "transactions": transactions}
        await client.post(
            "/statements/upload",
            files={"file": ("extrato_pg.pdf", b"%PDF-pagination", "application/pdf")},
            headers=auth_headers,
        )

    page1 = await client.get("/transactions", params={"limit": 3, "offset": 0}, headers=auth_headers)
    page2 = await client.get("/transactions", params={"limit": 3, "offset": 3}, headers=auth_headers)
    data1 = page1.json()
    data2 = page2.json()

    assert data1["total"] >= 7
    assert len(data1["items"]) == 3
    assert len(data2["items"]) == 3
    ids_page1 = {t["id"] for t in data1["items"]}
    ids_page2 = {t["id"] for t in data2["items"]}
    assert ids_page1.isdisjoint(ids_page2)
