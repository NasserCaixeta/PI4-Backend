# Production deployment

The backend image is built by GitHub Actions and published to GHCR with the
full commit SHA as its immutable tag. Production never builds application code
on the VPS.

The VPS deployment command validates the requested SHA, serializes frontend
and backend releases with `flock`, runs Alembic once, waits for container health
checks, and restores the previous application image when startup fails.

Runtime secrets remain in `/opt/camelbox/.env`. They are never copied into the
image or stored in GitHub Actions.

PostgreSQL and Redis continue to be owned by the existing `camelbox` Compose
project and retain their named volumes. `docker-compose.prod.yml` updates only
the API and Celery services on the external `camelbox-network` network.
