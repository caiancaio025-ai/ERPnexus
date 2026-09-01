param(
    [string]$ComposeFile = "docker-compose.yml",
    [string]$EnvFile = "",
    [string]$BackupRoot = "backups",
    [int]$RetentionDays = 0
)

$ErrorActionPreference = "Stop"

function Assert-NativeSuccess {
    param(
        [Parameter(Mandatory)]
        [string]$Operation
    )

    if ($LASTEXITCODE -ne 0) {
        throw "$Operation falhou. Exit code: $LASTEXITCODE"
    }
}

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

if (-not [System.IO.Path]::IsPathRooted($ComposeFile)) {
    $ComposeFile = Join-Path $RepoRoot $ComposeFile
}

if (-not (Test-Path -LiteralPath $ComposeFile)) {
    throw "Compose nao encontrado: $ComposeFile"
}

if (-not [System.IO.Path]::IsPathRooted($BackupRoot)) {
    $BackupRoot = Join-Path $RepoRoot $BackupRoot
}

New-Item -ItemType Directory -Path $BackupRoot -Force | Out-Null

$ComposeArgs = @(
    "compose",
    "-f", $ComposeFile
)

if (-not [string]::IsNullOrWhiteSpace($EnvFile)) {

    if (-not [System.IO.Path]::IsPathRooted($EnvFile)) {
        $EnvFile = Join-Path $RepoRoot $EnvFile
    }

    if (-not (Test-Path -LiteralPath $EnvFile)) {
        throw "Env file nao encontrado: $EnvFile"
    }

    $ComposeArgs += @("--env-file", $EnvFile)
}

Write-Host ""
Write-Host "=== NEXUS BACKUP ==="

$dbContainerRaw = & docker @ComposeArgs ps -q db
Assert-NativeSuccess "Localizacao do container PostgreSQL"

$dbContainer = ($dbContainerRaw | Out-String).Trim()

if ([string]::IsNullOrWhiteSpace($dbContainer)) {
    throw "Container PostgreSQL nao encontrado."
}

$apiContainerRaw = & docker @ComposeArgs ps -q api
Assert-NativeSuccess "Localizacao do container API"

$apiContainer = ($apiContainerRaw | Out-String).Trim()

if ([string]::IsNullOrWhiteSpace($apiContainer)) {
    throw "Container API nao encontrado."
}

Write-Host ""
Write-Host "=== IDENTIDADE DO BANCO ==="

$dbUserRaw = & docker @ComposeArgs exec -T db printenv POSTGRES_USER
Assert-NativeSuccess "Leitura de POSTGRES_USER"

$dbNameRaw = & docker @ComposeArgs exec -T db printenv POSTGRES_DB
Assert-NativeSuccess "Leitura de POSTGRES_DB"

$dbUser = ($dbUserRaw | Out-String).Trim()
$dbName = ($dbNameRaw | Out-String).Trim()

if ([string]::IsNullOrWhiteSpace($dbUser)) {
    throw "POSTGRES_USER vazio."
}

if ([string]::IsNullOrWhiteSpace($dbName)) {
    throw "POSTGRES_DB vazio."
}

Write-Host "Database: $dbName"
Write-Host "Usuario:  $dbUser"

$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupDir = Join-Path $BackupRoot "nexus_backup_$Timestamp"

New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null

$DbFile = Join-Path $BackupDir "nexus.dump"
$UploadsFile = Join-Path $BackupDir "uploads.tar.gz"
$ManifestFile = Join-Path $BackupDir "manifest.json"

Write-Host "Destino:  $BackupDir"

