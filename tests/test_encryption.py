import pytest
from cryptography.fernet import Fernet

from app.core import encryption
from app.models.statements import BankStatement, Transaction


def _set_encryption_key(monkeypatch, key: str | None, app_env: str = "test") -> None:
    monkeypatch.setattr(encryption.settings, "DATA_ENCRYPTION_KEY", key)
    monkeypatch.setattr(encryption.settings, "APP_ENV", app_env)
    encryption.clear_encryption_cache()


def test_encrypt_text_does_not_contain_plaintext_and_decrypts(monkeypatch):
    _set_encryption_key(monkeypatch, Fernet.generate_key().decode("ascii"))

    encrypted = encryption.encrypt_text("Mercado Particular")

    assert encrypted is not None
    assert "Mercado Particular" not in encrypted
    assert encryption.decrypt_text(encrypted) == "Mercado Particular"


def test_encrypt_and_decrypt_keep_none_as_none(monkeypatch):
    _set_encryption_key(monkeypatch, Fernet.generate_key().decode("ascii"))

    assert encryption.encrypt_text(None) is None
    assert encryption.decrypt_text(None) is None


def test_decrypt_invalid_token_raises_controlled_error(monkeypatch):
    _set_encryption_key(monkeypatch, Fernet.generate_key().decode("ascii"))

    with pytest.raises(encryption.DecryptionError, match="Could not decrypt sensitive data"):
        encryption.decrypt_text("not-a-fernet-token")


def test_encryption_key_fallback_is_rejected_in_production(monkeypatch):
    _set_encryption_key(monkeypatch, None, app_env="production")

    with pytest.raises(RuntimeError, match="DATA_ENCRYPTION_KEY must be configured in production"):
        encryption.encrypt_text("Mercado")


def test_development_fallback_key_can_encrypt_and_decrypt(monkeypatch):
    _set_encryption_key(monkeypatch, None, app_env="development")

    encrypted = encryption.encrypt_text("Mercado")

    assert encrypted is not None
    assert encryption.decrypt_text(encrypted) == "Mercado"


def test_transaction_description_is_stored_encrypted(monkeypatch):
    from datetime import date
    from decimal import Decimal

    _set_encryption_key(monkeypatch, Fernet.generate_key().decode("ascii"))

    transaction = Transaction(
        date=date(2026, 7, 10),
        description="Mercado Particular",
        amount=Decimal("123.45"),
        type="debit",
    )

    assert transaction._description is None
    assert transaction.description_encrypted is not None
    assert "Mercado Particular" not in transaction.description_encrypted
    assert transaction.description == "Mercado Particular"


def test_statement_filename_is_stored_encrypted(monkeypatch):
    _set_encryption_key(monkeypatch, Fernet.generate_key().decode("ascii"))

    statement = BankStatement(filename="fatura-particular.pdf")

    assert statement._filename is None
    assert statement.filename_encrypted is not None
    assert "fatura-particular.pdf" not in statement.filename_encrypted
    assert statement.filename == "fatura-particular.pdf"


def test_transaction_description_update_reencrypts(monkeypatch):
    from datetime import date
    from decimal import Decimal

    _set_encryption_key(monkeypatch, Fernet.generate_key().decode("ascii"))
    transaction = Transaction(
        date=date(2026, 7, 10),
        description="Original",
        amount=Decimal("10"),
        type="debit",
    )
    original_encrypted = transaction.description_encrypted

    transaction.description = "Atualizada"

    assert transaction._description is None
    assert transaction.description == "Atualizada"
    assert transaction.description_encrypted != original_encrypted
    assert "Atualizada" not in transaction.description_encrypted
