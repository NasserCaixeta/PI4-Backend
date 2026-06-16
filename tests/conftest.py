from collections.abc import AsyncGenerator
import os

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy import text

# PostgreSQL local (camelbox-pg Docker container)
TEST_DATABASE_URL = "postgresql+asyncpg://camelbox:camelbox@localhost:5432/camelbox_test"
os.environ["DATABASE_URL"] = TEST_DATABASE_URL

from app.database import Base, get_db
from app.main import app

# Disable rate limiters — all test requests share 127.0.0.1, would exceed limits immediately
import app.routers.auth as _auth_mod
import app.routers.statements as _statements_mod
import app.routers.feedback as _feedback_mod


def _noop_rate_check(self, request, endpoint_func=None, in_middleware=False):
    if not hasattr(request.state, "view_rate_limit"):
        request.state.view_rate_limit = (None, None)


for _mod in (_auth_mod, _statements_mod, _feedback_mod):
    _mod.limiter._check_request_limit = _noop_rate_check.__get__(_mod.limiter, type(_mod.limiter))
app.state.limiter._check_request_limit = _noop_rate_check.__get__(app.state.limiter, type(app.state.limiter))

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
test_session = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="session")
async def setup_database():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    # Seed default categories
    from app.database import DEFAULT_CATEGORIES
    from app.models.statements import Category

    async with test_session() as db:
        for cat_data in DEFAULT_CATEGORIES:
            db.add(Category(
                name=cat_data["name"],
                color=cat_data["color"],
                icon=cat_data["icon"],
                is_default=True,
                user_id=None,
            ))
        await db.commit()

    yield

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()


@pytest.fixture
async def db(setup_database) -> AsyncGenerator[AsyncSession, None]:
    """Each test gets its own transaction that is rolled back for isolation.

    join_transaction_mode='create_savepoint' ensures app-level commit() only
    releases a SAVEPOINT instead of committing the outer transaction, so we can
    roll everything back after the test without touching the real DB state.
    """
    conn = await test_engine.connect()
    await conn.begin()
    session = AsyncSession(
        bind=conn,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )

    yield session

    await session.close()
    await conn.rollback()
    await conn.close()


@pytest.fixture
async def client(db: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
async def auth_headers(client, request) -> dict:
    """Registra usuário e retorna headers com token."""
    import uuid
    unique_email = f"test_{uuid.uuid4().hex[:8]}@example.com"
    response = await client.post("/auth/register", json={
        "email": unique_email,
        "password": "12345678",
    })
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