try {

    Write-Host ""
    Write-Host "=== DUMP POSTGRES ==="

    & docker @ComposeArgs exec -T db `
        pg_dump `
        -U $dbUser `
        -d $dbName `
        -Fc `
        -f /tmp/nexus_backup.dump

    Assert-NativeSuccess "pg_dump"

    & docker cp `
        "${dbContainer}:/tmp/nexus_backup.dump" `
        $DbFile

    Assert-NativeSuccess "Copia do dump"

    & docker @ComposeArgs exec -T db `
        rm -f /tmp/nexus_backup.dump

    Assert-NativeSuccess "Limpeza do dump temporario"

    if (-not (Test-Path -LiteralPath $DbFile)) {
        throw "Dump nao foi criado no host."
    }

    if ((Get-Item $DbFile).Length -le 0) {
        throw "Dump criado com tamanho zero."
    }

    Write-Host ""
    Write-Host "=== VOLUME DE UPLOADS ==="

    $apiInspectRaw = & docker inspect $apiContainer
    Assert-NativeSuccess "docker inspect da API"

    $apiInspect = $apiInspectRaw | ConvertFrom-Json

    $storageMount = $apiInspect[0].Mounts |
        Where-Object { $_.Destination -eq "/app/storage" } |
        Select-Object -First 1

    if ($null -eq $storageMount) {
        throw "Mount /app/storage nao encontrado."
    }

    if ([string]::IsNullOrWhiteSpace($storageMount.Name)) {
        throw "Volume nomeado de /app/storage nao encontrado."
    }

    $uploadsVolume = $storageMount.Name

    Write-Host "Volume: $uploadsVolume"

    Write-Host ""
    Write-Host "=== BACKUP DOS UPLOADS ==="

    & docker run --rm `
        -v "${uploadsVolume}:/source:ro" `
        -v "${BackupDir}:/backup" `
        alpine:3.22 `
        tar -czf /backup/uploads.tar.gz -C /source .

    Assert-NativeSuccess "Backup dos uploads"

    if (-not (Test-Path -LiteralPath $UploadsFile)) {
        throw "uploads.tar.gz nao foi criado."
    }

    if ((Get-Item $UploadsFile).Length -le 0) {
        throw "uploads.tar.gz criado com tamanho zero."
    }

    Write-Host ""
    Write-Host "=== VALIDAR DUMP ==="

    & docker run --rm `
        --mount "type=bind,source=$DbFile,target=/backup/nexus.dump,readonly" `
        postgres:17-alpine `
        pg_restore --list /backup/nexus.dump |
        Out-Null

    Assert-NativeSuccess "Validacao pg_restore"

    Write-Host "DUMP: OK"

    Write-Host ""
    Write-Host "=== VALIDAR UPLOADS ==="

    $TarEntries = @(
        & docker run --rm `
            --mount "type=bind,source=$UploadsFile,target=/backup/uploads.tar.gz,readonly" `
            alpine:3.22 `
            tar -tzf /backup/uploads.tar.gz
    )

    Assert-NativeSuccess "Validacao uploads.tar.gz"

    $TarFiles = @(
        $TarEntries |
        Where-Object {
            -not [string]::IsNullOrWhiteSpace($_) -and
            -not $_.EndsWith("/")
        }
    )

    Write-Host "Arquivos no TAR: $($TarFiles.Count)"

    Write-Host ""
    Write-Host "=== CONTAR UPLOADS ORIGINAIS ==="

    $SourceFiles = @(
        & docker run --rm `
            -v "${uploadsVolume}:/source:ro" `
            alpine:3.22 `
            find /source -type f
    )

    Assert-NativeSuccess "Contagem dos uploads originais"

    $SourceFiles = @(
        $SourceFiles |
        Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
    )

    Write-Host "Arquivos na origem: $($SourceFiles.Count)"

    if ($SourceFiles.Count -ne $TarFiles.Count) {
        throw "Contagem de uploads divergente: origem=$($SourceFiles.Count), tar=$($TarFiles.Count)"
    }

    Write-Host ""
    Write-Host "=== CHECKSUMS ==="

    $dbHash = (Get-FileHash $DbFile -Algorithm SHA256).Hash
    $uploadsHash = (Get-FileHash $UploadsFile -Algorithm SHA256).Hash

    $manifest = [ordered]@{
        format_version = 1
        created_at = (Get-Date).ToString("o")
        database = $dbName
        database_user = $dbUser

        postgres_dump = [ordered]@{
            filename = "nexus.dump"
            sha256 = $dbHash
            bytes = (Get-Item $DbFile).Length
        }

        uploads = [ordered]@{
            filename = "uploads.tar.gz"
            sha256 = $uploadsHash
            bytes = (Get-Item $UploadsFile).Length
            files = $TarFiles.Count
        }
    }

    $manifestJson = $manifest | ConvertTo-Json -Depth 10

    [System.IO.File]::WriteAllText(
        $ManifestFile,
        $manifestJson,
        (New-Object System.Text.UTF8Encoding($false))
    )

    if ($RetentionDays -gt 0) {

        Write-Host ""
        Write-Host "=== RETENCAO: $RetentionDays DIAS ==="

        $Cutoff = (Get-Date).AddDays(-$RetentionDays)

        Get-ChildItem -LiteralPath $BackupRoot -Directory |
            Where-Object {
                $_.Name -like "nexus_backup_*" -and
                $_.LastWriteTime -lt $Cutoff -and
                $_.FullName -ne $BackupDir
            } |
            ForEach-Object {
                Write-Host "Removendo backup expirado: $($_.FullName)"
                Remove-Item -LiteralPath $_.FullName -Recurse -Force
            }
    }

    Write-Host ""
    Write-Host "=== RESULTADO ==="
    Write-Host "BACKUP VALIDADO COM SUCESSO"
    Write-Host "Dump:     $DbFile"
    Write-Host "Uploads:  $UploadsFile"
    Write-Host "Manifest: $ManifestFile"
    Write-Host "Arquivos: $($TarFiles.Count)"
}
catch {

    Write-Host ""
    Write-Host "=== BACKUP FALHOU ==="
    Write-Host $_.Exception.Message

    throw
}
finally {

    & docker @ComposeArgs exec -T db `
        rm -f /tmp/nexus_backup.dump 2>$null
}