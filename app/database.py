import ssl as _ssl
import urllib.parse as _urlparse
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


class Base(DeclarativeBase):
    pass


_connect_args: dict = {}
_url = settings.async_database_url

# Only enable SSL for asyncpg if explicitly requested via URL params
_requires_ssl = False
if "asyncpg" in _url:
    _parsed = _urlparse.urlparse(_url)
    _q = _urlparse.parse_qs(_parsed.query)
    _sslmode = (_q.get("sslmode") or [""])[0].lower()
    _sslflag = (_q.get("ssl") or [""])[0].lower()
    if _sslmode in {"require", "verify-full", "verify-ca"} or _sslflag in {"1", "true", "yes"}:
        _requires_ssl = True

if _requires_ssl:
    _ssl_ctx = _ssl.create_default_context()
    # Allow connection even if the provider doesn't offer a verifiable cert chain
    _ssl_ctx.check_hostname = False
    _ssl_ctx.verify_mode = _ssl.CERT_NONE
    _connect_args = {"ssl": _ssl_ctx}

engine = create_async_engine(settings.async_database_url, echo=False, connect_args=_connect_args)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        yield session


DEFAULT_CATEGORIES = [
    {"name": "Alimentação", "color": "#FF6B6B", "icon": "utensils"},
    {"name": "Moradia", "color": "#4ECDC4", "icon": "home"},
    {"name": "Transporte", "color": "#45B7D1", "icon": "car"},
    {"name": "Lazer", "color": "#96CEB4", "icon": "gamepad"},
    {"name": "Saúde", "color": "#DDA0DD", "icon": "heart-pulse"},
    {"name": "Compras", "color": "#F59E0B", "icon": "shopping-bag"},
    {"name": "Assinaturas", "color": "#8B5CF6", "icon": "repeat"},
    {"name": "Educação", "color": "#3B82F6", "icon": "graduation-cap"},
    {"name": "Serviços", "color": "#10B981", "icon": "wrench"},
    {"name": "Transferências", "color": "#64748B", "icon": "arrow-left-right"},
    {"name": "Outros", "color": "#95A5A6", "icon": "ellipsis"},
]


async def seed_default_categories():
    from sqlalchemy import select
    from app.models.statements import Category

    async with async_session() as db:
        for cat_data in DEFAULT_CATEGORIES:
            result = await db.execute(
                select(Category).where(
                    Category.name == cat_data["name"],
                    Category.user_id.is_(None)
                )
            )
            if not result.scalar_one_or_none():
                db.add(Category(
                    name=cat_data["name"],
                    color=cat_data["color"],
                    icon=cat_data["icon"],
                    is_default=True,
                    user_id=None,
                ))
        await db.commit()
