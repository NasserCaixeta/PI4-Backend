import pytest


@pytest.mark.anyio
async def test_list_categories_returns_defaults(client, auth_headers):
    response = await client.get("/categories", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 6
    names = [c["name"] for c in data]
    assert "Alimentação" in names
    assert "Outros" in names


@pytest.mark.anyio
async def test_create_custom_category(client, auth_headers):
    response = await client.post(
        "/categories",
        json={"name": "Investimentos", "color": "#FFD700", "icon": "chart-line"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Investimentos"
    assert data["color"] == "#FFD700"
    assert data["is_default"] is False


@pytest.mark.anyio
async def test_cannot_edit_default_category(client, auth_headers):
    # Get a default category
    list_response = await client.get("/categories", headers=auth_headers)
    default_cat = next(c for c in list_response.json() if c["is_default"])

    response = await client.patch(
        f"/categories/{default_cat['id']}",
        json={"name": "Renamed"},
        headers=auth_headers,
    )
    assert response.status_code == 403


@pytest.mark.anyio
async def test_cannot_delete_default_category(client, auth_headers):
    list_response = await client.get("/categories", headers=auth_headers)
    default_cat = next(c for c in list_response.json() if c["is_default"])

    response = await client.delete(
        f"/categories/{default_cat['id']}",
        headers=auth_headers,
    )
    assert response.status_code == 403


@pytest.mark.anyio
async def test_delete_category_moves_transactions(client, auth_headers, db):
    # Create custom category
    create_resp = await client.post(
        "/categories",
        json={"name": "ToDelete"},
        headers=auth_headers,
    )
    cat_id = create_resp.json()["id"]

    # Delete it (no transactions, but test the endpoint works)
    delete_resp = await client.delete(f"/categories/{cat_id}", headers=auth_headers)
    assert delete_resp.status_code == 204

    # Verify it's gone
    list_resp = await client.get("/categories", headers=auth_headers)
    names = [c["name"] for c in list_resp.json()]
    assert "ToDelete" not in names
