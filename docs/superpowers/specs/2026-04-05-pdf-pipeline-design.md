# Camelbox Backend — Sub-projeto 3: PDF Pipeline

## Resumo

Implementação do pipeline de processamento de extratos bancários em PDF. Upload assíncrono com Celery, extração e categorização via Google Gemini API, paywall com limite de 3 análises grátis.

## Decisões de Design

| Decisão | Escolha |
|---------|---------|
| Armazenamento PDF | Não armazenar (processa e descarta) |
| Processamento | Assíncrono |
| Worker | Celery com Redis |
| Paywall | Verifica/incrementa no upload |
| Modelo Gemini | gemini-1.5-flash |
| Categorização | Junto com extração (1 chamada) |
| Polling | Via `GET /statements/{id}` |

## Estrutura de Arquivos

```
app/
├── core/
│   └── config.py              # MODIFICAR - adicionar configs Celery/Redis/Gemini
├── routers/
│   └── statements.py          # NOVO - endpoints upload/list/get
├── services/
│   └── gemini.py              # NOVO - cliente Gemini para extração
├── workers/
│   ├── __init__.py
│   ├── celery_app.py          # NOVO - config Celery
│   └── tasks.py               # NOVO - task de processamento
tests/
├── test_statements.py         # NOVO - testes dos endpoints
└── conftest.py                # MODIFICAR - adicionar fixture auth_headers
pyproject.toml                 # MODIFICAR - adicionar dependências
.env.example                   # MODIFICAR - adicionar variáveis
app/main.py                    # MODIFICAR - incluir statements_router
```

## Configuração (`core/config.py`)

Adicionar ao Settings existente:

```python
# Redis/Celery
REDIS_URL: str = "redis://localhost:6379/0"

# Gemini
GEMINI_API_KEY: str | None = None  # já existe
GEMINI_MODEL: str = "gemini-1.5-flash"

# Paywall
FREE_ANALYSES_LIMIT: int = 3
```

## Celery App (`workers/celery_app.py`)

```python
from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "camelbox",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    task_track_started=True,
)
```

## Serviço Gemini (`services/gemini.py`)

```python
import json

import google.generativeai as genai

from app.core.config import settings


def extract_transactions(pdf_bytes: bytes) -> list[dict]:
    """
    Envia PDF para Gemini e retorna lista de transações.

    Retorna:
    [
        {
            "date": "2024-01-15",
            "description": "SUPERMERCADO XYZ",
            "amount": 150.50,
            "type": "debit",
            "category": "Alimentação"
        },
        ...
    ]
    """
    genai.configure(api_key=settings.GEMINI_API_KEY)
    model = genai.GenerativeModel(settings.GEMINI_MODEL)

    prompt = """
    Analise este extrato bancário PDF e extraia todas as transações.
    Para cada transação, retorne:
    - date: data no formato YYYY-MM-DD
    - description: descrição da transação
    - amount: valor absoluto (sempre positivo)
    - type: "credit" para entradas, "debit" para saídas
    - category: uma das categorias: Alimentação, Moradia, Transporte, Lazer, Saúde, Outros

    Retorne APENAS um JSON array, sem markdown ou explicações.
    """

    response = model.generate_content([
        prompt,
        {"mime_type": "application/pdf", "data": pdf_bytes}
    ])

    return json.loads(response.text)
```

Comportamento:
- Recebe bytes do PDF
- Envia para Gemini com prompt estruturado
- Gemini processa o PDF nativamente (não precisa de biblioteca de PDF)
- Retorna lista de dicts com transações já categorizadas
- Categorias mapeiam para as 6 categorias default do sistema

## Task Celery (`workers/tasks.py`)

