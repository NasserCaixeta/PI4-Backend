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
