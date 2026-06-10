from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy import text
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.database import engine, seed_default_categories
from app.routers.auth import router as auth_router
from app.routers.categories import router as categories_router
from app.routers.dashboard import router as dashboard_router
from app.routers.feedback import router as feedback_router
from app.routers.health import router as health_router
from app.routers.payments import router as payments_router
from app.routers.statements import router as statements_router
from app.routers.transactions import router as transactions_router

limiter = Limiter(key_func=get_remote_address)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        if settings.APP_ENV == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline'; "
                "style-src 'self' 'unsafe-inline'; "
                "font-src 'self' data: https://fonts.gstatic.com; "
                "img-src 'self' data: https:; "
                "connect-src 'self'"
            )
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.execute(text("SELECT 1"))
    await seed_default_categories()
    yield
    await engine.dispose()


_docs_url = None if settings.APP_ENV == "production" else "/docs"
_redoc_url = None if settings.APP_ENV == "production" else "/redoc"

app = FastAPI(
    title="Camelbox API",
    version="0.1.0",
    lifespan=lifespan,
    docs_url=_docs_url,
    redoc_url=_redoc_url,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

_allowed_origins = settings.ALLOWED_ORIGINS if settings.ALLOWED_ORIGINS else [settings.FRONTEND_URL]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

app.add_middleware(SecurityHeadersMiddleware)

app.include_router(health_router, tags=["Health"])
app.include_router(auth_router)
app.include_router(categories_router)
app.include_router(dashboard_router)
app.include_router(feedback_router)
app.include_router(payments_router)
app.include_router(statements_router)
app.include_router(transactions_router)