```python
import asyncio
import base64
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select

from app.database import async_session
from app.models.statements import BankStatement, Category, Transaction
from app.services.gemini import extract_transactions
from app.workers.celery_app import celery_app


@celery_app.task
def process_statement(statement_id: str, pdf_bytes_b64: str):
    """
    Processa o PDF: extrai transações via Gemini e salva no banco.

    Atualiza status:
    - "processing" → "completed" (sucesso)
    - "processing" → "error" (falha)
    """
    pdf_bytes = base64.b64decode(pdf_bytes_b64)

    async def _process():
        async with async_session() as db:
            # Busca statement
            result = await db.execute(
                select(BankStatement).where(BankStatement.id == statement_id)
            )
            statement = result.scalar_one_or_none()
            if not statement:
                return

            try:
                # Extrai transações via Gemini
                transactions_data = extract_transactions(pdf_bytes)

                # Busca categorias default para mapear por nome
                cat_result = await db.execute(
                    select(Category).where(Category.is_default == True)
                )
                categories = {c.name: c.id for c in cat_result.scalars()}

                # Cria transações
                for tx in transactions_data:
                    category_id = categories.get(tx["category"])
                    transaction = Transaction(
                        statement_id=statement.id,
                        date=tx["date"],
                        description=tx["description"],
                        amount=Decimal(str(tx["amount"])),
                        type=tx["type"],
                        category_id=category_id,
                    )
                    db.add(transaction)

                statement.status = "completed"
                statement.processed_at = datetime.utcnow()

            except Exception:
                statement.status = "error"

            await db.commit()

    asyncio.run(_process())
```

Fluxo:
1. Decodifica PDF de base64
2. Chama Gemini para extrair transações
3. Mapeia categorias pelo nome
4. Cria registros de Transaction
5. Atualiza status para "completed" ou "error"

## Router Statements (`routers/statements.py`)

```python
import base64
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.dependencies import get_current_user
from app.database import get_db
from app.models.auth import FreeUsage, User
from app.models.statements import BankStatement
from app.schemas.statements import StatementResponse
from app.workers.tasks import process_statement

router = APIRouter(prefix="/statements", tags=["Statements"])


@router.post("/upload", response_model=StatementResponse, status_code=202)
async def upload_statement(
    file: UploadFile,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Valida tipo de arquivo
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Apenas PDFs são aceitos")

    # Verifica paywall (se não tem assinatura ativa)
    has_subscription = user.subscription and user.subscription.status == "active"

    if not has_subscription:
        # Busca ou cria FreeUsage
        result = await db.execute(
            select(FreeUsage).where(FreeUsage.user_id == user.id)
        )
        free_usage = result.scalar_one_or_none()

        if not free_usage:
            free_usage = FreeUsage(user_id=user.id, analyses_used=0)
            db.add(free_usage)

        if free_usage.analyses_used >= settings.FREE_ANALYSES_LIMIT:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail="Limite de análises gratuitas atingido",
            )

        free_usage.analyses_used += 1

    # Lê arquivo
    pdf_bytes = await file.read()
    file_size_kb = len(pdf_bytes) // 1024

    # Cria statement
    statement = BankStatement(
        user_id=user.id,
        filename=file.filename,
        file_size_kb=file_size_kb,
        status="processing",
    )
    db.add(statement)
    await db.commit()
    await db.refresh(statement)

    # Enfileira task
    pdf_b64 = base64.b64encode(pdf_bytes).decode()
    process_statement.delay(str(statement.id), pdf_b64)

    return statement


@router.get("", response_model=list[StatementResponse])
async def list_statements(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(BankStatement)
        .where(BankStatement.user_id == user.id)
        .order_by(BankStatement.uploaded_at.desc())
    )
    return result.scalars().all()


@router.get("/{statement_id}", response_model=StatementResponse)
async def get_statement(
    statement_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(BankStatement)
        .options(selectinload(BankStatement.transactions))
        .where(BankStatement.id == statement_id, BankStatement.user_id == user.id)
    )
    statement = result.scalar_one_or_none()

    if not statement:
        raise HTTPException(status_code=404, detail="Statement não encontrado")

    return statement
```

### Comportamento dos Endpoints

| Endpoint | Sucesso | Erro |
|----------|---------|------|
| `POST /statements/upload` | 202 + statement com `status="processing"` | 400 se não PDF, 402 se paywall |
| `GET /statements` | 200 + lista de statements (sem transações) | - |
| `GET /statements/{id}` | 200 + statement com transações | 404 se não encontrado |

## Testes (`tests/test_statements.py`)

