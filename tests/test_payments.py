from types import SimpleNamespace
from unittest.mock import patch

import pytest


@pytest.mark.anyio
async def test_get_billing_status_free(client, auth_headers):
    from app.core.config import settings

    response = await client.get("/payments/me", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["plan"] == "free"
    assert data["status"] == "free"
    assert data["analyses_used"] == 0
    assert data["analyses_limit"] == settings.FREE_ANALYSES_LIMIT
    assert data["analyses_remaining"] == settings.FREE_ANALYSES_LIMIT


@pytest.mark.anyio
async def test_checkout_requires_valid_plan(client, auth_headers, monkeypatch):
    monkeypatch.setattr("app.routers.payments.settings.STRIPE_SECRET_KEY", "sk_test_fake")

    response = await client.post("/payments/checkout", json={"plan": "invalid"}, headers=auth_headers)

    assert response.status_code == 400


@pytest.mark.anyio
async def test_checkout_creates_stripe_session(client, auth_headers, monkeypatch):
    monkeypatch.setattr("app.routers.payments.settings.STRIPE_SECRET_KEY", "sk_test_fake")
    monkeypatch.setattr("app.routers.payments.settings.STRIPE_SUPER_PRICE_ID", "price_super")
    monkeypatch.setattr("app.routers.payments.settings.FRONTEND_URL", "https://front.test")

    fake_session = SimpleNamespace(url="https://checkout.stripe.test/session")
    with patch("app.routers.payments.stripe.checkout.Session.create", return_value=fake_session) as create_session:
        response = await client.post("/payments/checkout", json={"plan": "super"}, headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["checkout_url"] == "https://checkout.stripe.test/session"
    create_session.assert_called_once()
