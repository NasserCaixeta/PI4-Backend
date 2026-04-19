# Railway Deploy Fixes — Design Spec

## Goal

Make the Camelbox backend deployable on Railway (PostgreSQL) with login/register endpoints working. Dashboard data will be mocked on the frontend. Deadline: 2026-04-20.

## Scope

Minimum viable fixes only — 4 files, no new features, no refactoring beyond what's required.

## Changes

### 1. `app/database.py` — Replace SQLite-specific insert

**Problem:** `seed_default_categories()` uses `from sqlalchemy.dialects.sqlite import insert as sqlite_insert` which crashes on PostgreSQL.

**Fix:** Replace `sqlite_insert(Category).values(...)` with `db.add(Category(...))`. The existing `select` + `if not existing` check already prevents duplicates, so no extra logic needed.

### 2. `tests/conftest.py` — Same SQLite insert fix

**Problem:** Test setup uses `sqlite_insert` and `on_conflict_do_nothing()` to seed categories.

**Fix:** Replace with `db.add(Category(...))`. Since tests create the database from scratch in memory, there are no conflicts — `on_conflict_do_nothing` was unnecessary.

### 3. `app/main.py` — Add CORS middleware

**Problem:** No CORS middleware. Frontend on Cloudflare Pages (different origin) will be blocked by browser CORS policy.

**Fix:** Add `CORSMiddleware` with:
- `allow_origins=["*"]` (tighten later when Cloudflare Pages domain is known)
- `allow_methods=["*"]`
- `allow_headers=["*"]`
- `allow_credentials=True`

**Nota:** `allow_origins=["*"]` + `allow_credentials=True` e tecnicamente conflitante pela spec HTTP, mas o Starlette resolve refletindo a origem da request. Aceitavel pro MVP; trocar `*` pela URL do Cloudflare Pages quando disponivel.

### 4. `Procfile` — Create deployment config

**Problem:** Railway doesn't know how to start the app.

**Fix:** Create `Procfile` with:
```
web: alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

This runs migrations on every deploy before starting the server, and uses Railway's dynamic `$PORT`.

## Railway Setup (manual steps after deploy)

1. Add PostgreSQL addon in Railway dashboard
2. Set environment variables:
   - `DATABASE_URL` — **ATENCION:** Railway fornece a URL no formato `postgresql://user:pass@host:port/db`, mas este projeto usa driver async. Você DEVE transformar para `postgresql+asyncpg://user:pass@host:port/db` (adicionar `+asyncpg` após `postgresql`). Sem isso, o deploy quebra.
   - `JWT_SECRET` — **OBRIGATORIO.** Gere com `openssl rand -hex 32`. Sem isso, cada restart invalida todos os tokens dos usuarios.
3. Connect GitHub repo and deploy

## Out of Scope

- Celery/Redis setup (no statement processing needed yet)
- Gemini API integration
- Stripe/payments
- JWT_SECRET validation enforcement
- `datetime.utcnow()` deprecation fix
- Health check HTTP status code improvement
- Dockerization

## Frontend Architecture

- Hosted on Cloudflare Pages (default `.pages.dev` domain)
- Calls backend via `VITE_API_URL` env var pointing to Railway URL
- Dashboard data mocked on frontend for now

## Testing

- Tests continue running with SQLite in-memory (no change to test infrastructure)
- Only the seed logic changes to be database-agnostic
- Rodar `pytest` apos as mudancas para confirmar que nada quebrou
