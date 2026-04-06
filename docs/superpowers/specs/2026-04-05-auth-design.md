# Camelbox Backend — Sub-projeto 2: Auth

## Resumo

Implementação de autenticação via email/senha com JWT. Três endpoints: register, login e me.

## Decisões de Design

| Decisão | Escolha |
|---------|---------|
| Escopo | Email/senha apenas (Google OAuth depois) |
| Resposta do login | Token no body |
| FreeUsage | Criado sob demanda (não no registro) |
| Dependency de auth | Uma só (`get_current_user`) |
| Validação de senha | Mínimo 8 caracteres |
| Endpoints | register, login, me |

## Estrutura de Arquivos

Arquivos novos/modificados:

```
app/
├── core/
│   └── dependencies.py    # NOVO - get_current_user
├── routers/
│   └── auth.py            # NOVO - endpoints register/login/me
├── schemas/
│   └── auth.py            # MODIFICAR - adicionar TokenResponse, LoginRequest
└── main.py                # MODIFICAR - incluir auth_router
tests/
└── test_auth.py           # NOVO - testes dos endpoints
```

## Schemas (`schemas/auth.py`)

Adicionar ao arquivo existente:

```python
class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
```

Schemas existentes que serão usados:
- `UserCreate` — para registro (email, password, name)
- `UserResponse` — dados do usuário na resposta

## Dependency (`core/dependencies.py`)

```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.database import get_db
from app.models.auth import User

security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    token = credentials.credentials
    payload = decode_access_token(token)

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido ou expirado",
        )

    user_id = payload.get("sub")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário não encontrado",
        )

    return user
```

Comportamento:
- Usa `HTTPBearer` para extrair token do header `Authorization: Bearer <token>`
- Retorna 401 se token inválido ou usuário não existe
- Retorna o objeto `User` do banco

## Router (`routers/auth.py`)

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.core.security import create_access_token, hash_password, verify_password
from app.database import get_db
from app.models.auth import User
from app.schemas.auth import LoginRequest, TokenResponse, UserCreate, UserResponse

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(data: UserCreate, db: AsyncSession = Depends(get_db)):
    # Verifica se email já existe
    result = await db.execute(select(User).where(User.email == data.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email já cadastrado",
        )

    # Cria usuário
    user = User(
        email=data.email,
        password_hash=hash_password(data.password),
        name=data.name,
        auth_provider="email",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    # Gera token e retorna
    token = create_access_token(user.id)
    return TokenResponse(access_token=token, user=UserResponse.model_validate(user))


@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    # Busca usuário
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()

    if not user or not user.password_hash:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou senha inválidos",
        )

    if not verify_password(data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou senha inválidos",
        )

    token = create_access_token(user.id)
    return TokenResponse(access_token=token, user=UserResponse.model_validate(user))


@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)):
    return user
```

### Comportamento dos Endpoints

| Endpoint | Sucesso | Erro |
|----------|---------|------|
| `POST /auth/register` | 201 + token + user | 400 se email duplicado |
| `POST /auth/login` | 200 + token + user | 401 se credenciais inválidas |
| `GET /auth/me` | 200 + user | 401 se não autenticado |

Nota: Login retorna mensagem genérica "Email ou senha inválidos" para não revelar se email existe.

## Modificação no `main.py`

```python
from app.routers.auth import router as auth_router

# ... (código existente)

app.include_router(health_router, tags=["Health"])
app.include_router(auth_router)  # NOVO
```

## Testes (`tests/test_auth.py`)

```python
import pytest


@pytest.mark.anyio
async def test_register_success(client):
    response = await client.post("/auth/register", json={
        "email": "test@example.com",
        "password": "12345678",
        "name": "Test User",
    })
    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "test@example.com"


@pytest.mark.anyio
async def test_register_duplicate_email(client):
    # Primeiro registro
    await client.post("/auth/register", json={
        "email": "duplicate@example.com",
        "password": "12345678",
    })
    # Segundo registro com mesmo email
    response = await client.post("/auth/register", json={
        "email": "duplicate@example.com",
        "password": "87654321",
    })
    assert response.status_code == 400


@pytest.mark.anyio
async def test_login_success(client):
    # Registra usuário
    await client.post("/auth/register", json={
        "email": "login@example.com",
        "password": "12345678",
    })
    # Faz login
    response = await client.post("/auth/login", json={
        "email": "login@example.com",
        "password": "12345678",
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data


@pytest.mark.anyio
async def test_login_wrong_password(client):
    await client.post("/auth/register", json={
        "email": "wrong@example.com",
        "password": "12345678",
    })
    response = await client.post("/auth/login", json={
        "email": "wrong@example.com",
        "password": "wrongpassword",
    })
    assert response.status_code == 401


@pytest.mark.anyio
async def test_me_authenticated(client):
    # Registra e pega token
    reg_response = await client.post("/auth/register", json={
        "email": "me@example.com",
        "password": "12345678",
    })
    token = reg_response.json()["access_token"]

    # Chama /me com token
    response = await client.get("/auth/me", headers={
        "Authorization": f"Bearer {token}",
    })
    assert response.status_code == 200
    assert response.json()["email"] == "me@example.com"


@pytest.mark.anyio
async def test_me_unauthenticated(client):
    response = await client.get("/auth/me")
    assert response.status_code == 403  # HTTPBearer retorna 403 sem header
```

### Cobertura de Testes

| Cenário | Teste |
|---------|-------|
| Register sucesso | `test_register_success` |
| Register email duplicado | `test_register_duplicate_email` |
| Login sucesso | `test_login_success` |
| Login senha errada | `test_login_wrong_password` |
| Me autenticado | `test_me_authenticated` |
| Me não autenticado | `test_me_unauthenticated` |

## Próximos Sub-projetos

1. ~~Foundation~~ ✅
2. ~~Auth~~ ← este
3. **PDF Pipeline** — upload, extração, Gemini, categorização
4. **Payments** — Stripe, webhooks, paywall, free_usage
