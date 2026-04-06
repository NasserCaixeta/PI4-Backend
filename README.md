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
