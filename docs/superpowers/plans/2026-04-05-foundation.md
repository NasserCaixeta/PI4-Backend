# Camelbox Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Setup the complete foundation for the Camelbox backend with FastAPI, SQLAlchemy async, all models, schemas, security module, health endpoint, and tests.

**Architecture:** FastAPI with async SQLAlchemy 2.0 using asyncpg. Models grouped by domain (auth, statements, payments). Single Alembic migration with seed data. TDD approach with pytest-anyio.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy 2.0 (async), asyncpg, Pydantic v2, Alembic, bcrypt, python-jose, pytest, httpx, uv

---

## File Structure

```
pi4-backend/
├── app/
│   ├── __init__.py              # Empty, marks package
│   ├── main.py                  # FastAPI app, lifespan, router includes
│   ├── database.py              # Base, engine, async_session, get_db
│   ├── core/
│   │   ├── __init__.py          # Empty
│   │   ├── config.py            # Settings with pydantic-settings
│   │   └── security.py          # JWT and bcrypt functions
│   ├── models/
│   │   ├── __init__.py          # Re-exports all models
│   │   ├── auth.py              # User, FreeUsage
│   │   ├── statements.py        # BankStatement, Category, Transaction
│   │   └── payments.py          # Subscription
│   ├── schemas/
│   │   ├── __init__.py          # Empty
│   │   ├── common.py            # ErrorResponse, HealthResponse
│   │   ├── auth.py              # UserCreate, UserResponse, TokenData
│   │   ├── statements.py        # CategoryResponse, TransactionResponse, StatementResponse
│   │   └── payments.py          # SubscriptionResponse
│   └── routers/
│       ├── __init__.py          # Empty
│       └── health.py            # GET /health endpoint
├── alembic/
│   ├── env.py                   # Async alembic config
│   ├── script.py.mako           # Migration template
│   └── versions/
│       └── 001_initial_schema.py
├── tests/
│   ├── __init__.py              # Empty
│   ├── conftest.py              # Fixtures: db, client
│   └── test_health.py           # Health endpoint test
├── pyproject.toml               # Dependencies and scripts
├── alembic.ini                  # Alembic config
├── .env.example                 # Environment template
├── .gitignore                   # Git ignores
└── README.md                    # Project readme
```

---

## Task 1: Project Setup

**Files:**
- Create: `pyproject.toml`
- Create: `.env.example`
- Create: `.gitignore`
- Create: `README.md`

- [ ] **Step 1: Create pyproject.toml**

Create file `pyproject.toml`:

```toml
[project]
name = "camelbox-backend"
version = "0.1.0"
description = "Backend API for Camelbox - Financial Analysis SaaS"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.110.0",
    "uvicorn[standard]>=0.27.0",
    "sqlalchemy[asyncio]>=2.0.0",
    "asyncpg>=0.29.0",
    "pydantic[email]>=2.0.0",
    "pydantic-settings>=2.0.0",
    "python-jose[cryptography]>=3.3.0",
    "bcrypt>=4.1.0",
    "alembic>=1.13.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-anyio>=0.0.0",
    "httpx>=0.27.0",
]

[project.scripts]
dev = "uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **Step 2: Create .env.example**

Create file `.env.example`:

```env
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/camelbox
JWT_SECRET=sua-chave-secreta-aqui

# Configurados nos próximos sub-projetos
# GEMINI_API_KEY=
# STRIPE_SECRET_KEY=
# STRIPE_WEBHOOK_SECRET=
# RESEND_API_KEY=
```

- [ ] **Step 3: Create .gitignore**

Create file `.gitignore`:

```
.env
__pycache__/
*.pyc
.pytest_cache/
.venv/
*.egg-info/
.ruff_cache/
```

- [ ] **Step 4: Create README.md**

Create file `README.md`:

```markdown
# Camelbox Backend

Backend API for Camelbox - Financial Analysis SaaS.

## Setup

1. Copy `.env.example` to `.env` and configure
2. Install dependencies: `uv sync --all-extras`
3. Run migrations: `uv run alembic upgrade head`
4. Start server: `uv run dev`

## Development

