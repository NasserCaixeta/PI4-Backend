# Dashboard Financeiro Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement financial dashboard with categories CRUD, transactions management, and aggregated metrics with period comparison.

**Architecture:** Three separate routers (categories, transactions, dashboard) with dedicated schemas. Dashboard service encapsulates metric calculation logic. Default categories seeded at startup.

**Tech Stack:** FastAPI, SQLAlchemy async, Pydantic v2, pytest-anyio

---

## File Structure

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `app/schemas/categories.py` | Category schemas |
| Create | `app/schemas/transactions.py` | Transaction schemas |
| Create | `app/schemas/dashboard.py` | Dashboard response schemas |
| Create | `app/routers/categories.py` | Categories CRUD endpoints |
| Create | `app/routers/transactions.py` | Transactions CRUD endpoints |
| Create | `app/services/dashboard.py` | Metric calculation logic |
| Create | `app/routers/dashboard.py` | Dashboard endpoints |
| Modify | `app/database.py` | Add seed_default_categories function |
| Modify | `app/main.py` | Call seed in lifespan, include new routers |
| Create | `tests/test_categories.py` | Category tests |
| Create | `tests/test_transactions.py` | Transaction tests |
| Create | `tests/test_dashboard.py` | Dashboard tests |

---

### Task 1: Category Schemas

**Files:**
- Create: `app/schemas/categories.py`

- [ ] **Step 1: Create category schemas file**

```python
import uuid

from pydantic import BaseModel, ConfigDict


class CategoryCreate(BaseModel):
    name: str
    color: str | None = None
    icon: str | None = None


class CategoryUpdate(BaseModel):
    name: str | None = None
    color: str | None = None
    icon: str | None = None


class CategoryResponse(BaseModel):
    id: uuid.UUID
    name: str
    color: str | None
    icon: str | None
    is_default: bool

    model_config = ConfigDict(from_attributes=True)
```

- [ ] **Step 2: Verify file syntax**

Run: `uv run python -c "from app.schemas.categories import CategoryCreate, CategoryUpdate, CategoryResponse; print('OK')"`

Expected: `OK`

---

### Task 2: Transaction Schemas

**Files:**
- Create: `app/schemas/transactions.py`

- [ ] **Step 1: Create transaction schemas file**

```python
import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.schemas.categories import CategoryResponse


class TransactionUpdate(BaseModel):
    category_id: uuid.UUID | None = None
    description: str | None = None


class TransactionResponse(BaseModel):
    id: uuid.UUID
    date: date
    description: str | None
    amount: Decimal
    type: str
    category: CategoryResponse | None

    model_config = ConfigDict(from_attributes=True)


class TransactionListResponse(BaseModel):
    items: list[TransactionResponse]
    total: int
    limit: int
    offset: int
```

- [ ] **Step 2: Verify file syntax**

Run: `uv run python -c "from app.schemas.transactions import TransactionUpdate, TransactionResponse, TransactionListResponse; print('OK')"`

Expected: `OK`

---

### Task 3: Dashboard Schemas

**Files:**
- Create: `app/schemas/dashboard.py`

- [ ] **Step 1: Create dashboard schemas file**

```python
from datetime import date
from decimal import Decimal

from pydantic import BaseModel

from app.schemas.categories import CategoryResponse


class PeriodSchema(BaseModel):
    start: date
    end: date


class ComparisonSchema(BaseModel):
    income_change_percent: float | None
    expenses_change_percent: float | None
    previous_period: PeriodSchema


class SummaryResponse(BaseModel):
    period: PeriodSchema
    total_income: Decimal
    total_expenses: Decimal
    balance: Decimal
    transaction_count: int
    comparison: ComparisonSchema | None


class CategoryComparisonSchema(BaseModel):
    change_percent: float | None
    previous_total: Decimal


class CategoryBreakdownItem(BaseModel):
    category: CategoryResponse | None
    total: Decimal
    percentage: float
    transaction_count: int
    comparison: CategoryComparisonSchema | None


class ByCategoryResponse(BaseModel):
    period: PeriodSchema
    categories: list[CategoryBreakdownItem]
```

