param(
    [switch]$Apply
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "NEXUS - Importacao do sistema legado" -ForegroundColor Cyan
Write-Host "Banco banco_equipamentos.db: IGNORADO por decisao do projeto." -ForegroundColor Yellow
Write-Host "Banco banco_estoque.db: arquivo mantido, mas sem registros relevantes para importar." -ForegroundColor Yellow

$required = @(
    "legacy_data\banco_laboratorio.db",
    "legacy_data\banco_automacao.db",
    "legacy_data\banco_empresa.db",
    "legacy_data\banco_compras.db",
    "legacy_data\banco_solucoes.db"
)

foreach ($file in $required) {
    if (-not (Test-Path $file)) {
        throw "Arquivo obrigatorio nao encontrado: $file"
    }
}

Write-Host "`n1/3 Subindo PostgreSQL e API..." -ForegroundColor Cyan
docker compose up -d db api
if ($LASTEXITCODE -ne 0) { throw "Falha ao iniciar db/api via Docker Compose." }

Write-Host "`n2/3 Atualizando schema do PostgreSQL..." -ForegroundColor Cyan
docker compose exec api alembic upgrade head
if ($LASTEXITCODE -ne 0) { throw "Falha ao executar Alembic." }

if ($Apply) {
    Write-Host "`n3/3 IMPORTACAO REAL iniciada..." -ForegroundColor Red
    docker compose exec api python scripts/import_legacy_sqlite.py --source-dir /legacy --apply
    if ($LASTEXITCODE -ne 0) { throw "Importacao REAL falhou. Nenhum sucesso deve ser assumido; confira o erro acima." }
} else {
    Write-Host "`n3/3 DRY-RUN iniciado. Nenhum dado sera gravado..." -ForegroundColor Green
    docker compose exec api python scripts/import_legacy_sqlite.py --source-dir /legacy
    if ($LASTEXITCODE -ne 0) { throw "DRY-RUN falhou. NAO execute -Apply; confira o erro acima." }
    Write-Host "`nDRY-RUN concluido com sucesso. Confira o resumo acima." -ForegroundColor Green
    Write-Host "Para importar de verdade, execute:" -ForegroundColor Cyan
    Write-Host ".\scripts\import_legacy_local.ps1 -Apply" -ForegroundColor White
}
