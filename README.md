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

Celery worker code exists under `app/workers`, but the current production flow does not enqueue those tasks. Upload processing and feedback generation run synchronously through the FastAPI routers.

Celery integration is planned as a separate feature for VPS deployment, with API job enqueueing, worker process management, Redis/broker configuration, persisted status, and observability handled together.