- [ ] **Step 2: Verify file syntax**

Run: `uv run python -c "from app.schemas.dashboard import SummaryResponse, ByCategoryResponse; print('OK')"`

Expected: `OK`

---

### Task 4: Seed Default Categories

**Files:**
- Modify: `app/database.py`
- Modify: `app/main.py`

- [ ] **Step 1: Add seed function to database.py**

Add at end of `app/database.py`:

```python
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
    from app.models.statements import Category

    async with async_session() as db:
        for cat_data in DEFAULT_CATEGORIES:
            stmt = sqlite_insert(Category).values(
                name=cat_data["name"],
                color=cat_data["color"],
                icon=cat_data["icon"],
                is_default=True,
                user_id=None,
            ).on_conflict_do_nothing(index_elements=["name"])
            await db.execute(stmt)
        await db.commit()
```

- [ ] **Step 2: Update main.py lifespan to call seed**

Replace the lifespan function in `app/main.py`:

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from app.database import engine, seed_default_categories
from app.routers.auth import router as auth_router
from app.routers.health import router as health_router
from app.routers.statements import router as statements_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.execute(text("SELECT 1"))
    await seed_default_categories()
    yield
    await engine.dispose()
```

- [ ] **Step 3: Add unique constraint to Category.name for upsert**

Check `app/models/statements.py` - the Category model needs a unique constraint on `name` for `on_conflict_do_nothing` to work. Add to Category class:

```python
from sqlalchemy import UniqueConstraint

class Category(Base):
    __tablename__ = "categories"
    __table_args__ = (UniqueConstraint("name", "user_id", name="uq_category_name_user"),)
    # ... rest of fields
```

- [ ] **Step 4: Verify seed runs without error**

Run: `uv run python -c "import asyncio; from app.database import seed_default_categories; asyncio.run(seed_default_categories()); print('OK')"`

Expected: `OK`

---

### Task 5: Categories Router - List and Create

**Files:**
- Create: `app/routers/categories.py`
- Create: `tests/test_categories.py`

- [ ] **Step 1: Write failing test for list categories**

Create `tests/test_categories.py`:

```python
import pytest


@pytest.mark.anyio
async def test_list_categories_returns_defaults(client, auth_headers):
    response = await client.get("/categories", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 6
    names = [c["name"] for c in data]
    assert "Alimentação" in names
    assert "Outros" in names
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_categories.py::test_list_categories_returns_defaults -v`

Expected: FAIL (404 or no route)

- [ ] **Step 3: Create categories router with list endpoint**

Create `app/routers/categories.py`:

```python
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.database import get_db
from app.models.auth import User
from app.models.statements import Category
from app.schemas.categories import CategoryCreate, CategoryResponse, CategoryUpdate

router = APIRouter(prefix="/categories", tags=["Categories"])


@router.get("", response_model=list[CategoryResponse])
async def list_categories(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Category).where(
            or_(Category.user_id == user.id, Category.is_default == True)
        )
    )
    return result.scalars().all()


