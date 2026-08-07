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

    APP_ENV: str = "development"

    JWT_SECRET: str | None = None
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_DAYS: int = 7

    BCRYPT_ROUNDS: int = 12

    GEMINI_API_KEY: str | None = None
    STRIPE_SECRET_KEY: str | None = None
    STRIPE_WEBHOOK_SECRET: str | None = None
    STRIPE_SUPER_PRICE_ID: str | None = None
    STRIPE_MASTER_PRICE_ID: str | None = None
    FRONTEND_URL: str = "http://localhost:5173"
    ALLOWED_ORIGINS: list[str] = []
    RESEND_API_KEY: str | None = None

    EMAIL_PROVIDER: str = "console"
    BREVO_API_KEY: str | None = None
    EMAIL_FROM: str | None = None
    EMAIL_VERIFICATION_EXPIRES_MINUTES: int = 15
    EMAIL_VERIFICATION_RESEND_COOLDOWN_SECONDS: int = 60
    EMAIL_VERIFICATION_MAX_ATTEMPTS: int = 5
    REQUIRE_EMAIL_VERIFICATION: bool = True

    DATA_ENCRYPTION_KEY: str | None = None
    DATA_ENCRYPTION_KEY_ID: str | None = None

    # Redis/Celery
    REDIS_URL: str = "redis://localhost:6379/0"

    # Gemini
    GEMINI_MODEL: str = "gemini-1.5-flash"

    # Paywall
    FREE_ANALYSES_LIMIT: int = 3
    SUPER_ANALYSES_LIMIT: int = 20

    model_config = SettingsConfigDict(env_file=".env")

    @property
    def jwt_secret(self) -> str:
        if self.JWT_SECRET:
            return self.JWT_SECRET
        if self.APP_ENV == "production":
            raise RuntimeError("JWT_SECRET must be configured in production")
        warnings.warn("Using development JWT_SECRET fallback - não use em produção")
        return "camelbox-development-jwt-secret"

    @property
    def data_encryption_key(self) -> str:
        if self.DATA_ENCRYPTION_KEY:
            return self.DATA_ENCRYPTION_KEY
        if self.APP_ENV == "production":
            raise RuntimeError("DATA_ENCRYPTION_KEY must be configured in production")
        warnings.warn("Using development DATA_ENCRYPTION_KEY fallback - não use em produção")
        return "GOvrw75tCz_k_-TZ8vHUQQBqtZp-ze8o-WEA3ZgE6mE="


settings = Settings()
