$ErrorActionPreference = "Stop"
$scriptPath = Join-Path $PSScriptRoot "verify_finance_qa.sql"
Get-Content -Raw $scriptPath |
  docker compose exec -T db sh -lc 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