```python
import pytest
from unittest.mock import patch, MagicMock


@pytest.mark.anyio
async def test_upload_requires_auth(client):
    response = await client.post("/statements/upload")
    assert response.status_code == 401


@pytest.mark.anyio
async def test_upload_requires_pdf(client, auth_headers):
    response = await client.post(
        "/statements/upload",
        files={"file": ("test.txt", b"not a pdf", "text/plain")},
        headers=auth_headers,
    )
    assert response.status_code == 400


@pytest.mark.anyio
async def test_upload_success(client, auth_headers):
    with patch("app.routers.statements.process_statement") as mock_task:
        mock_task.delay = MagicMock()

        response = await client.post(
            "/statements/upload",
            files={"file": ("extrato.pdf", b"%PDF-fake", "application/pdf")},
            headers=auth_headers,
        )

        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "processing"
        assert data["filename"] == "extrato.pdf"
        mock_task.delay.assert_called_once()


@pytest.mark.anyio
async def test_upload_paywall_limit(client, auth_headers_with_exhausted_free_usage):
    with patch("app.routers.statements.process_statement"):
        response = await client.post(
            "/statements/upload",
            files={"file": ("extrato.pdf", b"%PDF-fake", "application/pdf")},
            headers=auth_headers_with_exhausted_free_usage,
        )
        assert response.status_code == 402


@pytest.mark.anyio
async def test_list_statements(client, auth_headers):
    response = await client.get("/statements", headers=auth_headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.anyio
async def test_get_statement_not_found(client, auth_headers):
    response = await client.get(
        "/statements/00000000-0000-0000-0000-000000000000",
        headers=auth_headers,
    )
    assert response.status_code == 404
```

### Fixtures Necessárias (`conftest.py`)

```python
@pytest.fixture
async def auth_headers(client) -> dict:
    """Registra usuário e retorna headers com token."""
    response = await client.post("/auth/register", json={
        "email": "statements_test@example.com",
        "password": "12345678",
    })
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def auth_headers_with_exhausted_free_usage(client, db) -> dict:
    """Registra usuário com limite de análises esgotado."""
    response = await client.post("/auth/register", json={
        "email": "exhausted@example.com",
        "password": "12345678",
    })
    token = response.json()["access_token"]
    user_id = response.json()["user"]["id"]

    # Cria FreeUsage com limite esgotado
    from app.models.auth import FreeUsage
    free_usage = FreeUsage(user_id=user_id, analyses_used=3)
    db.add(free_usage)
    await db.commit()

    return {"Authorization": f"Bearer {token}"}
```

## Dependências (`pyproject.toml`)

Adicionar:

```toml
dependencies = [
    # ... existentes
    "celery>=5.3.0",
    "redis>=5.0.0",
    "google-generativeai>=0.5.0",
]
```

## Variáveis de Ambiente (`.env.example`)

Adicionar:

```env
REDIS_URL=redis://localhost:6379/0
GEMINI_API_KEY=sua-chave-gemini-aqui
```

## Modificação no `main.py`

```python
from app.routers.statements import router as statements_router

# ... (código existente)

app.include_router(statements_router)
```

## Como Rodar

**1. Iniciar Redis:**
```bash
docker run -d -p 6379:6379 redis:alpine
```

**2. Iniciar Celery Worker:**
```bash
celery -A app.workers.celery_app worker --loglevel=info
```

**3. Iniciar API:**
```bash
uv run uvicorn app.main:app --reload
```

## Fluxo Completo

```
1. POST /statements/upload (PDF)
   ↓
2. Verifica paywall (402 se limite)
   ↓
3. Cria BankStatement (status="processing")
   ↓
4. Enfileira task Celery
   ↓
5. Retorna 202 com statement_id
   ↓
6. [Worker] Processa PDF via Gemini
   ↓
7. [Worker] Cria transações, atualiza status
   ↓
8. GET /statements/{id} (polling)
   ↓
9. Retorna statement com transações (quando completed)
```

## Próximos Sub-projetos

1. ~~Foundation~~ ✅
2. ~~Auth~~ ✅
3. ~~PDF Pipeline~~ ← este
4. **Payments** — Stripe, webhooks, assinaturas
