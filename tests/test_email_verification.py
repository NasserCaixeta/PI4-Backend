from datetime import datetime, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base
from app.core.config import settings
from app.core.dependencies import require_verified_email
from app.models.auth import User
from app.models.auth import EmailVerificationCode
from app.services import email_verification
from app.services.email_verification import EmailVerificationError, generate_verification_code


def test_generate_verification_code_is_six_digits():
    codes = {generate_verification_code() for _ in range(20)}

    assert all(len(code) == 6 for code in codes)
    assert all(code.isdigit() for code in codes)


def test_user_email_verification_property_reflects_verified_timestamp():
    user = User(email="user@example.com")

    assert user.is_email_verified is False

    user.email_verified_at = datetime.utcnow()

    assert user.is_email_verified is True


@pytest.mark.anyio
async def test_verified_email_dependency_blocks_unverified_users(monkeypatch):
    monkeypatch.setattr(settings, "REQUIRE_EMAIL_VERIFICATION", True)
    user = User(email="unverified@example.com")

    with pytest.raises(HTTPException) as exc_info:
        await require_verified_email(user)

    assert exc_info.value.status_code == 403


@pytest.mark.anyio
async def test_verified_email_dependency_can_be_disabled_for_tests(monkeypatch):
    monkeypatch.setattr(settings, "REQUIRE_EMAIL_VERIFICATION", False)
    user = User(email="unverified@example.com")

    assert await require_verified_email(user) is user


@pytest.fixture
async def sqlite_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest.fixture
def capture_verification_code(monkeypatch):
    sent_codes: list[str] = []

    async def fake_send_email_verification_code(email: str, code: str) -> None:
        sent_codes.append(code)

    monkeypatch.setattr(email_verification, "send_email_verification_code", fake_send_email_verification_code)
    monkeypatch.setattr(email_verification.settings, "BCRYPT_ROUNDS", 4)
    monkeypatch.setattr(email_verification.settings, "EMAIL_VERIFICATION_EXPIRES_MINUTES", 15)
    monkeypatch.setattr(email_verification.settings, "EMAIL_VERIFICATION_MAX_ATTEMPTS", 5)
    return sent_codes


@pytest.mark.anyio
async def test_verify_email_code_marks_user_as_verified(sqlite_db, capture_verification_code):
    user = User(email="user@example.com")
    sqlite_db.add(user)
    await sqlite_db.flush()

    await email_verification.create_and_send_verification_code(sqlite_db, user)
    await email_verification.verify_email_code(sqlite_db, user, capture_verification_code[0])

    assert user.is_email_verified is True


@pytest.mark.anyio
async def test_verify_email_code_rejects_wrong_code_and_counts_attempt(sqlite_db, capture_verification_code):
    user = User(email="user@example.com")
    sqlite_db.add(user)
    await sqlite_db.flush()

    await email_verification.create_and_send_verification_code(sqlite_db, user)

    with pytest.raises(EmailVerificationError, match="Codigo invalido"):
        await email_verification.verify_email_code(sqlite_db, user, "000000")

    result = await sqlite_db.execute(select(EmailVerificationCode).where(EmailVerificationCode.user_id == user.id))
    verification = result.scalar_one()
    assert verification.attempt_count == 1
    assert user.is_email_verified is False


@pytest.mark.anyio
async def test_verify_email_code_rejects_expired_code(sqlite_db, capture_verification_code):
    user = User(email="user@example.com")
    sqlite_db.add(user)
    await sqlite_db.flush()

    verification = await email_verification.create_and_send_verification_code(sqlite_db, user)
    verification.expires_at = datetime.utcnow() - timedelta(minutes=1)

    with pytest.raises(EmailVerificationError, match="Codigo expirado"):
        await email_verification.verify_email_code(sqlite_db, user, capture_verification_code[0])

    assert verification.consumed_at is not None
    assert user.is_email_verified is False


@pytest.mark.anyio
async def test_verify_email_code_cannot_be_reused(sqlite_db, capture_verification_code):
    user = User(email="user@example.com")
    sqlite_db.add(user)
    await sqlite_db.flush()

    await email_verification.create_and_send_verification_code(sqlite_db, user)
    await email_verification.verify_email_code(sqlite_db, user, capture_verification_code[0])
    user.email_verified_at = None

    with pytest.raises(EmailVerificationError, match="Codigo invalido ou expirado"):
        await email_verification.verify_email_code(sqlite_db, user, capture_verification_code[0])
