import pytest
from httpx import ASGITransport, AsyncClient

from app.database import get_db
from app.main import app


@pytest.mark.anyio
async def test_health_check_returns_healthy(client):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"


@pytest.mark.anyio
async def test_health_check_returns_503_when_database_is_unavailable():
    class FailingSession:
        async def execute(self, *_args, **_kwargs):
            raise RuntimeError("database unavailable")

    async def failing_db():
        yield FailingSession()

    app.dependency_overrides[get_db] = failing_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/health")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {
        "status": "unhealthy",
        "database": "disconnected",
    }
