# Camelbox Backend — Sub-projeto 1: Foundation

## Resumo

Setup inicial do projeto Camelbox com estrutura de pastas, configuração, models SQLAlchemy, schemas Pydantic, migration inicial com seed de categorias, módulo de security (JWT + bcrypt), endpoint de health check e estrutura de testes.

## Decisões de Design

| Decisão | Escolha |
|---------|---------|
| Gerenciador de dependências | uv |
| Estrutura de arquivos | Agrupado por domínio |
| Migrations | Uma única migration inicial |
| Seed de categorias | Via migration |
| Variáveis de ambiente | `.env.example` commitado |
| Validação de config | Permissiva com defaults em dev |
| Testes | Incluídos no Foundation |
| Servidor de dev | Script no pyproject.toml (`uv run dev`) |

## Estrutura de Arquivos

```
pi4-backend/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── database.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   └── security.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── statements.py
│   │   └── payments.py
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── common.py
│   │   ├── auth.py
│   │   ├── statements.py
│   │   └── payments.py
│   └── routers/
│       ├── __init__.py
│       └── health.py
├── alembic/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       └── 001_initial_schema.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   └── test_health.py
├── pyproject.toml
├── alembic.ini
├── .env.example
├── .gitignore
└── README.md
```

## Configuração (`core/config.py`)

```python
class Settings(BaseSettings):
    # Obrigatórios
    DATABASE_URL: str

    # Obrigatórios em produção, geram valor random em dev com warning
    JWT_SECRET: str | None = None

    # Opcionais (usados em sub-projetos futuros)
    GEMINI_API_KEY: str | None = None
    STRIPE_SECRET_KEY: str | None = None
    STRIPE_WEBHOOK_SECRET: str | None = None
    RESEND_API_KEY: str | None = None

    # Configurações JWT
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_DAYS: int = 30

    # Configurações bcrypt
    BCRYPT_ROUNDS: int = 12

    _cached_jwt_secret: str | None = None

    @property
    def jwt_secret(self) -> str:
        if self.JWT_SECRET:
            return self.JWT_SECRET
        if self._cached_jwt_secret is None:
            import warnings
            warnings.warn("Using random JWT_SECRET - não use em produção")
            self._cached_jwt_secret = str(uuid.uuid4())
        return self._cached_jwt_secret

    model_config = ConfigDict(env_file=".env")
```

Comportamento:
- `DATABASE_URL` é obrigatório — app falha no startup se não existir
- `JWT_SECRET` gera UUID random em dev se não existir (com warning)
- Demais chaves ficam `None` até os sub-projetos que as usam

## Database (`database.py`)

```python
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

engine = create_async_engine(settings.DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        yield session
```

- `DATABASE_URL` deve usar o scheme `postgresql+asyncpg://`
- `expire_on_commit=False` evita lazy loading acidental após commit

## Models

### `models/auth.py` — User, FreeUsage

```python
class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String(255))
    avatar_url: Mapped[str | None] = mapped_column(Text)
    auth_provider: Mapped[str | None] = mapped_column(String(50))  # 'google' | 'email'
    password_hash: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=func.now())

    # Relationships
    statements: Mapped[list["BankStatement"]] = relationship(back_populates="user")
    categories: Mapped[list["Category"]] = relationship(back_populates="user")
    subscription: Mapped["Subscription | None"] = relationship(back_populates="user")
    free_usage: Mapped["FreeUsage | None"] = relationship(back_populates="user")

class FreeUsage(Base):
    __tablename__ = "free_usage"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), unique=True)
    analyses_used: Mapped[int] = mapped_column(default=0)
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship(back_populates="free_usage")
```

### `models/statements.py` — BankStatement, Transaction, Category

```python
class BankStatement(Base):
    __tablename__ = "bank_statements"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    filename: Mapped[str | None] = mapped_column(String(255))
    file_size_kb: Mapped[int | None]
    status: Mapped[str] = mapped_column(String(20), default="reading")
    uploaded_at: Mapped[datetime] = mapped_column(default=func.now())
    processed_at: Mapped[datetime | None]

    user: Mapped["User"] = relationship(back_populates="statements")
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="statement")

class Category(Base):
    __tablename__ = "categories"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    color: Mapped[str | None] = mapped_column(String(7))
    icon: Mapped[str | None] = mapped_column(String(50))
    is_default: Mapped[bool] = mapped_column(default=False)

    user: Mapped["User | None"] = relationship(back_populates="categories")
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="category")

class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    statement_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bank_statements.id", ondelete="CASCADE"))
    category_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("categories.id"))
    date: Mapped[date] = mapped_column(nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    type: Mapped[str] = mapped_column(String(10))  # 'credit' | 'debit'

    statement: Mapped["BankStatement"] = relationship(back_populates="transactions")
    category: Mapped["Category | None"] = relationship(back_populates="transactions")
```

