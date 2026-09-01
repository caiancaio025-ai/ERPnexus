param(
    [string]$ComposeFile = "docker-compose.yml",
    [string]$EnvFile = "",
    [string]$BackupDir = ""
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

if ([string]::IsNullOrWhiteSpace($BackupDir)) {

    $BackupRoot = Join-Path $RepoRoot "backups"

    $Latest = Get-ChildItem `
        -LiteralPath $BackupRoot `
        -Directory `
        -Filter "nexus_backup_*" |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1

    if ($null -eq $Latest) {
        throw "Nenhum backup nexus_backup_* encontrado."
    }

    $BackupDir = $Latest.FullName
}
elseif (-not [System.IO.Path]::IsPathRooted($BackupDir)) {
    $BackupDir = Join-Path $RepoRoot $BackupDir
}

if (-not (Test-Path -LiteralPath $BackupDir)) {
    throw "Backup nao encontrado: $BackupDir"
}

$DbFile = Join-Path $BackupDir "nexus.dump"
$UploadsFile = Join-Path $BackupDir "uploads.tar.gz"
$ManifestFile = Join-Path $BackupDir "manifest.json"

foreach ($File in @($DbFile, $UploadsFile, $ManifestFile)) {
    if (-not (Test-Path -LiteralPath $File)) {
        throw "Arquivo obrigatorio ausente: $File"
    }
}

Write-Host ""
Write-Host "=== NEXUS VERIFY RESTORE ==="
Write-Host "Backup: $BackupDir"

Write-Host ""
Write-Host "=== MANIFEST / CHECKSUMS ==="

$Manifest = Get-Content `
    -LiteralPath $ManifestFile `
    -Raw |
    ConvertFrom-Json

if ($Manifest.format_version -ne 1) {
    throw "Versao de manifest nao suportada: $($Manifest.format_version)"
}

$DbHash = (Get-FileHash $DbFile -Algorithm SHA256).Hash
$UploadsHash = (Get-FileHash $UploadsFile -Algorithm SHA256).Hash

if ($DbHash -ne $Manifest.postgres_dump.sha256) {
    throw "SHA256 do dump divergente."
}

if ($UploadsHash -ne $Manifest.uploads.sha256) {
    throw "SHA256 dos uploads divergente."
}

if ((Get-Item $DbFile).Length -ne [long]$Manifest.postgres_dump.bytes) {
    throw "Tamanho do dump divergente."
}

if ((Get-Item $UploadsFile).Length -ne [long]$Manifest.uploads.bytes) {
    throw "Tamanho do arquivo de uploads divergente."
}

Write-Host "CHECKSUM DUMP: OK"
Write-Host "CHECKSUM UPLOADS: OK"

Write-Host ""
Write-Host "=== VALIDAR ARQUIVOS ==="

& docker run --rm `
    --mount "type=bind,source=$DbFile,target=/backup/nexus.dump,readonly" `
    postgres:17-alpine `
    pg_restore --list /backup/nexus.dump |
    Out-Null

Assert-NativeSuccess "pg_restore --list"

$TarEntries = @(
    & docker run --rm `
        --mount "type=bind,source=$UploadsFile,target=/backup/uploads.tar.gz,readonly" `
        alpine:3.22 `
        tar -tzf /backup/uploads.tar.gz
)

Assert-NativeSuccess "Validacao do TAR"

$TarFiles = @(
    $TarEntries |
    Where-Object {
        -not [string]::IsNullOrWhiteSpace($_) -and
        -not $_.EndsWith("/")
    }
)

Write-Host "Arquivos no TAR: $($TarFiles.Count)"

if ($TarFiles.Count -ne [int]$Manifest.uploads.files) {
    throw "Quantidade de uploads divergente do manifest."
}

Write-Host ""
Write-Host "=== IDENTIFICAR POSTGRES ==="

$dbContainerRaw = & docker @ComposeArgs ps -q db
Assert-NativeSuccess "Localizacao do PostgreSQL"

$dbContainer = ($dbContainerRaw | Out-String).Trim()

if ([string]::IsNullOrWhiteSpace($dbContainer)) {
    throw "Container PostgreSQL nao encontrado."
}

$dbUserRaw = & docker @ComposeArgs exec -T db printenv POSTGRES_USER
Assert-NativeSuccess "Leitura POSTGRES_USER"

$dbNameRaw = & docker @ComposeArgs exec -T db printenv POSTGRES_DB
Assert-NativeSuccess "Leitura POSTGRES_DB"

$dbUser = ($dbUserRaw | Out-String).Trim()
$dbName = ($dbNameRaw | Out-String).Trim()

if ([string]::IsNullOrWhiteSpace($dbUser)) {
    throw "POSTGRES_USER vazio."
}

if ([string]::IsNullOrWhiteSpace($dbName)) {
    throw "POSTGRES_DB vazio."
}

Write-Host "Original: $dbName"

$RestoreDb = "nexus_restore_verify_" + (Get-Date -Format "yyyyMMdd_HHmmss")
$TempDump = "/tmp/nexus_verify_restore.dump"

$RestoreCreated = $false

try {

    Write-Host ""
    Write-Host "=== CRIAR BANCO TEMPORARIO ==="
    Write-Host "Temporario: $RestoreDb"

    & docker @ComposeArgs exec -T db `
        psql `
        -U $dbUser `
        -d postgres `
        -v ON_ERROR_STOP=1 `
        -c "CREATE DATABASE $RestoreDb;"

    Assert-NativeSuccess "Criacao do banco temporario"

    $RestoreCreated = $true

    Write-Host ""
    Write-Host "=== COPIAR DUMP ==="

    & docker cp `
        $DbFile `
        "${dbContainer}:${TempDump}"

    Assert-NativeSuccess "Copia do dump para PostgreSQL"

    Write-Host ""
    Write-Host "=== RESTAURAR ==="

    & docker @ComposeArgs exec -T db `
        pg_restore `
        -U $dbUser `
        -d $RestoreDb `
        --no-owner `
        --no-privileges `
        --exit-on-error `
        $TempDump

    Assert-NativeSuccess "Restore PostgreSQL"

    Write-Host "RESTORE: OK"

    Write-Host ""
    Write-Host "=== COMPARAR ALEMBIC ==="

    $OriginalAlembicRaw = & docker @ComposeArgs exec -T db `
        psql -U $dbUser -d $dbName -Atc `
        "select version_num from alembic_version;"

    Assert-NativeSuccess "Alembic original"

    $RestoredAlembicRaw = & docker @ComposeArgs exec -T db `
        psql -U $dbUser -d $RestoreDb -Atc `
        "select version_num from alembic_version;"

    Assert-NativeSuccess "Alembic restaurado"

    $OriginalAlembic = ($OriginalAlembicRaw | Out-String).Trim()
    $RestoredAlembic = ($RestoredAlembicRaw | Out-String).Trim()

    Write-Host "Original  : $OriginalAlembic"
    Write-Host "Restaurado: $RestoredAlembic"

    if ($OriginalAlembic -ne $RestoredAlembic) {
        throw "Alembic divergente."
    }

    Write-Host ""
    Write-Host "=== LISTAR TABELAS ==="

    $Tables = @(
        & docker @ComposeArgs exec -T db `
            psql -U $dbUser -d $dbName -Atc `
            "select tablename from pg_tables where schemaname='public' order by tablename;"
    )

    Assert-NativeSuccess "Listagem das tabelas"

    $Tables = @(
        $Tables |
        Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
    )

    Write-Host "Tabelas encontradas: $($Tables.Count)"

    $RestoredTableCountRaw = & docker @ComposeArgs exec -T db `
        psql -U $dbUser -d $RestoreDb -Atc `
        "select count(*) from pg_tables where schemaname='public';"

    Assert-NativeSuccess "Contagem de tabelas restauradas"

    $RestoredTableCount = [int](($RestoredTableCountRaw | Out-String).Trim())

    if ($RestoredTableCount -ne $Tables.Count) {
        throw "Quantidade de tabelas divergente: original=$($Tables.Count), restaurado=$RestoredTableCount"
    }

    Write-Host ""
    Write-Host "=== COMPARAR CONTAGENS ==="

    $Divergences = @()

    foreach ($Table in $Tables) {

        $SafeTable = '"' + $Table.Replace('"', '""') + '"'

        $OriginalCountRaw = & docker @ComposeArgs exec -T db `
            psql -U $dbUser -d $dbName -Atc `
            "select count(*) from public.$SafeTable;"

        Assert-NativeSuccess "Contagem original: $Table"

        $RestoredCountRaw = & docker @ComposeArgs exec -T db `
            psql -U $dbUser -d $RestoreDb -Atc `
            "select count(*) from public.$SafeTable;"

        Assert-NativeSuccess "Contagem restaurada: $Table"

        $OriginalCount = (($OriginalCountRaw | Out-String).Trim())
        $RestoredCount = (($RestoredCountRaw | Out-String).Trim())

        Write-Host "$Table -> ORIGINAL=$OriginalCount RESTAURADO=$RestoredCount"

        if ($OriginalCount -ne $RestoredCount) {
            $Divergences += "$Table original=$OriginalCount restaurado=$RestoredCount"
        }
    }

    if ($Divergences.Count -gt 0) {

        Write-Host ""
        Write-Host "=== DIVERGENCIAS ==="

        $Divergences |
            ForEach-Object { Write-Host $_ }

        throw "Restore possui divergencias."
    }

    Write-Host ""
    Write-Host "=== RESULTADO ==="
    Write-Host "VERIFY RESTORE: OK"
    Write-Host "ALEMBIC: OK"
    Write-Host "TABELAS: $($Tables.Count)"
    Write-Host "CONTAGENS: OK"
    Write-Host "UPLOADS: $($TarFiles.Count)"
}
finally {

    Write-Host ""
    Write-Host "=== LIMPEZA ==="

    & docker @ComposeArgs exec -T db `
        rm -f $TempDump 2>$null

    if ($RestoreCreated) {

        & docker @ComposeArgs exec -T db `
            psql `
            -U $dbUser `
            -d postgres `
            -c "DROP DATABASE IF EXISTS $RestoreDb WITH (FORCE);" `
            2>$null

        if ($LASTEXITCODE -eq 0) {
            Write-Host "Banco temporario removido: OK"
        }
        else {
            Write-Warning "Nao foi possivel remover automaticamente: $RestoreDb"
        }
    }
}