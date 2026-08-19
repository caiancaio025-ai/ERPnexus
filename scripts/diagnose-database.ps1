[CmdletBinding()]
param(
    [int]$Samples = 3,
    [int]$TimeoutSeconds = 5
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$apiRoot = Join-Path $projectRoot "apps\api"

function Write-Step([string]$Message) {
    Write-Host "`n=== $Message ===" -ForegroundColor Cyan
}

Set-Location $projectRoot

Write-Step "Estado dos containers"
docker compose ps

$dbContainer = docker compose ps -q db
if (-not $dbContainer) {
    throw "O container do PostgreSQL não está em execução. Rode: docker compose up -d db"
}

Write-Step "SELECT 1 dentro do container"
$insideContainer = Measure-Command {
    docker compose exec -T db sh -lc 'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB" && psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -c "SELECT 1;"'
}
Write-Host ("Tempo interno do container: {0:N3}s" -f $insideContainer.TotalSeconds)

Write-Step "Teste da porta publicada no Windows"
$envFile = Join-Path $projectRoot ".env"
$port = 5433
if (Test-Path $envFile) {
    $portLine = Get-Content $envFile | Where-Object { $_ -match '^POSTGRES_PORT=' } | Select-Object -First 1
    if ($portLine) {
        $port = [int](($portLine -split '=', 2)[1].Trim())
    }
}

$tcp = Measure-Command {
    $reachable = Test-NetConnection 127.0.0.1 -Port $port -InformationLevel Quiet
}
Write-Host "Porta 127.0.0.1:$port acessível: $reachable"
Write-Host ("Tempo do Test-NetConnection: {0:N3}s" -f $tcp.TotalSeconds)

if (-not $reachable) {
    throw "A porta PostgreSQL publicada pelo Docker não está acessível."
}

Write-Step "Diagnóstico direto do Psycopg"
Set-Location $apiRoot
python scripts\diagnose_psycopg.py --samples $Samples --timeout $TimeoutSeconds

Write-Step "Teste funcional do pool"
python -m pytest tests\test_database_pool.py -v -s -m "not performance"

Write-Host "`nDiagnóstico concluído." -ForegroundColor Green
