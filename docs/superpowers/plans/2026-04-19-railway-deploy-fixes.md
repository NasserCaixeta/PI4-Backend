# Railway Deploy Fixes — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Camelbox backend deployable on Railway with PostgreSQL, with login/register endpoints functional.

**Architecture:** 4 surgical changes — replace SQLite-specific ORM calls with generic ones, add CORS middleware, create Procfile for Railway. No new features.

**Tech Stack:** FastAPI, SQLAlchemy (async), Alembic, Railway, PostgreSQL

**Spec:** `docs/superpowers/specs/2026-04-19-railway-deploy-fixes-design.md`

---

### Task 1: Fix SQLite-specific insert in `app/database.py`

**Files:**
- Modify: `app/database.py:22-59`

- [ ] **Step 1: Remove `sqlite_insert` import and replace seed logic**

Replace the entire block from line 22 to 59 with:

```python
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
```

What changed: removed `from sqlalchemy.dialects.sqlite import insert as sqlite_insert`, replaced `sqlite_insert(Category).values(...)` with `db.add(Category(...))`. The `if not existing` guard remains for idempotency.

- [ ] **Step 2: Run tests to verify nothing broke**

Run: `uv run pytest tests/ -v`
Expected: All tests PASS (seed logic is tested indirectly via auth tests that depend on categories existing)

---

### Task 2: Fix SQLite-specific insert in `tests/conftest.py`

**Files:**
- Modify: `tests/conftest.py:28-44`

- [ ] **Step 1: Replace sqlite_insert with db.add in test setup**

Replace lines 28-44 (inside `setup_database` fixture, after `create_all`) with:

```python
    from app.database import DEFAULT_CATEGORIES
    from app.models.statements import Category

    async with test_session() as db:
        for cat_data in DEFAULT_CATEGORIES:
            db.add(Category(
                name=cat_data["name"],
                color=cat_data["color"],
                icon=cat_data["icon"],
                is_default=True,
                user_id=None,
            ))
        await db.commit()
```

What changed: removed `from sqlalchemy.dialects.sqlite import insert as sqlite_insert`, removed `on_conflict_do_nothing()` (unnecessary — tests start from empty DB), replaced with `db.add(Category(...))`.

- [ ] **Step 2: Run tests to verify**

Run: `uv run pytest tests/ -v`
Expected: All tests PASS

---

### Task 3: Add CORS middleware to `app/main.py`

**Files:**
- Insert import after: `app/main.py:3`
- Insert middleware after: `app/main.py:28`

- [ ] **Step 1: Add CORSMiddleware import**

Add to imports (after `from fastapi import FastAPI`):

```python
from fastapi.middleware.cors import CORSMiddleware
```

- [ ] **Step 2: Add middleware after app creation**

After the `app = FastAPI(...)` block (after line 28), add:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

- [ ] **Step 3: Run tests to verify**

Run: `uv run pytest tests/ -v`
Expected: All tests PASS

---

### Task 4: Create Procfile

**Files:**
- Create: `Procfile` (project root)

- [ ] **Step 1: Create the file**

Create `Procfile` at project root with exactly:

```
web: alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

No trailing newline issues — just this one line.

---

### Task 5: Final verification

- [ ] **Step 1: Run full test suite**

Run: `uv run pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 2: Test local startup**

Run: `uv run uvicorn app.main:app --host 0.0.0.0 --port 8000`
Expected: Server starts without errors, seeds default categories

- [ ] **Step 3: Test register endpoint**

Run: `curl -X POST http://localhost:8000/auth/register -H "Content-Type: application/json" -d '{"email":"test@test.com","password":"12345678","name":"Test"}'`
Expected: 201 response with `access_token` and `user` object

- [ ] **Step 4: Test login endpoint**

Run: `curl -X POST http://localhost:8000/auth/login -H "Content-Type: application/json" -d '{"email":"test@test.com","password":"12345678"}'`
Expected: 200 response with `access_token` and `user` object

- [ ] **Step 5: Verify CORS headers**

Run: `curl -X OPTIONS http://localhost:8000/auth/login -H "Origin: https://example.pages.dev" -H "Access-Control-Request-Method: POST" -v 2>&1 | grep -i "access-control"`
Expected: Response includes `access-control-allow-origin` and `access-control-allow-methods` headers

---

### Appendix: Railway Setup (manual, after code deploy)

Estes passos sao manuais no dashboard do Railway, nao sao codigo:

1. Adicionar addon PostgreSQL no projeto Railway
2. Setar variaveis de ambiente:
   - `DATABASE_URL` — Railway fornece `postgresql://user:pass@host:port/db`. Voce DEVE mudar para `postgresql+asyncpg://user:pass@host:port/db` (adicionar `+asyncpg`). Sem isso o deploy quebra.
   - `JWT_SECRET` — gerar com `openssl rand -hex 32`. OBRIGATORIO. Sem isso cada restart invalida todos os tokens.
3. Conectar repo GitHub e fazer deploy
