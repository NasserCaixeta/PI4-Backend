import pytest

from app.core.config import Settings


def test_jwt_secret_uses_configured_value():
    settings = Settings(JWT_SECRET="configured-secret")

    assert settings.jwt_secret == "configured-secret"


def test_jwt_secret_is_stable_outside_production_when_missing():
    settings = Settings(APP_ENV="development", JWT_SECRET=None)

    first = settings.jwt_secret
    second = settings.jwt_secret

    assert first == "camelbox-development-jwt-secret"
    assert second == "camelbox-development-jwt-secret"


def test_jwt_secret_requires_configured_value_in_production():
    settings = Settings(APP_ENV="production", JWT_SECRET=None)

    with pytest.raises(RuntimeError, match="JWT_SECRET must be configured in production"):
        _ = settings.jwt_secret
