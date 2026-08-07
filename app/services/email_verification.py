from __future__ import annotations

import secrets
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import hash_password, verify_password
from app.models.auth import EmailVerificationCode, User
from app.services.email import send_email_verification_code


class EmailVerificationError(ValueError):
    pass


class EmailVerificationCooldownError(EmailVerificationError):
    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__("Aguarde antes de solicitar um novo codigo")
        self.retry_after_seconds = retry_after_seconds


def generate_verification_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


async def create_and_send_verification_code(
    db: AsyncSession,
    user: User,
    *,
    enforce_cooldown: bool = False,
) -> EmailVerificationCode:
    if user.email_verified_at is not None:
        raise EmailVerificationError("Email ja verificado")

    now = datetime.utcnow()
    latest = await _get_latest_code(db, user)
    if enforce_cooldown and latest is not None:
        retry_after = _retry_after_seconds(latest.created_at, now)
        if retry_after > 0:
            raise EmailVerificationCooldownError(retry_after)

    await _consume_active_codes(db, user, now)

    code = generate_verification_code()
    verification = EmailVerificationCode(
        user_id=user.id,
        sent_to_email=user.email,
        code_hash=hash_password(code),
        expires_at=now + timedelta(minutes=settings.EMAIL_VERIFICATION_EXPIRES_MINUTES),
    )
    db.add(verification)
    await db.flush()
    await send_email_verification_code(user.email, code)
    return verification


async def verify_email_code(db: AsyncSession, user: User, code: str) -> None:
    if user.email_verified_at is not None:
        return

    verification = await _get_active_code(db, user)
    if verification is None:
        raise EmailVerificationError("Codigo invalido ou expirado")

    now = datetime.utcnow()
    if verification.expires_at <= now:
        verification.consumed_at = now
        raise EmailVerificationError("Codigo expirado")

    if verification.attempt_count >= settings.EMAIL_VERIFICATION_MAX_ATTEMPTS:
        verification.consumed_at = now
        raise EmailVerificationError("Limite de tentativas excedido")

    if not verify_password(code, verification.code_hash):
        verification.attempt_count += 1
        raise EmailVerificationError("Codigo invalido")

    verification.consumed_at = now
    user.email_verified_at = now


async def _get_latest_code(db: AsyncSession, user: User) -> EmailVerificationCode | None:
    result = await db.execute(
        select(EmailVerificationCode)
        .where(EmailVerificationCode.user_id == user.id)
        .order_by(EmailVerificationCode.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _get_active_code(db: AsyncSession, user: User) -> EmailVerificationCode | None:
    result = await db.execute(
        select(EmailVerificationCode)
        .where(
            EmailVerificationCode.user_id == user.id,
            EmailVerificationCode.sent_to_email == user.email,
            EmailVerificationCode.consumed_at.is_(None),
        )
        .order_by(EmailVerificationCode.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _consume_active_codes(db: AsyncSession, user: User, consumed_at: datetime) -> None:
    result = await db.execute(
        select(EmailVerificationCode).where(
            EmailVerificationCode.user_id == user.id,
            EmailVerificationCode.consumed_at.is_(None),
        )
    )
    for code in result.scalars().all():
        code.consumed_at = consumed_at


def _retry_after_seconds(created_at: datetime, now: datetime) -> int:
    cooldown_until = created_at + timedelta(seconds=settings.EMAIL_VERIFICATION_RESEND_COOLDOWN_SECONDS)
    remaining = cooldown_until - now
    return max(0, int(remaining.total_seconds()))
