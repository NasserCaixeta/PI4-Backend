import uuid
import warnings
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite+aiosqlite:///./dev.db"

    JWT_SECRET: str | None = None
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_DAYS: int = 30

    BCRYPT_ROUNDS: int = 12

    GEMINI_API_KEY: str | None = None
    STRIPE_SECRET_KEY: str | None = None
    STRIPE_WEBHOOK_SECRET: str | None = None
    RESEND_API_KEY: str | None = None

    # Redis/Celery
    REDIS_URL: str = "redis://localhost:6379/0"

    # Gemini
    GEMINI_MODEL: str = "gemini-1.5-flash"

    # Paywall
    FREE_ANALYSES_LIMIT: int = 3

    model_config = SettingsConfigDict(env_file=".env")

    _cached_jwt_secret: str | None = None

    @property
    def jwt_secret(self) -> str:
        if self.JWT_SECRET:
            return self.JWT_SECRET
        if self._cached_jwt_secret is None:
            warnings.warn("Using random JWT_SECRET - não use em produção")
            self._cached_jwt_secret = str(uuid.uuid4())
        return self._cached_jwt_secret


settings = Settings()
