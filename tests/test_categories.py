import pytest


@pytest.mark.anyio
async def test_list_categories_returns_defaults(client, auth_headers):
    response = await client.get("/categories", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 11
    names = [c["name"] for c in data]
    assert "Alimentação" in names
    assert "Compras" in names
    assert "Assinaturas" in names
    assert "Transferências" in names
    assert "Outros" in names


@pytest.mark.anyio
async def test_cannot_create_custom_category(client, auth_headers):
    response = await client.post(
        "/categories",
        json={"name": "Investimentos", "color": "#FFD700", "icon": "chart-line"},
        headers=auth_headers,
    )
    assert response.status_code == 405


@pytest.mark.anyio
async def test_cannot_edit_category(client, auth_headers):
    # Get a default category
    list_response = await client.get("/categories", headers=auth_headers)
    default_cat = next(c for c in list_response.json() if c["is_default"])

    response = await client.patch(
        f"/categories/{default_cat['id']}",
        json={"name": "Renamed"},
        headers=auth_headers,
    )
    assert response.status_code == 404


@pytest.mark.anyio
async def test_cannot_delete_category(client, auth_headers):
    list_response = await client.get("/categories", headers=auth_headers)
    default_cat = next(c for c in list_response.json() if c["is_default"])

    response = await client.delete(
        f"/categories/{default_cat['id']}",
        headers=auth_headers,
    )
    assert response.status_code == 404
