from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


class Base(DeclarativeBase):
    pass


engine = create_async_engine(settings.DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        yield session


from sqlalchemy.dialects.sqlite import insert as sqlite_insert


DEFAULT_CATEGORIES = [
    {"name": "Alimentação", "color": "#FF6B6B", "icon": "utensils"},
    {"name": "Moradia", "color": "#4ECDC4", "icon": "home"},
    {"name": "Transporte", "color": "#45B7D1", "icon": "car"},
    {"name": "Lazer", "color": "#96CEB4", "icon": "gamepad"},
    {"name": "Saúde", "color": "#DDA0DD", "icon": "heart-pulse"},
    {"name": "Outros", "color": "#95A5A6", "icon": "ellipsis"},
]


async def seed_default_categories():
    from sqlalchemy import select
    from app.models.statements import Category

    async with async_session() as db:
        for cat_data in DEFAULT_CATEGORIES:
            # Check if default category already exists (user_id IS NULL)
            result = await db.execute(
                select(Category).where(
                    Category.name == cat_data["name"],
                    Category.user_id.is_(None)
                )
            )
            existing = result.scalar_one_or_none()

            if not existing:
                stmt = sqlite_insert(Category).values(
                    name=cat_data["name"],
                    color=cat_data["color"],
                    icon=cat_data["icon"],
                    is_default=True,
                    user_id=None,
                )
                await db.execute(stmt)
        await db.commit()