- Run tests: `uv run pytest`
- Create migration: `uv run alembic revision --autogenerate -m "description"`
```

- [ ] **Step 5: Install dependencies**

```bash
cd /home/dministrador/dev/work/pi4-backend
uv sync --all-extras
```

Expected: Dependencies installed successfully

---

## Task 2: Core Configuration

**Files:**
- Create: `app/__init__.py`
- Create: `app/core/__init__.py`
- Create: `app/core/config.py`

- [ ] **Step 1: Create app package**

```bash
mkdir -p /home/dministrador/dev/work/pi4-backend/app/core
```

- [ ] **Step 2: Create app/__init__.py**

Create file `app/__init__.py`:

```python
```

(Empty file)

- [ ] **Step 3: Create app/core/__init__.py**

Create file `app/core/__init__.py`:

```python
```

(Empty file)

- [ ] **Step 4: Create app/core/config.py**

Create file `app/core/config.py`:

```python
import uuid
import warnings
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str

    JWT_SECRET: str | None = None
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_DAYS: int = 30

    BCRYPT_ROUNDS: int = 12

    GEMINI_API_KEY: str | None = None
    STRIPE_SECRET_KEY: str | None = None
    STRIPE_WEBHOOK_SECRET: str | None = None
    RESEND_API_KEY: str | None = None

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
```

---

## Task 3: Database Setup

**Files:**
- Create: `app/database.py`

- [ ] **Step 1: Create app/database.py**

Create file `app/database.py`:

```python
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
```

---

## Task 4: Auth Models (User, FreeUsage)

**Files:**
- Create: `app/models/__init__.py`
- Create: `app/models/auth.py`

- [ ] **Step 1: Create models package**

```bash
mkdir -p /home/dministrador/dev/work/pi4-backend/app/models
```

- [ ] **Step 2: Create app/models/auth.py**

Create file `app/models/auth.py`:

```python
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.payments import Subscription
    from app.models.statements import BankStatement, Category


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String(255))
    avatar_url: Mapped[str | None] = mapped_column(Text)
    auth_provider: Mapped[str | None] = mapped_column(String(50))
    password_hash: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=func.now())

    statements: Mapped[list[BankStatement]] = relationship(back_populates="user")
    categories: Mapped[list[Category]] = relationship(back_populates="user")
    subscription: Mapped[Subscription | None] = relationship(back_populates="user")
    free_usage: Mapped[FreeUsage | None] = relationship(back_populates="user")


class FreeUsage(Base):
    __tablename__ = "free_usage"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), unique=True)
    analyses_used: Mapped[int] = mapped_column(default=0)
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())

    user: Mapped[User] = relationship(back_populates="free_usage")
```

---

## Task 5: Statements Models (BankStatement, Category, Transaction)

**Files:**
- Create: `app/models/statements.py`

- [ ] **Step 1: Create app/models/statements.py**

Create file `app/models/statements.py`:

```python
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.auth import User


class BankStatement(Base):
    __tablename__ = "bank_statements"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    filename: Mapped[str | None] = mapped_column(String(255))
    file_size_kb: Mapped[int | None]
    status: Mapped[str] = mapped_column(String(20), default="reading")
    uploaded_at: Mapped[datetime] = mapped_column(default=func.now())
    processed_at: Mapped[datetime | None]

    user: Mapped[User] = relationship(back_populates="statements")
    transactions: Mapped[list[Transaction]] = relationship(back_populates="statement")


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    color: Mapped[str | None] = mapped_column(String(7))
    icon: Mapped[str | None] = mapped_column(String(50))
    is_default: Mapped[bool] = mapped_column(default=False)

    user: Mapped[User | None] = relationship(back_populates="categories")
    transactions: Mapped[list[Transaction]] = relationship(back_populates="category")


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    statement_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bank_statements.id", ondelete="CASCADE"))
    category_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("categories.id"))
    date: Mapped[date] = mapped_column(nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    type: Mapped[str] = mapped_column(String(10))

    statement: Mapped[BankStatement] = relationship(back_populates="transactions")
    category: Mapped[Category | None] = relationship(back_populates="transactions")
```

---

## Task 6: Payments Model (Subscription)

**Files:**
- Create: `app/models/payments.py`

- [ ] **Step 1: Create app/models/payments.py**

Create file `app/models/payments.py`:

```python
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.auth import User


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), unique=True)
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255))
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20))
    current_period_end: Mapped[datetime | None]

    user: Mapped[User] = relationship(back_populates="subscription")
```

- [ ] **Step 2: Create app/models/__init__.py**

Create file `app/models/__init__.py`:

```python
from app.models.auth import FreeUsage, User
from app.models.payments import Subscription
from app.models.statements import BankStatement, Category, Transaction

__all__ = [
    "User",
    "FreeUsage",
    "BankStatement",
    "Category",
    "Transaction",
    "Subscription",
]
```

---

## Task 7: Alembic Setup and Initial Migration

**Files:**
- Create: `alembic.ini`
- Create: `alembic/env.py`
- Create: `alembic/script.py.mako`
- Create: `alembic/versions/001_initial_schema.py`

- [ ] **Step 1: Create alembic directory**

```bash
mkdir -p /home/dministrador/dev/work/pi4-backend/alembic/versions
```

- [ ] **Step 2: Create alembic.ini**

Create file `alembic.ini`:

```ini
[alembic]
script_location = alembic
prepend_sys_path = .
version_path_separator = os

