$ErrorActionPreference = "Stop"
$root = (Resolve-Path "$PSScriptRoot\..").Path

Push-Location $root
try {
    docker info | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Docker Desktop não está pronto. Aguarde o Engine ficar em execução."
    }

    docker compose up -d --build
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    docker compose ps
    Write-Host "ERP:  http://localhost:5173"
    Write-Host "API:  http://localhost:8000/docs"
    Write-Host "Site: http://localhost:4321"
}
finally {
    Pop-Location
}
