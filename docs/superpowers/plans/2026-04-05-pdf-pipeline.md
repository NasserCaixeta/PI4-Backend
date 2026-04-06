# PDF Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar pipeline de upload e processamento de extratos bancários PDF com Celery e Gemini API.

**Architecture:** Upload assíncrono via FastAPI, processamento em background com Celery/Redis, extração de transações via Google Gemini API, paywall com limite de 3 análises grátis.

**Tech Stack:** FastAPI, Celery, Redis, Google Generative AI (Gemini), SQLAlchemy async

---

## File Structure

| Arquivo | Ação | Responsabilidade |
|---------|------|------------------|
| `app/core/config.py` | Modificar | Adicionar configs Redis/Gemini/Paywall |
| `app/services/__init__.py` | Criar | Package init |
| `app/services/gemini.py` | Criar | Cliente Gemini para extração |
| `app/workers/__init__.py` | Criar | Package init |
| `app/workers/celery_app.py` | Criar | Configuração Celery |
| `app/workers/tasks.py` | Criar | Task de processamento |
| `app/routers/statements.py` | Criar | Endpoints upload/list/get |
| `app/main.py` | Modificar | Incluir statements_router |
| `tests/conftest.py` | Modificar | Adicionar fixtures auth_headers |
| `tests/test_statements.py` | Criar | Testes dos endpoints |
| `pyproject.toml` | Modificar | Adicionar dependências |
| `.env.example` | Modificar | Adicionar variáveis |

---

### Task 1: Adicionar Dependências

**Files:**
- Modify: `pyproject.toml`
- Modify: `.env.example`

- [ ] **Step 1: Adicionar dependências ao pyproject.toml**

Adicionar ao array `dependencies` em `pyproject.toml`:

```toml
    "celery>=5.3.0",
    "redis>=5.0.0",
    "google-generativeai>=0.5.0",
```

- [ ] **Step 2: Adicionar variáveis ao .env.example**

Adicionar ao final de `.env.example`:

```env
REDIS_URL=redis://localhost:6379/0
# GEMINI_API_KEY=sua-chave-gemini-aqui
```

- [ ] **Step 3: Instalar dependências**

Run: `uv sync --all-extras`

Expected: Dependências instaladas com sucesso

---

### Task 2: Atualizar Configuração

**Files:**
- Modify: `app/core/config.py`

- [ ] **Step 1: Adicionar configurações Redis/Gemini/Paywall**

Adicionar os seguintes campos à classe `Settings` em `app/core/config.py`, após `RESEND_API_KEY`:

```python
    # Redis/Celery
    REDIS_URL: str = "redis://localhost:6379/0"

    # Gemini
    GEMINI_MODEL: str = "gemini-1.5-flash"

    # Paywall
    FREE_ANALYSES_LIMIT: int = 3
```

---

### Task 3: Criar Serviço Gemini

**Files:**
- Create: `app/services/__init__.py`
- Create: `app/services/gemini.py`

- [ ] **Step 1: Criar package services**

Criar `app/services/__init__.py`:

```python
```

(arquivo vazio)

- [ ] **Step 2: Criar serviço Gemini**

Criar `app/services/gemini.py`:

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

---

### Task 4: Criar Celery App

**Files:**
- Create: `app/workers/__init__.py`
- Create: `app/workers/celery_app.py`

- [ ] **Step 1: Criar package workers**

Criar `app/workers/__init__.py`:

```python
```

(arquivo vazio)

- [ ] **Step 2: Criar configuração Celery**

Criar `app/workers/celery_app.py`:

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

---

### Task 5: Criar Task de Processamento

**Files:**
- Create: `app/workers/tasks.py`

- [ ] **Step 1: Criar task process_statement**

Criar `app/workers/tasks.py`:

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

---

### Task 6: Criar Router Statements

**Files:**
- Create: `app/routers/statements.py`

- [ ] **Step 1: Criar router com endpoints**

Criar `app/routers/statements.py`:

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

---

### Task 7: Incluir Router no Main

**Files:**
- Modify: `app/main.py`

- [ ] **Step 1: Adicionar import do statements_router**

Adicionar import no topo de `app/main.py`:

```python
from app.routers.statements import router as statements_router
```

- [ ] **Step 2: Incluir router na app**

Adicionar após `app.include_router(auth_router)`:

```python
app.include_router(statements_router)
```

---

### Task 8: Adicionar Fixtures de Teste

**Files:**
- Modify: `tests/conftest.py`

- [ ] **Step 1: Adicionar fixture auth_headers**

