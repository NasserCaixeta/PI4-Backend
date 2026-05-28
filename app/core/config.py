import uuid
import warnings
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite+aiosqlite:///./dev.db"

    @property
    def async_database_url(self) -> str:
        url = self.DATABASE_URL
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        return url

    JWT_SECRET: str | None = None
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_DAYS: int = 30

    BCRYPT_ROUNDS: int = 12

    GEMINI_API_KEY: str | None = None
    STRIPE_SECRET_KEY: str | None = None
    STRIPE_WEBHOOK_SECRET: str | None = None
    STRIPE_SUPER_PRICE_ID: str | None = None
    STRIPE_MASTER_PRICE_ID: str | None = None
    FRONTEND_URL: str = "http://localhost:5173"
    RESEND_API_KEY: str | None = None

    # Redis/Celery
    REDIS_URL: str = "redis://localhost:6379/0"

    # Gemini
    GEMINI_MODEL: str = "gemini-1.5-flash"

    # Paywall
    FREE_ANALYSES_LIMIT: int = 3
    SUPER_ANALYSES_LIMIT: int = 20

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
