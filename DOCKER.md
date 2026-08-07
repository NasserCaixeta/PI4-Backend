# Docker

FastAPI and Celery use the same application image. Compose changes only the
command used by each service, while Postgres and Redis remain separate services.

## Run locally

```bash
cp .env.docker.example .env
docker compose up --build
```

API: `http://localhost:8000`

Health check:

```bash
curl http://localhost:8000/health
```

## Services

- `api`: runs migrations and starts `uvicorn app.main:app` in local development.
- `celery_worker`: starts `celery -A app.workers.celery_app:celery_app worker`.
- `postgres`: local PostgreSQL 16.
- `redis`: local Redis 7 broker/result backend.

## Production notes

Production uses an immutable image created by GitHub Actions. Set the full
commit SHA as `BACKEND_TAG`, keep the runtime secrets in `.env`, and run:

```bash
BACKEND_TAG=<full-commit-sha> docker compose -f docker-compose.prod.yml up -d
```

Alembic is executed once by the production deployment script before API and
Celery are updated. See `deploy/README.md` for the VPS workflow.

Set `APP_ENV=production`, provide strong `JWT_SECRET` and
`DATA_ENCRYPTION_KEY` values, and configure the real `DATABASE_URL` and
`REDIS_URL` in `.env`. The default `docker-compose.yml` remains intended for
local development.