Adicionar ao final de `tests/conftest.py`:

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
```

- [ ] **Step 2: Adicionar import pytest**

Verificar que `import pytest` existe no topo do arquivo (já deve existir).

---

### Task 9: Criar Testes de Statements

**Files:**
- Create: `tests/test_statements.py`

- [ ] **Step 1: Criar arquivo de testes**

Criar `tests/test_statements.py`:

```python
import pytest
from unittest.mock import MagicMock, patch


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
    assert "PDF" in response.json()["detail"]


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
async def test_upload_increments_free_usage(client, auth_headers, db):
    with patch("app.routers.statements.process_statement") as mock_task:
        mock_task.delay = MagicMock()

        # Primeiro upload
        await client.post(
            "/statements/upload",
            files={"file": ("extrato1.pdf", b"%PDF-fake", "application/pdf")},
            headers=auth_headers,
        )

        # Verifica que free_usage foi criado e incrementado
        from sqlalchemy import select
        from app.models.auth import FreeUsage

        result = await db.execute(select(FreeUsage))
        free_usage = result.scalar_one_or_none()
        assert free_usage is not None
        assert free_usage.analyses_used == 1


@pytest.mark.anyio
async def test_upload_paywall_limit(client, db):
    # Registra usuário
    reg_response = await client.post("/auth/register", json={
        "email": "paywall_test@example.com",
        "password": "12345678",
    })
    token = reg_response.json()["access_token"]
    user_id = reg_response.json()["user"]["id"]
    headers = {"Authorization": f"Bearer {token}"}

    # Cria FreeUsage com limite esgotado
    from app.models.auth import FreeUsage
    import uuid

    free_usage = FreeUsage(user_id=uuid.UUID(user_id), analyses_used=3)
    db.add(free_usage)
    await db.commit()

    with patch("app.routers.statements.process_statement"):
        response = await client.post(
            "/statements/upload",
            files={"file": ("extrato.pdf", b"%PDF-fake", "application/pdf")},
            headers=headers,
        )
        assert response.status_code == 402


@pytest.mark.anyio
async def test_list_statements_empty(client, auth_headers):
    response = await client.get("/statements", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.anyio
async def test_list_statements_with_data(client, auth_headers):
    with patch("app.routers.statements.process_statement") as mock_task:
        mock_task.delay = MagicMock()

        # Upload um statement
        await client.post(
            "/statements/upload",
            files={"file": ("extrato.pdf", b"%PDF-fake", "application/pdf")},
            headers=auth_headers,
        )

        # Lista statements
        response = await client.get("/statements", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["filename"] == "extrato.pdf"


@pytest.mark.anyio
async def test_get_statement_not_found(client, auth_headers):
    response = await client.get(
        "/statements/00000000-0000-0000-0000-000000000000",
        headers=auth_headers,
    )
    assert response.status_code == 404


@pytest.mark.anyio
async def test_get_statement_success(client, auth_headers):
    with patch("app.routers.statements.process_statement") as mock_task:
        mock_task.delay = MagicMock()

        # Upload
        upload_response = await client.post(
            "/statements/upload",
            files={"file": ("extrato.pdf", b"%PDF-fake", "application/pdf")},
            headers=auth_headers,
        )
        statement_id = upload_response.json()["id"]

        # Get
        response = await client.get(f"/statements/{statement_id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == statement_id
        assert data["filename"] == "extrato.pdf"
```

---

### Task 10: Rodar Testes e Verificar

**Files:**
- None (verification only)

- [ ] **Step 1: Rodar todos os testes**

Run: `uv run pytest tests/ -v`

Expected: Todos os testes passando (7 auth + 1 health + 10 statements = 18 testes)

```
tests/test_health.py::test_health_check_returns_healthy PASSED
tests/test_auth.py::test_register_success PASSED
tests/test_auth.py::test_register_duplicate_email PASSED
tests/test_auth.py::test_login_success PASSED
tests/test_auth.py::test_login_wrong_password PASSED
tests/test_auth.py::test_me_authenticated PASSED
tests/test_auth.py::test_me_unauthenticated PASSED
tests/test_statements.py::test_upload_requires_auth PASSED
tests/test_statements.py::test_upload_requires_pdf PASSED
tests/test_statements.py::test_upload_success PASSED
tests/test_statements.py::test_upload_increments_free_usage PASSED
tests/test_statements.py::test_upload_paywall_limit PASSED
tests/test_statements.py::test_list_statements_empty PASSED
tests/test_statements.py::test_list_statements_with_data PASSED
tests/test_statements.py::test_get_statement_not_found PASSED
tests/test_statements.py::test_get_statement_success PASSED
```
