from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.database import engine, seed_default_categories
from app.routers.auth import router as auth_router
from app.routers.categories import router as categories_router
from app.routers.dashboard import router as dashboard_router
from app.routers.health import router as health_router
from app.routers.statements import router as statements_router
from app.routers.transactions import router as transactions_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.execute(text("SELECT 1"))
    await seed_default_categories()
    yield
    await engine.dispose()


app = FastAPI(
    title="Camelbox API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, tags=["Health"])
app.include_router(auth_router)
app.include_router(categories_router)
app.include_router(dashboard_router)
app.include_router(statements_router)
app.include_router(transactions_router)
