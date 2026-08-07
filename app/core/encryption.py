from __future__ import annotations

from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


class DecryptionError(Exception):
    """Raised when encrypted application data cannot be decrypted."""


@lru_cache(maxsize=1)
def _fernet() -> Fernet:
    return Fernet(settings.data_encryption_key.encode("ascii"))


def clear_encryption_cache() -> None:
    _fernet.cache_clear()


def encrypt_text(value: str | None) -> str | None:
    if value is None:
        return None
    return _fernet().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_text(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        return _fernet().decrypt(value.encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise DecryptionError("Could not decrypt sensitive data") from exc
