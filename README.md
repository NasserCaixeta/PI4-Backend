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

## Background Jobs

Celery processes statement PDFs outside the FastAPI request cycle. The API accepts the upload, stores a `BankStatement` with `status="processing"`, enqueues a task, and returns immediately. The worker later updates the statement to `completed` or `error`.

Run Redis locally:

```bash
redis-server
```

Run the API:

```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Run the worker:

```bash
uv run celery -A app.workers.celery_app.celery_app worker --loglevel=info
```

Required environment variables for VPS deployment include `DATABASE_URL`, `REDIS_URL`, `JWT_SECRET`, `APP_ENV=production`, `GEMINI_API_KEY`, `GEMINI_MODEL`, and the existing Stripe variables.

Feedback generation still runs synchronously in this phase. It will move to Celery in a separate phase using the same status pattern.
