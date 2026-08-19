$ErrorActionPreference = "Stop"
docker compose ps
docker compose exec api ruff check .
docker compose exec api mypy app
docker compose exec api pytest
