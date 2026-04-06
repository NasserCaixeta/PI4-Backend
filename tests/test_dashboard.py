import pytest


@pytest.mark.anyio
async def test_summary_empty(client, auth_headers):
    response = await client.get("/dashboard/summary", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total_income"] == "0.00"
    assert data["total_expenses"] == "0.00"
    assert data["balance"] == "0.00"
    assert data["transaction_count"] == 0


@pytest.mark.anyio
async def test_by_category_empty(client, auth_headers):
    response = await client.get("/dashboard/by-category", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["categories"] == []


@pytest.mark.anyio
async def test_summary_filter_by_month(client, auth_headers):
    response = await client.get(
        "/dashboard/summary",
        params={"month": 4, "year": 2026},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["period"]["start"] == "2026-04-01"
    assert data["period"]["end"] == "2026-04-30"


@pytest.mark.anyio
async def test_summary_filter_by_date_range(client, auth_headers):
    response = await client.get(
        "/dashboard/summary",
        params={"start_date": "2026-01-01", "end_date": "2026-01-31"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["period"]["start"] == "2026-01-01"
    assert data["period"]["end"] == "2026-01-31"


@pytest.mark.anyio
async def test_summary_has_comparison(client, auth_headers):
    response = await client.get(
        "/dashboard/summary",
        params={"month": 4, "year": 2026},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert "comparison" in data
    assert data["comparison"]["previous_period"]["start"] == "2026-03-02"
    assert data["comparison"]["previous_period"]["end"] == "2026-03-31"
