#Requires -Version 5.1
[CmdletBinding()]
param([string]$ProjectDir = (Join-Path $PSScriptRoot 'codigo-fonte'))
$ErrorActionPreference = 'Stop'
function DockerSeguro {
    param([string[]]$Comando)
    $old = $ErrorActionPreference
    try {
        $ErrorActionPreference='Continue'
        $out = @(& docker @Comando 2>$null)
        $rc = $LASTEXITCODE
    } finally { $ErrorActionPreference=$old }
    return @{ Out=$out; Code=$rc }
}
try {
    Write-Host "`n=== DIAGNOSTICO DO POSTGRESQL SENTICO (SOMENTE LEITURA) ===" -ForegroundColor Cyan
    $dir = (Resolve-Path -LiteralPath $ProjectDir -ErrorAction Stop).Path
    if (-not (Test-Path (Join-Path $dir 'compose.dev.yml'))) { throw 'compose.dev.yml ausente.' }
    if (-not (Test-Path (Join-Path $dir '.env.dev'))) { throw '.env.dev ausente. Nao gere outra senha no volume existente.' }
    $check = DockerSeguro -Comando @('info','--format','{{.OSType}}')
    if ($check.Code -ne 0 -or (($check.Out -join '') -ne 'linux')) { throw 'Docker Desktop Linux indisponivel.' }
    $ctx = DockerSeguro -Comando @('context','inspect','--format','{{json .Endpoints}}')
    if ($ctx.Code -ne 0 -or @($ctx.Out).Count -ne 1) { throw 'Contexto Docker nao verificado.' }
    $endpoint = ($ctx.Out[0] | ConvertFrom-Json).docker.Host
    if ($endpoint -notmatch '^npipe:') { throw 'Nao executar no Docker remoto. Este diagnostico e local.' }
    Push-Location -LiteralPath $dir
    try {
        $db = DockerSeguro -Comando @('compose','--env-file','.env.dev','-f','compose.dev.yml','ps','-q','db')
        if ($db.Code -ne 0 -or @($db.Out).Count -ne 1 -or [string]::IsNullOrWhiteSpace([string]$db.Out[0])) {
            throw 'Container db nao encontrado. Abra Docker Desktop e inicie o instalador ate a etapa do banco.'
        }
        $id = [string]$db.Out[0]
        $label = DockerSeguro -Comando @('inspect','--format','{{json .Config.Labels}}',$id)
        if ($label.Code -ne 0) { throw 'Nao foi possivel identificar o projeto Docker.' }
        $labelJson = ($label.Out -join '') | ConvertFrom-Json
        if ($labelJson.'com.docker.compose.project' -ne 'sentico-dev-entrega' -or $labelJson.'com.docker.compose.service' -ne 'db') { throw 'Container nao pertence ao projeto/servico esperado.' }
        $mounts = DockerSeguro -Comando @('inspect','--format','{{json .Mounts}}',$id)
        if ($mounts.Code -ne 0) { throw 'Nao foi possivel inspecionar os volumes.' }
        $mountList = @((($mounts.Out -join '') | ConvertFrom-Json) | Where-Object { $_.Destination -eq '/var/lib/postgresql/data' })
        if ($mountList.Count -ne 1 -or [string]::IsNullOrWhiteSpace([string]$mountList[0].Name)) { throw 'Volume PostgreSQL ausente ou ambiguo.' }
        Write-Host ('VOLUME_POSTGRES=' + $mountList[0].Name)
        Write-Host 'DADOS_NAO_ALTERADOS=SIM'
        $ready = DockerSeguro -Comando @('exec',$id,'pg_isready','-q','-h','127.0.0.1')
        if ($ready.Code -ne 0) { throw 'PostgreSQL ainda nao esta pronto; verificar logs do banco sem excluir volumes.' }
        # Apenas conexoes locais por socket; nao imprimir nem solicitar senhas.
        $found = $false
        foreach ($candidate in @('sentico_dev','postgres','sentico','nexus','sentico_green','sentico_local')) {
            $probe = DockerSeguro -Comando @('exec','-i',$id,'psql','-X','-U',$candidate,'-d','template1','-qAt','-v','ON_ERROR_STOP=1','-c',"SELECT current_user")
            if ($probe.Code -eq 0 -and (@($probe.Out).Count -eq 1)) {
                Write-Host ('ROLE_ACESSIVEL=' + $candidate) -ForegroundColor Green
                $roles = DockerSeguro -Comando @('exec','-i',$id,'psql','-X','-U',$candidate,'-d','template1','-qAt','-c','SELECT rolname FROM pg_roles WHERE rolcanlogin ORDER BY 1')
                if ($roles.Code -eq 0) { Write-Host 'ROLES_LOGIN:'; foreach ($r in $roles.Out) { Write-Host ('  ' + $r) } }
                $dbs = DockerSeguro -Comando @('exec','-i',$id,'psql','-X','-U',$candidate,'-d','template1','-qAt','-c',"SELECT datname FROM pg_database WHERE datallowconn ORDER BY 1")
                if ($dbs.Code -eq 0) { Write-Host 'BANCOS:'; foreach ($d in $dbs.Out) { Write-Host ('  ' + $d) } }
                $found=$true
                break
            }
        }
        if (-not $found) { Write-Host 'ROLE_ACESSIVEL=NENHUMA_DAS_TESTADAS; e necessario identificar como o volume foi inicializado.' -ForegroundColor Yellow }
        Write-Host 'DIAGNOSTICO_CONCLUIDO_SEM_MODIFICAR_POSTGRESQL=OK' -ForegroundColor Green
    } finally { Pop-Location }
} catch {
    Write-Host ('DIAGNOSTICO_INTERROMPIDO: ' + $_.Exception.Message) -ForegroundColor Yellow
    exit 1
}
