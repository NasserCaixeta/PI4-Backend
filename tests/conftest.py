from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base, get_db
from app.main import app

# SQLite em memória para testes (não requer PostgreSQL)
test_engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    echo=False,
    connect_args={"check_same_thread": False},
)
test_session = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="session")
async def setup_database():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # Seed default categories for tests
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


@pytest.fixture
async def db(setup_database) -> AsyncGenerator[AsyncSession, None]:
    async with test_session() as session:
        yield session
        await session.rollback()


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