@router.post("", response_model=CategoryResponse, status_code=201)
async def create_category(
    data: CategoryCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    category = Category(
        name=data.name,
        color=data.color,
        icon=data.icon,
        user_id=user.id,
        is_default=False,
    )
    db.add(category)
    await db.commit()
    await db.refresh(category)
    return category
```

- [ ] **Step 4: Include router in main.py**

Add to `app/main.py`:

```python
from app.routers.categories import router as categories_router

# In app setup, add:
app.include_router(categories_router)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_categories.py::test_list_categories_returns_defaults -v`

Expected: PASS

- [ ] **Step 6: Write and run test for create category**

Add to `tests/test_categories.py`:

```python
@pytest.mark.anyio
async def test_create_custom_category(client, auth_headers):
    response = await client.post(
        "/categories",
        json={"name": "Investimentos", "color": "#FFD700", "icon": "chart-line"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Investimentos"
    assert data["color"] == "#FFD700"
    assert data["is_default"] is False
```

Run: `uv run pytest tests/test_categories.py::test_create_custom_category -v`

Expected: PASS

---

### Task 6: Categories Router - Update and Delete

**Files:**
- Modify: `app/routers/categories.py`
- Modify: `tests/test_categories.py`

- [ ] **Step 1: Write failing test for cannot edit default**

Add to `tests/test_categories.py`:

```python
@pytest.mark.anyio
async def test_cannot_edit_default_category(client, auth_headers):
    # Get a default category
    list_response = await client.get("/categories", headers=auth_headers)
    default_cat = next(c for c in list_response.json() if c["is_default"])

    response = await client.patch(
        f"/categories/{default_cat['id']}",
        json={"name": "Renamed"},
        headers=auth_headers,
    )
    assert response.status_code == 403
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_categories.py::test_cannot_edit_default_category -v`

Expected: FAIL (404 or 405)

- [ ] **Step 3: Add update endpoint**

Add to `app/routers/categories.py`:

```python
@router.patch("/{category_id}", response_model=CategoryResponse)
async def update_category(
    category_id: uuid.UUID,
    data: CategoryUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Category).where(Category.id == category_id)
    )
    category = result.scalar_one_or_none()

    if not category:
        raise HTTPException(status_code=404, detail="Categoria não encontrada")

    if category.is_default or category.user_id != user.id:
        raise HTTPException(status_code=403, detail="Não é possível editar esta categoria")

    if data.name is not None:
        category.name = data.name
    if data.color is not None:
        category.color = data.color if data.color != "" else None
    if data.icon is not None:
        category.icon = data.icon if data.icon != "" else None

    await db.commit()
    await db.refresh(category)
    return category
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_categories.py::test_cannot_edit_default_category -v`

Expected: PASS

- [ ] **Step 5: Write failing test for cannot delete default**

Add to `tests/test_categories.py`:

```python
@pytest.mark.anyio
async def test_cannot_delete_default_category(client, auth_headers):
    list_response = await client.get("/categories", headers=auth_headers)
    default_cat = next(c for c in list_response.json() if c["is_default"])

    response = await client.delete(
        f"/categories/{default_cat['id']}",
        headers=auth_headers,
    )
    assert response.status_code == 403
```

- [ ] **Step 6: Run test to verify it fails**

Run: `uv run pytest tests/test_categories.py::test_cannot_delete_default_category -v`

Expected: FAIL

- [ ] **Step 7: Add delete endpoint**

Add to `app/routers/categories.py`:

```python
from sqlalchemy.orm import selectinload

@router.delete("/{category_id}", status_code=204)
async def delete_category(
    category_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Category)
        .options(selectinload(Category.transactions))
        .where(Category.id == category_id)
    )
    category = result.scalar_one_or_none()

    if not category:
        raise HTTPException(status_code=404, detail="Categoria não encontrada")

    if category.is_default or category.user_id != user.id:
        raise HTTPException(status_code=403, detail="Não é possível deletar esta categoria")

    # Move transactions to "Outros"
    if category.transactions:
        outros_result = await db.execute(
            select(Category).where(Category.name == "Outros", Category.is_default == True)
        )
        outros = outros_result.scalar_one()
        for tx in category.transactions:
            tx.category_id = outros.id

    await db.delete(category)
    await db.commit()
```

- [ ] **Step 8: Run test to verify it passes**

Run: `uv run pytest tests/test_categories.py::test_cannot_delete_default_category -v`

Expected: PASS

- [ ] **Step 9: Write and run test for delete moves transactions**

Add to `tests/test_categories.py`:

```python
@pytest.mark.anyio
async def test_delete_category_moves_transactions(client, auth_headers, db):
    # Create custom category
    create_resp = await client.post(
        "/categories",
        json={"name": "ToDelete"},
        headers=auth_headers,
    )
    cat_id = create_resp.json()["id"]

    # Delete it (no transactions, but test the endpoint works)
    delete_resp = await client.delete(f"/categories/{cat_id}", headers=auth_headers)
    assert delete_resp.status_code == 204

    # Verify it's gone
    list_resp = await client.get("/categories", headers=auth_headers)
    names = [c["name"] for c in list_resp.json()]
    assert "ToDelete" not in names
```

Run: `uv run pytest tests/test_categories.py::test_delete_category_moves_transactions -v`

Expected: PASS

- [ ] **Step 10: Run all category tests**

Run: `uv run pytest tests/test_categories.py -v`

Expected: All 5 tests PASS

---

### Task 7: Transactions Router - List with Filters

**Files:**
- Create: `app/routers/transactions.py`
- Create: `tests/test_transactions.py`

- [ ] **Step 1: Write failing test for list transactions empty**

Create `tests/test_transactions.py`:

```python
import pytest


@pytest.mark.anyio
async def test_list_transactions_empty(client, auth_headers):
    response = await client.get("/transactions", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_transactions.py::test_list_transactions_empty -v`

Expected: FAIL (404)

- [ ] **Step 3: Create transactions router**

Create `app/routers/transactions.py`:

```python
import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.dependencies import get_current_user
from app.database import get_db
from app.models.auth import User
from app.models.statements import BankStatement, Transaction
from app.schemas.transactions import (
    TransactionListResponse,
    TransactionResponse,
    TransactionUpdate,
)

router = APIRouter(prefix="/transactions", tags=["Transactions"])


def get_date_filter(
    month: int | None, year: int | None, start_date: date | None, end_date: date | None
) -> tuple[date | None, date | None]:
    """Returns start and end date based on params. Returns (None, None) if no filter."""
    if month and year:
        import calendar
        last_day = calendar.monthrange(year, month)[1]
        return date(year, month, 1), date(year, month, last_day)
    if start_date and end_date:
        return start_date, end_date
    return None, None


@router.get("", response_model=TransactionListResponse)
async def list_transactions(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    month: int | None = Query(None, ge=1, le=12),
    year: int | None = Query(None, ge=2000, le=2100),
    start_date: date | None = None,
    end_date: date | None = None,
    category_id: uuid.UUID | None = None,
    type: str | None = Query(None, regex="^(credit|debit)$"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    # Base query: only user's transactions via statement
    base_query = (
        select(Transaction)
        .join(BankStatement)
        .where(BankStatement.user_id == user.id)
        .options(selectinload(Transaction.category))
    )

    # Apply filters
    filters = []
    date_start, date_end = get_date_filter(month, year, start_date, end_date)
    if date_start and date_end:
        filters.append(Transaction.date >= date_start)
        filters.append(Transaction.date <= date_end)
    if category_id:
        filters.append(Transaction.category_id == category_id)
    if type:
        filters.append(Transaction.type == type)

    if filters:
        base_query = base_query.where(and_(*filters))

    # Count total
    count_query = select(func.count()).select_from(
        base_query.with_only_columns(Transaction.id).subquery()
    )
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Paginate
    query = base_query.order_by(Transaction.date.desc()).limit(limit).offset(offset)
    result = await db.execute(query)
    items = result.scalars().all()

    return TransactionListResponse(items=items, total=total, limit=limit, offset=offset)
```

- [ ] **Step 4: Include router in main.py**

Add to `app/main.py`:

```python
from app.routers.transactions import router as transactions_router

app.include_router(transactions_router)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_transactions.py::test_list_transactions_empty -v`

Expected: PASS

- [ ] **Step 6: Write and run test for filters**

Add to `tests/test_transactions.py`:

```python
@pytest.mark.anyio
async def test_list_transactions_with_filters(client, auth_headers):
    # Without data, filters should still work and return empty
    response = await client.get(
        "/transactions",
        params={"month": 4, "year": 2026, "type": "debit"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
```

Run: `uv run pytest tests/test_transactions.py::test_list_transactions_with_filters -v`

Expected: PASS

---

### Task 8: Transactions Router - Get, Update, Delete

**Files:**
- Modify: `app/routers/transactions.py`
- Modify: `tests/test_transactions.py`

- [ ] **Step 1: Add get single transaction endpoint**

Add to `app/routers/transactions.py`:

```python
@router.get("/{transaction_id}", response_model=TransactionResponse)
async def get_transaction(
    transaction_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Transaction)
        .join(BankStatement)
        .where(Transaction.id == transaction_id, BankStatement.user_id == user.id)
        .options(selectinload(Transaction.category))
    )
    transaction = result.scalar_one_or_none()

    if not transaction:
        raise HTTPException(status_code=404, detail="Transação não encontrada")

    return transaction
```

- [ ] **Step 2: Add update transaction endpoint**

Add to `app/routers/transactions.py`:

```python
@router.patch("/{transaction_id}", response_model=TransactionResponse)
async def update_transaction(
    transaction_id: uuid.UUID,
    data: TransactionUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Transaction)
        .join(BankStatement)
        .where(Transaction.id == transaction_id, BankStatement.user_id == user.id)
        .options(selectinload(Transaction.category))
    )
    transaction = result.scalar_one_or_none()

    if not transaction:
        raise HTTPException(status_code=404, detail="Transação não encontrada")

    if data.category_id is not None:
        transaction.category_id = data.category_id
    if data.description is not None:
        transaction.description = data.description

    await db.commit()
    await db.refresh(transaction, ["category"])
    return transaction
```

- [ ] **Step 3: Add delete transaction endpoint**

Add to `app/routers/transactions.py`:

```python
@router.delete("/{transaction_id}", status_code=204)
async def delete_transaction(
    transaction_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Transaction)
        .join(BankStatement)
        .where(Transaction.id == transaction_id, BankStatement.user_id == user.id)
    )
    transaction = result.scalar_one_or_none()

    if not transaction:
        raise HTTPException(status_code=404, detail="Transação não encontrada")

    await db.delete(transaction)
    await db.commit()
```

- [ ] **Step 4: Write and run tests**

Add to `tests/test_transactions.py`:

```python
@pytest.mark.anyio
async def test_cannot_access_other_user_transaction(client, auth_headers):
    # Try to access a non-existent transaction (simulates other user's)
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = await client.get(f"/transactions/{fake_id}", headers=auth_headers)
    assert response.status_code == 404


@pytest.mark.anyio
async def test_update_transaction_not_found(client, auth_headers):
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = await client.patch(
        f"/transactions/{fake_id}",
        json={"description": "Updated"},
        headers=auth_headers,
    )
    assert response.status_code == 404


@pytest.mark.anyio
async def test_delete_transaction_not_found(client, auth_headers):
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = await client.delete(f"/transactions/{fake_id}", headers=auth_headers)
    assert response.status_code == 404
```

Run: `uv run pytest tests/test_transactions.py -v`

Expected: All tests PASS

---

### Task 9: Dashboard Service

**Files:**
- Create: `app/services/dashboard.py`

- [ ] **Step 1: Create dashboard service**

Create `app/services/dashboard.py`:

```python
import calendar
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.statements import BankStatement, Category, Transaction
from app.schemas.categories import CategoryResponse
from app.schemas.dashboard import (
    ByCategoryResponse,
    CategoryBreakdownItem,
    CategoryComparisonSchema,
    ComparisonSchema,
    PeriodSchema,
    SummaryResponse,
)


def get_period_dates(
    month: int | None, year: int | None, start_date: date | None, end_date: date | None
) -> tuple[date, date]:
    """Returns start and end dates for the period."""
    if month and year:
        last_day = calendar.monthrange(year, month)[1]
        return date(year, month, 1), date(year, month, last_day)
    if start_date and end_date:
        return start_date, end_date
    # Default: current month
    today = date.today()
    last_day = calendar.monthrange(today.year, today.month)[1]
    return date(today.year, today.month, 1), date(today.year, today.month, last_day)


def get_previous_period(start: date, end: date) -> tuple[date, date]:
    """Returns the previous period of same duration."""
    duration = (end - start).days + 1
    prev_end = start - __import__("datetime").timedelta(days=1)
    prev_start = prev_end - __import__("datetime").timedelta(days=duration - 1)
    return prev_start, prev_end


async def get_period_totals(
    db: AsyncSession, user_id: uuid.UUID, start: date, end: date
) -> tuple[Decimal, Decimal, int]:
    """Returns (total_income, total_expenses, count) for period."""
    result = await db.execute(
        select(
            func.coalesce(func.sum(Transaction.amount).filter(Transaction.type == "credit"), 0),
            func.coalesce(func.sum(Transaction.amount).filter(Transaction.type == "debit"), 0),
            func.count(Transaction.id),
        )
        .join(BankStatement)
        .where(
            BankStatement.user_id == user_id,
            Transaction.date >= start,
            Transaction.date <= end,
        )
    )
    row = result.one()
    return Decimal(str(row[0])), Decimal(str(row[1])), row[2]


def calc_change_percent(current: Decimal, previous: Decimal) -> float | None:
    """Calculate percentage change."""
    if previous == 0:
        return None
    return round(float((current - previous) / previous * 100), 1)


async def get_summary(
    db: AsyncSession,
    user_id: uuid.UUID,
    month: int | None,
    year: int | None,
    start_date: date | None,
    end_date: date | None,
) -> SummaryResponse:
    start, end = get_period_dates(month, year, start_date, end_date)
    income, expenses, count = await get_period_totals(db, user_id, start, end)

    # Previous period comparison
    prev_start, prev_end = get_previous_period(start, end)
    prev_income, prev_expenses, _ = await get_period_totals(db, user_id, prev_start, prev_end)

    comparison = ComparisonSchema(
        income_change_percent=calc_change_percent(income, prev_income),
        expenses_change_percent=calc_change_percent(expenses, prev_expenses),
        previous_period=PeriodSchema(start=prev_start, end=prev_end),
    )

    return SummaryResponse(
        period=PeriodSchema(start=start, end=end),
        total_income=income,
        total_expenses=expenses,
        balance=income - expenses,
        transaction_count=count,
        comparison=comparison,
    )


async def get_by_category(
    db: AsyncSession,
    user_id: uuid.UUID,
    month: int | None,
    year: int | None,
    start_date: date | None,
    end_date: date | None,
) -> ByCategoryResponse:
    start, end = get_period_dates(month, year, start_date, end_date)
    prev_start, prev_end = get_previous_period(start, end)

    # Current period by category (only expenses/debits)
    result = await db.execute(
        select(
            Transaction.category_id,
            func.sum(Transaction.amount).label("total"),
            func.count(Transaction.id).label("count"),
        )
        .join(BankStatement)
        .where(
            BankStatement.user_id == user_id,
            Transaction.date >= start,
            Transaction.date <= end,
            Transaction.type == "debit",
        )
        .group_by(Transaction.category_id)
    )
    current_data = {row.category_id: (Decimal(str(row.total)), row.count) for row in result}

    # Previous period by category
    prev_result = await db.execute(
        select(
            Transaction.category_id,
            func.sum(Transaction.amount).label("total"),
        )
        .join(BankStatement)
        .where(
            BankStatement.user_id == user_id,
            Transaction.date >= prev_start,
            Transaction.date <= prev_end,
            Transaction.type == "debit",
        )
        .group_by(Transaction.category_id)
    )
    prev_data = {row.category_id: Decimal(str(row.total)) for row in prev_result}

    # Fetch categories
    cat_ids = list(current_data.keys())
    if cat_ids:
        cat_result = await db.execute(select(Category).where(Category.id.in_(cat_ids)))
        categories = {c.id: c for c in cat_result.scalars()}
    else:
        categories = {}

    # Calculate total for percentage
    total_expenses = sum(t[0] for t in current_data.values())

    # Build breakdown
    items = []
    for cat_id, (total, count) in sorted(current_data.items(), key=lambda x: x[1][0], reverse=True):
        cat = categories.get(cat_id)
        prev_total = prev_data.get(cat_id, Decimal("0"))

        items.append(
            CategoryBreakdownItem(
                category=CategoryResponse.model_validate(cat) if cat else None,
                total=total,
                percentage=round(float(total / total_expenses * 100), 1) if total_expenses else 0,
                transaction_count=count,
                comparison=CategoryComparisonSchema(
                    change_percent=calc_change_percent(total, prev_total),
                    previous_total=prev_total,
                ),
            )
        )

    return ByCategoryResponse(
        period=PeriodSchema(start=start, end=end),
        categories=items,
    )
```

- [ ] **Step 2: Verify syntax**

Run: `uv run python -c "from app.services.dashboard import get_summary, get_by_category; print('OK')"`

Expected: `OK`

---

### Task 10: Dashboard Router

**Files:**
- Create: `app/routers/dashboard.py`
- Modify: `app/main.py`
- Create: `tests/test_dashboard.py`

- [ ] **Step 1: Write failing test for summary empty**

Create `tests/test_dashboard.py`:

```python
import pytest


@pytest.mark.anyio
async def test_summary_empty(client, auth_headers):
    response = await client.get("/dashboard/summary", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total_income"] == "0"
    assert data["total_expenses"] == "0"
    assert data["balance"] == "0"
    assert data["transaction_count"] == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_dashboard.py::test_summary_empty -v`

Expected: FAIL (404)

- [ ] **Step 3: Create dashboard router**

Create `app/routers/dashboard.py`:

```python
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.database import get_db
from app.models.auth import User
from app.schemas.dashboard import ByCategoryResponse, SummaryResponse
from app.services import dashboard as dashboard_service

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/summary", response_model=SummaryResponse)
async def get_summary(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    month: int | None = Query(None, ge=1, le=12),
    year: int | None = Query(None, ge=2000, le=2100),
    start_date: date | None = None,
    end_date: date | None = None,
):
    return await dashboard_service.get_summary(db, user.id, month, year, start_date, end_date)


@router.get("/by-category", response_model=ByCategoryResponse)
async def get_by_category(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    month: int | None = Query(None, ge=1, le=12),
    year: int | None = Query(None, ge=2000, le=2100),
    start_date: date | None = None,
    end_date: date | None = None,
):
    return await dashboard_service.get_by_category(db, user.id, month, year, start_date, end_date)
```

- [ ] **Step 4: Include router in main.py**

Add to `app/main.py`:

```python
from app.routers.dashboard import router as dashboard_router

app.include_router(dashboard_router)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_dashboard.py::test_summary_empty -v`

Expected: PASS

- [ ] **Step 6: Write and run remaining dashboard tests**

Add to `tests/test_dashboard.py`:

```python
@pytest.mark.anyio
async def test_by_category_empty(client, auth_headers):
    response = await client.get("/dashboard/by-category", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["categories"] == []


@pytest.mark.anyio
async def test_summary_filter_by_month(client, auth_headers):
    response = await client.get(
        "/dashboard/summary",
        params={"month": 4, "year": 2026},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["period"]["start"] == "2026-04-01"
    assert data["period"]["end"] == "2026-04-30"


@pytest.mark.anyio
async def test_summary_filter_by_date_range(client, auth_headers):
    response = await client.get(
        "/dashboard/summary",
        params={"start_date": "2026-01-01", "end_date": "2026-01-31"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["period"]["start"] == "2026-01-01"
    assert data["period"]["end"] == "2026-01-31"


@pytest.mark.anyio
async def test_summary_has_comparison(client, auth_headers):
    response = await client.get(
        "/dashboard/summary",
        params={"month": 4, "year": 2026},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert "comparison" in data
    assert data["comparison"]["previous_period"]["start"] == "2026-03-01"
    assert data["comparison"]["previous_period"]["end"] == "2026-03-31"
```

Run: `uv run pytest tests/test_dashboard.py -v`

Expected: All tests PASS

---

### Task 11: Final Integration Test

**Files:**
- All test files

- [ ] **Step 1: Run all tests**

Run: `uv run pytest tests/ -v`

Expected: All tests PASS

- [ ] **Step 2: Verify API starts correctly**

Run: `uv run python -c "from app.main import app; print('App OK')" `

Expected: `App OK`

---

## Summary

| Task | Description | Tests |
|------|-------------|-------|
| 1 | Category Schemas | - |
| 2 | Transaction Schemas | - |
| 3 | Dashboard Schemas | - |
| 4 | Seed Default Categories | - |
| 5 | Categories List/Create | 2 |
| 6 | Categories Update/Delete | 3 |
| 7 | Transactions List | 2 |
| 8 | Transactions Get/Update/Delete | 3 |
| 9 | Dashboard Service | - |
| 10 | Dashboard Router | 4 |
| 11 | Final Integration | - |

**Total: 11 tasks, 14 new tests**