### `models/payments.py` — Subscription

```python
class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), unique=True)
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255))
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20))  # 'active' | 'canceled' | 'past_due'
    current_period_end: Mapped[datetime | None]

    user: Mapped["User"] = relationship(back_populates="subscription")
```

## Migration Inicial (`001_initial_schema.py`)

A migration:

1. Cria todas as tabelas na ordem correta (respeitando FKs):
   - `users`
   - `free_usage`
   - `categories`
   - `bank_statements`
   - `transactions`
   - `subscriptions`

2. Insere as categorias padrão do sistema:
   ```sql
   INSERT INTO categories (id, user_id, name, color, icon, is_default) VALUES
   (gen_random_uuid(), NULL, 'Alimentação', '#FF6B6B', 'utensils', true),
   (gen_random_uuid(), NULL, 'Moradia', '#4ECDC4', 'home', true),
   (gen_random_uuid(), NULL, 'Transporte', '#45B7D1', 'car', true),
   (gen_random_uuid(), NULL, 'Lazer', '#96CEB4', 'gamepad', true),
   (gen_random_uuid(), NULL, 'Saúde', '#FFEAA7', 'heart-pulse', true),
   (gen_random_uuid(), NULL, 'Outros', '#DFE6E9', 'ellipsis', true);
   ```

3. Cria índices:
   - `idx_transactions_statement_id` em `transactions.statement_id`
   - `idx_bank_statements_user_id` em `bank_statements.user_id`
   - `idx_categories_user_id` em `categories.user_id`

## Security (`core/security.py`)

```python
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=settings.BCRYPT_ROUNDS)).decode()

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
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        return None
```

- `jti` incluído para permitir invalidação no logout (implementado no sub-projeto Auth)
- Funções puras, sem dependência de banco

## Schemas

### `schemas/common.py`

```python
class ErrorResponse(BaseModel):
    error: str
    code: str

class HealthResponse(BaseModel):
    status: str  # "healthy" | "unhealthy"
    database: str  # "connected" | "disconnected"
```

### `schemas/auth.py`

```python
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

### `schemas/statements.py`

```python
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

### `schemas/payments.py`

```python
class SubscriptionResponse(BaseModel):
    id: uuid.UUID
    status: str
    current_period_end: datetime | None

    model_config = ConfigDict(from_attributes=True)
```

## Health Router (`routers/health.py`)

```python
@router.get("/health", response_model=HealthResponse)
async def health_check(db: AsyncSession = Depends(get_db)) -> HealthResponse:
    try:
        await db.execute(text("SELECT 1"))
        return HealthResponse(status="healthy", database="connected")
    except Exception:
        return HealthResponse(status="unhealthy", database="disconnected")
```

## Main (`main.py`)

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: valida conexão com banco
    async with engine.begin() as conn:
        await conn.execute(text("SELECT 1"))
    yield
    # Shutdown: dispose do engine
    await engine.dispose()

app = FastAPI(
    title="Camelbox API",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(health_router, tags=["Health"])
```

## Testes

### `tests/conftest.py`

```python
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.main import app
from app.database import Base, get_db
from app.core.config import settings

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

### `tests/test_health.py`

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

## Arquivos de Configuração

### `pyproject.toml`

```toml
[project]
name = "camelbox-backend"
version = "0.1.0"
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
```

### `.env.example`

```env
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/camelbox
JWT_SECRET=sua-chave-secreta-aqui

# Configurados nos próximos sub-projetos
# GEMINI_API_KEY=
# STRIPE_SECRET_KEY=
# STRIPE_WEBHOOK_SECRET=
# RESEND_API_KEY=
```

### `.gitignore`

```
.env
__pycache__/
*.pyc
.pytest_cache/
.venv/
*.egg-info/
```

## Próximos Sub-projetos

1. **Auth** — JWT, Google OAuth, email/senha, recuperação de senha
2. **PDF Pipeline** — upload, extração, Gemini, categorização
3. **Payments** — Stripe, webhooks, paywall, free_usage