[post_write_hooks]

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

- [ ] **Step 3: Create alembic/env.py**

Create file `alembic/env.py`:

```python
import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.core.config import settings
from app.database import Base
from app.models import *  # noqa: F401, F403

config = context.config
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 4: Create alembic/script.py.mako**

Create file `alembic/script.py.mako`:

```mako
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

# revision identifiers, used by Alembic.
revision: str = ${repr(up_revision)}
down_revision: Union[str, None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

- [ ] **Step 5: Create initial migration**

Create file `alembic/versions/001_initial_schema.py`:

```python
"""Initial schema with all tables and seed data

Revision ID: 001
Revises:
Create Date: 2026-04-05

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Users table
    op.create_table(
        "users",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("avatar_url", sa.Text(), nullable=True),
        sa.Column("auth_provider", sa.String(50), nullable=True),
        sa.Column("password_hash", sa.Text(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )

    # Free usage table
    op.create_table(
        "free_usage",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("analyses_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )

    # Categories table
    op.create_table(
        "categories",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("color", sa.String(7), nullable=True),
        sa.Column("icon", sa.String(50), nullable=True),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default="false"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_categories_user_id", "categories", ["user_id"])

    # Bank statements table
    op.create_table(
        "bank_statements",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("filename", sa.String(255), nullable=True),
        sa.Column("file_size_kb", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="reading"),
        sa.Column("uploaded_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("processed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_bank_statements_user_id", "bank_statements", ["user_id"])

    # Transactions table
    op.create_table(
        "transactions",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("statement_id", sa.UUID(), nullable=False),
        sa.Column("category_id", sa.UUID(), nullable=True),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("type", sa.String(10), nullable=False),
        sa.ForeignKeyConstraint(["statement_id"], ["bank_statements.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_transactions_statement_id", "transactions", ["statement_id"])

    # Subscriptions table
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("stripe_customer_id", sa.String(255), nullable=True),
        sa.Column("stripe_subscription_id", sa.String(255), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("current_period_end", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )

    # Seed default categories
    op.execute("""
        INSERT INTO categories (id, user_id, name, color, icon, is_default) VALUES
        (gen_random_uuid(), NULL, 'Alimentação', '#FF6B6B', 'utensils', true),
        (gen_random_uuid(), NULL, 'Moradia', '#4ECDC4', 'home', true),
        (gen_random_uuid(), NULL, 'Transporte', '#45B7D1', 'car', true),
        (gen_random_uuid(), NULL, 'Lazer', '#96CEB4', 'gamepad', true),
        (gen_random_uuid(), NULL, 'Saúde', '#FFEAA7', 'heart-pulse', true),
        (gen_random_uuid(), NULL, 'Outros', '#DFE6E9', 'ellipsis', true);
    """)


def downgrade() -> None:
    op.drop_table("subscriptions")
    op.drop_index("idx_transactions_statement_id", table_name="transactions")
    op.drop_table("transactions")
    op.drop_index("idx_bank_statements_user_id", table_name="bank_statements")
    op.drop_table("bank_statements")
    op.drop_index("idx_categories_user_id", table_name="categories")
    op.drop_table("categories")
    op.drop_table("free_usage")
    op.drop_table("users")
```

---

## Task 8: Security Module

**Files:**
- Create: `app/core/security.py`

- [ ] **Step 1: Create app/core/security.py**

Create file `app/core/security.py`:

```python
import uuid
from datetime import datetime, timedelta

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(
        password.encode(), bcrypt.gensalt(rounds=settings.BCRYPT_ROUNDS)
    ).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def create_access_token(user_id: uuid.UUID) -> str:
    payload = {
        "sub": str(user_id),
        "jti": str(uuid.uuid4()),
        "exp": datetime.utcnow() + timedelta(days=settings.JWT_EXPIRATION_DAYS),
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    try:
        return jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.JWT_ALGORITHM]
        )
    except JWTError:
        return None
```

---

## Task 9: Pydantic Schemas

**Files:**
- Create: `app/schemas/__init__.py`
- Create: `app/schemas/common.py`
- Create: `app/schemas/auth.py`
- Create: `app/schemas/statements.py`
- Create: `app/schemas/payments.py`

- [ ] **Step 1: Create schemas package**

```bash
mkdir -p /home/dministrador/dev/work/pi4-backend/app/schemas
```

- [ ] **Step 2: Create app/schemas/__init__.py**

Create file `app/schemas/__init__.py`:

```python
```

(Empty file)

- [ ] **Step 3: Create app/schemas/common.py**

Create file `app/schemas/common.py`:

```python
from pydantic import BaseModel


class ErrorResponse(BaseModel):
    error: str
    code: str


class HealthResponse(BaseModel):
    status: str
    database: str
```

- [ ] **Step 4: Create app/schemas/auth.py**

Create file `app/schemas/auth.py`:

```python
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    name: str | None = None


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    name: str | None
    avatar_url: str | None
    auth_provider: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TokenData(BaseModel):
    user_id: uuid.UUID
    jti: str
```

- [ ] **Step 5: Create app/schemas/statements.py**

Create file `app/schemas/statements.py`:

```python
import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class CategoryResponse(BaseModel):
    id: uuid.UUID
    name: str
    color: str | None
    icon: str | None
    is_default: bool

    model_config = ConfigDict(from_attributes=True)


class TransactionResponse(BaseModel):
    id: uuid.UUID
    date: date
    description: str | None
    amount: Decimal
    type: str
    category: CategoryResponse | None

    model_config = ConfigDict(from_attributes=True)


class StatementResponse(BaseModel):
    id: uuid.UUID
    filename: str | None
    file_size_kb: int | None
    status: str
    uploaded_at: datetime
    processed_at: datetime | None
    transactions: list[TransactionResponse] = []

    model_config = ConfigDict(from_attributes=True)
```

- [ ] **Step 6: Create app/schemas/payments.py**

Create file `app/schemas/payments.py`:

```python
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SubscriptionResponse(BaseModel):
    id: uuid.UUID
    status: str
    current_period_end: datetime | None

    model_config = ConfigDict(from_attributes=True)
```

---

## Task 10: Health Router

**Files:**
- Create: `app/routers/__init__.py`
- Create: `app/routers/health.py`

- [ ] **Step 1: Create routers package**

```bash
mkdir -p /home/dministrador/dev/work/pi4-backend/app/routers
```

- [ ] **Step 2: Create app/routers/__init__.py**

Create file `app/routers/__init__.py`:

```python
```

(Empty file)

- [ ] **Step 3: Create app/routers/health.py**

Create file `app/routers/health.py`:

```python
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.common import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check(db: AsyncSession = Depends(get_db)) -> HealthResponse:
    try:
        await db.execute(text("SELECT 1"))
        return HealthResponse(status="healthy", database="connected")
    except Exception:
        return HealthResponse(status="unhealthy", database="disconnected")
```

---

## Task 11: FastAPI Main Application

**Files:**
- Create: `app/main.py`

- [ ] **Step 1: Create app/main.py**

Create file `app/main.py`:

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from app.database import engine
from app.routers.health import router as health_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.execute(text("SELECT 1"))
    yield
    await engine.dispose()


app = FastAPI(
    title="Camelbox API",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(health_router, tags=["Health"])
```

---

## Task 12: Test Setup and Health Test

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `tests/test_health.py`

- [ ] **Step 1: Create tests package**

```bash
mkdir -p /home/dministrador/dev/work/pi4-backend/tests
```

- [ ] **Step 2: Create tests/__init__.py**

Create file `tests/__init__.py`:

```python
```

(Empty file)

- [ ] **Step 3: Create tests/conftest.py**

Create file `tests/conftest.py`:

```python
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.database import Base, get_db
from app.main import app

test_engine = create_async_engine(settings.DATABASE_URL, echo=False)
test_session = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="session")
async def setup_database():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def db(setup_database) -> AsyncGenerator[AsyncSession, None]:
    async with test_session() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def client(db: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
```

- [ ] **Step 4: Create tests/test_health.py**

Create file `tests/test_health.py`:

```python
import pytest


@pytest.mark.anyio
async def test_health_check_returns_healthy(client):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"
```

- [ ] **Step 5: Run tests to verify setup**

```bash
cd /home/dministrador/dev/work/pi4-backend
uv run pytest tests/ -v
```

Expected: `1 passed`

---

## Task 13: Final Verification

**Files:** None (verification only)

- [ ] **Step 1: Verify project structure**

```bash
find /home/dministrador/dev/work/pi4-backend -type f -name "*.py" | head -20
```

Expected: All Python files listed

- [ ] **Step 2: Run all tests**

```bash
cd /home/dministrador/dev/work/pi4-backend
uv run pytest tests/ -v
```

Expected: All tests pass

- [ ] **Step 3: Verify app starts (requires .env and database)**

Create `.env` from `.env.example` with valid DATABASE_URL, then:

```bash
cd /home/dministrador/dev/work/pi4-backend
timeout 5 uv run dev || true
```

Expected: Server starts (or timeout after 5 seconds confirming startup)
