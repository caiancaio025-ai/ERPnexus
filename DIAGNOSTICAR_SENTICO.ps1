#Requires -Version 5.1
# Diagnostico somente leitura, sem imprimir senha ou arquivo .env.
$ErrorActionPreference='Continue'
Write-Host '=== VERSAO E CONEXAO DA API ===' -ForegroundColor Cyan
foreach ($endpoint in @('version','ready')) {
    try {
        $relogio=[System.Diagnostics.Stopwatch]::StartNew()
        $resposta=Invoke-RestMethod -Uri "http://127.0.0.1:5184/api/health/$endpoint" -TimeoutSec 12
        $relogio.Stop()
        if ($endpoint -eq 'version') {
            Write-Host "SENTICO_VERSAO=$($resposta.version) DATA=$($resposta.release_date)"
        } else { Write-Host "API_BANCO=$($resposta.status) TEMPO_MS=$($relogio.ElapsedMilliseconds)" }
    } catch { Write-Host "HTTP_DIAGNOSTICO_FALHOU=$endpoint" -ForegroundColor Yellow }
}
Write-Host '=== REINICIOS E MEMORIA DOS CONTAINERS ===' -ForegroundColor Cyan
$todos=@(& docker.exe ps -a --filter 'label=com.docker.compose.project=sentico-v14-recuperado' --format '{{.ID}}' 2>$null)
foreach ($container in $todos) {
    if ($container -match '^[a-fA-F0-9]{12,64}$') {
        & docker.exe inspect --format '{{.Name}} restart_count={{.RestartCount}} oom={{.State.OOMKilled}} status={{.State.Status}}' $container 2>$null
    }
}
Write-Host '=== CONTAINERS DO PROJETO SENTICO ===' -ForegroundColor Cyan
& docker.exe ps -a --filter 'label=com.docker.compose.project=sentico-v14-recuperado' --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
$db=@(& docker.exe ps -a --filter 'label=com.docker.compose.project=sentico-v14-recuperado' --filter 'label=com.docker.compose.service=db' --format '{{.ID}}' 2>$null)
$db=@($db | Where-Object { $_ -match '^[a-fA-F0-9]{12,64}$' })
if ($db.Count -ne 1) {
    Write-Host 'DB_SENTICO_NAO_LOCALIZADO_OU_AMBIGUO'
    exit 0
}
Write-Host '=== VOLUMES REALMENTE MONTADOS (NOMES DINAMICOS) ===' -ForegroundColor Cyan
$inspecao=@(& docker.exe inspect --format '{{json .Mounts}}' $db[0] 2>$null)
try {
    $mounts=($inspecao -join '') | ConvertFrom-Json
    foreach ($m in @($mounts)) { if ($m.Type -eq 'volume') { Write-Host "$($m.Name) -> $($m.Destination)" } }
} catch { Write-Host 'FALHA_CONSULTA_MOUNTS' }
Write-Host '=== BANCOS DO POSTGRESQL ===' -ForegroundColor Cyan
$running=@(& docker.exe inspect --format '{{.State.Running}}' $db[0] 2>$null)
if ($running -contains 'true') {
    # Senha apenas no ambiente do container; nenhum segredo enviado ao PowerShell.
    & docker.exe exec $db[0] sh -c 'PGPASSWORD="$POSTGRES_PASSWORD" psql -w -X -qAt -h 127.0.0.1 -U "$POSTGRES_USER" -d postgres -c "SELECT datname FROM pg_database WHERE datallowconn AND NOT datistemplate ORDER BY datname;"' 2>$null
    if ($LASTEXITCODE -ne 0) { Write-Host 'FALHA_LEITURA_CATALOGO_SEM_EXIBIR_CREDENCIAIS' }
} else { Write-Host 'DB_SENTICO_NAO_INICIADO' }
Write-Host 'Nenhum volume ou registro foi alterado.'
