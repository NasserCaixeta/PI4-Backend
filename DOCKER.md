# Docker

This setup follows the same split used by `wps-ai-infra`: one image for FastAPI and one image for the Celery worker, with Postgres and Redis provided by Compose.

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

- `api`: runs migrations and starts `uvicorn app.main:app`.
- `celery_worker`: starts `celery -A app.workers.celery_app:celery_app worker`.
- `postgres`: local PostgreSQL 16.
- `redis`: local Redis 7 broker/result backend.

## Production notes

For external Postgres and Redis:

```bash
docker compose -f docker-compose.prod.yml up --build
```

Set `APP_ENV=production`, provide a strong `JWT_SECRET`, and configure the real `DATABASE_URL` and `REDIS_URL` in `.env`. The default `docker-compose.yml` is meant for local execution and always points the app containers at the Compose Postgres and Redis services.
