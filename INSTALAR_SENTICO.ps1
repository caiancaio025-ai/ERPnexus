#Requires -Version 5.1
<#
 SENTICO V15 - instalador unico Windows com descoberta por COMPATIBILIDADE.
 Reutiliza o volume da instalacao SÊNTICO existente independentemente do nome.
 Com volume desconhecido, somente o CLONA para o volume V14, sem alterar a origem.
 Identifica role e banco pelo catalogo real; nunca cria banco vazio de producao.
#>
[CmdletBinding()]
param(
    [string]$ProjectDir = $PSScriptRoot,
    [string]$BackupDir = ''
)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$env:COMPOSE_PARALLEL_LIMIT = '1'

$Projeto = 'sentico-v14-recuperado'
$VolumeBanco = 'sentico-v14-recuperado_pgdata'
$VolumeUploads = 'sentico-v14-recuperado_uploads'
$VolumeNode = 'sentico-v14-recuperado_node_modules'
$ComposeFile = 'compose.recuperacao.yml'
$ConfigDir = Join-Path $env:LOCALAPPDATA 'Sentico\RecuperacaoV14'
$EnvFile = Join-Path $ConfigDir '.env.recuperacao'
$ScriptsDir = Join-Path $PSScriptRoot 'scripts_recuperacao'
$Role = 'sentico_green'
$BancoPreferido = 'postgres'
$VolumeOrigem = $null
$Revisoes = @('20261013_02','20261022_01','20261022_02','20261026_01','20261026_02','20261026_03','20261027_01','20261027_02','20261027_03','20261027_04','20261027_05','20261028_01','20261112_01','20261116_01','20261117_01','20261123_01','20261123_02','20261126_01','20261126_02')
$Senha = $null
$Banco = $null

function Etapa([string]$Texto) { Write-Host "`n=== $Texto ===" -ForegroundColor Cyan }
function DockerOutput([string[]]$ArgsDocker) {
    $anterior = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $saida = @(& docker.exe @ArgsDocker 2>&1)
        $codigo = $LASTEXITCODE
    } finally { $ErrorActionPreference = $anterior }
    return @{ Code=$codigo; Lines=@($saida | ForEach-Object { [string]$_ }) }
}
function Docker([string[]]$ArgsDocker) {
    $anterior = $ErrorActionPreference
    try { $ErrorActionPreference='Continue'; & docker.exe @ArgsDocker; $codigo=$LASTEXITCODE }
    finally { $ErrorActionPreference=$anterior }
    if ($codigo -ne 0) { throw "ERRO_DOCKER_COMANDO (codigo $codigo). Os volumes nao foram apagados." }
}
function Compose([string[]]$ArgsCompose) {
    Docker (@('compose','-p',$Projeto,'--env-file',$EnvFile,'-f',$ComposeFile) + $ArgsCompose)
}
function ComposeOutput([string[]]$ArgsCompose) {
    return DockerOutput (@('compose','-p',$Projeto,'--env-file',$EnvFile,'-f',$ComposeFile) + $ArgsCompose)
}
function ExisteVolume([string]$nome) { return ((DockerOutput @('volume','inspect',$nome)).Code -eq 0) }
function EstadoVolume([string]$nome,[bool]$silencioso=$false) {
    # Nao gravar, criar banco, limpar ou inicializar o PGDATA nesta funcao.
    # Docker/Windows pode emitir WARN/avisos junto ao resultado legitimo.
    $r = DockerOutput @('run','--rm','--pull=missing','--network','none',
        '--mount',"type=volume,source=$nome,target=/dados,readonly",
        '--mount',"type=bind,source=$ScriptsDir,target=/scripts,readonly",
        '--entrypoint','sh','postgres:17-alpine','/scripts/estado_volume_v14.sh')

    $marcadores = @($r.Lines | ForEach-Object { $_.Trim() } |
        Where-Object { $_ -match '^SENTICO_ESTADO_VOLUME=(PG_VERSION=17|VAZIO|INESPERADO)$' })
    if ($r.Code -ne 0 -or $marcadores.Count -ne 1) {
        # Esta chamada nao recebe .env, senhas ou dados SQL; stderr e seguro para diagnosticar.
        $detalhe = (@($r.Lines | Select-Object -Last 8) -join ' ').Trim()
        if ($detalhe.Length -gt 650) { $detalhe = $detalhe.Substring(0,650) }
        if (-not $detalhe) { $detalhe = 'Sem detalhe retornado pelo Docker.' }
        throw "ERRO_INSPECAO_VOLUME_DOCKER (codigo $($r.Code)): $detalhe"
    }
    $estado = $marcadores[0].Substring('SENTICO_ESTADO_VOLUME='.Length)
    if (-not $silencioso) { Write-Host "VOLUME_POSTGRESQL_ESTADO=$estado" -ForegroundColor Green }
    return $estado
}
function LerEnv {
    $pares=@{}
    Get-Content -LiteralPath $EnvFile -Encoding UTF8 | ForEach-Object {
        if ($_ -match '^([A-Z_0-9]+)=(.*)$') { $pares[$Matches[1]] = $Matches[2] }
    }
    if (-not $pares.ContainsKey('SENTICO_RECOVERY_DB_PASSWORD') -or $pares['SENTICO_RECOVERY_DB_PASSWORD'] -cnotmatch '^[a-f0-9]{64}$') {
        throw 'ERRO_ENV_RECUPERACAO_INVALIDO: nao envie o arquivo nem gere senha manualmente.'
    }
    return $pares
}
function NomeSeguro([string]$nome) {
    return ($nome -cmatch '^[a-zA-Z_][a-zA-Z0-9_]*$' -and $nome.Length -le 63)
}
function NomeVolumeSeguro([string]$nome) {
    return ($nome -cmatch '^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}$')
}
function EscreverEnv([string]$senhaAtual,[string]$bancoAtual) {
    if (-not (NomeSeguro $bancoAtual) -or -not (NomeSeguro $Role)) { throw 'ERRO_ENV_IDENTIFICADOR_INSEGURO' }
    foreach ($v in @($VolumeBanco,$VolumeUploads,$VolumeNode)) {
        if (-not (NomeVolumeSeguro $v)) { throw 'ERRO_ENV_VOLUME_INSEGURO' }
    }
    $linhas = @(
      "SENTICO_RECOVERY_DB_PASSWORD=$senhaAtual"
      "SENTICO_DB_NAME=$bancoAtual"
      "SENTICO_DB_ROLE=$Role"
      "SENTICO_PGDATA_VOLUME=$VolumeBanco"
      "SENTICO_UPLOADS_VOLUME=$VolumeUploads"
      "SENTICO_NODE_VOLUME=$VolumeNode"
    )
    # Preservar a configuração opcional de notificações em reinstalações locais.
    # Chave privada nunca é escrita no .env: somente arquivo PEM em secrets/.
    if (Test-Path -LiteralPath $EnvFile -PathType Leaf) {
        foreach ($linha in (Get-Content -LiteralPath $EnvFile -Encoding UTF8)) {
            if ($linha -cmatch '^PUSH_VAPID_PUBLIC_KEY=([A-Za-z0-9_-]{80,100})$') {
                $linhas += $linha
            } elseif ($linha -cmatch '^PUSH_VAPID_SUBJECT=mailto:[^\s#]{3,160}$') {
                $linhas += $linha
            }
        }
    }
    [System.IO.File]::WriteAllText($EnvFile,($linhas -join "`n")+"`n",[System.Text.UTF8Encoding]::new($false))
}
# Identifica volumes de containers pertencentes a ESTE projeto, inclusive parados.
function VolumeDoProjeto([string]$servico,[string]$destino) {
    $r=DockerOutput @('ps','-a','--filter',"label=com.docker.compose.project=$Projeto",'--filter',"label=com.docker.compose.service=$servico",'--format','{{.ID}}')
    if ($r.Code -ne 0) { return $null }
    $ids=@($r.Lines | Where-Object { $_ -match '^[a-fA-F0-9]{12,64}$' })
    foreach ($id in $ids) {
        $q=DockerOutput @('inspect','--format','{{json .Mounts}}',$id)
        if ($q.Code -ne 0 -or -not $q.Lines.Count) { continue }
        try { $mounts=($q.Lines -join '') | ConvertFrom-Json }
        catch { continue }
        foreach ($m in @($mounts)) {
            if ($m.Type -eq 'volume' -and $m.Destination -eq $destino -and (NomeVolumeSeguro $m.Name)) { return [string]$m.Name }
        }
    }
    return $null
}
# Nao alterar um volume que ainda pertence a outra instalacao. A descoberta
# avulsa so permite clonar origem NAO utilizada por nenhum container.
function AcharOrigemIsoladaCompativel {
    $list=DockerOutput @('volume','ls','--format','{{.Name}}')
    if ($list.Code -ne 0) { return $null }
    $candidatos=New-Object 'System.Collections.Generic.List[string]'
    foreach ($v in $list.Lines) {
        $v=$v.Trim()
        if (-not (NomeVolumeSeguro $v) -or $v -eq $VolumeBanco -or $v -match '(^|[-_])(blue|prod)([-_]|$)') { continue }
        $emUso=DockerOutput @('ps','-a','--filter',"volume=$v",'--format','{{.ID}}')
        if ($emUso.Code -ne 0 -or (@($emUso.Lines | Where-Object { $_.Trim() }).Count -gt 0)) { continue }
        try { $estado=EstadoVolume $v $true }
        catch { continue } # Um volume alheio nao deve derrubar o instalador.
        if ($estado -eq 'PG_VERSION=17') { $candidatos.Add($v) }
    }
    if ($candidatos.Count -eq 1) { return $candidatos[0] }
    if ($candidatos.Count -gt 1) {
        Write-Host ('VOLUMES_PG17_AVULSOS=' + $candidatos.Count + '; nenhum foi alterado nem escolhido aleatoriamente.') -ForegroundColor Yellow
    }
    return $null
}
function ValidarExclusividadePgdata {
    # Um mesmo PGDATA nao pode ser montado por 2 servidores PostgreSQL ao mesmo tempo.
    $r=DockerOutput @('ps','--filter',"volume=$VolumeBanco",'--format','{{.ID}}')
    if ($r.Code -ne 0) { throw 'ERRO_CHECAGEM_USO_PGDATA' }
    foreach ($id in $r.Lines) {
        $id=$id.Trim()
        if ($id -notmatch '^[a-fA-F0-9]{12,64}$') { continue }
        $info=DockerOutput @('inspect','--format','{{json .Config.Labels}}',$id)
        if ($info.Code -ne 0 -or -not $info.Lines.Count) { throw 'ERRO_CONSULTA_LABELS_CONTAINER_PGDATA' }
        try { $labels=($info.Lines -join '') | ConvertFrom-Json }
        catch { throw 'ERRO_LEITURA_LABELS_CONTAINER_PGDATA' }
        if ($labels.'com.docker.compose.project' -ne $Projeto -or $labels.'com.docker.compose.service' -ne 'db') {
            throw 'ERRO_PGDATA_EM_USO_POR_OUTRO_CONTAINER: nao iniciar dois servidores no mesmo volume.'
        }
    }
}
function ClonarOrigemCompativel([string]$origem) {
    if (-not (NomeVolumeSeguro $origem)) { throw 'ERRO_ORIGEM_VOLUME_INVALIDO' }
    if (ExisteVolume $VolumeBanco) { throw 'ERRO_CLONE_DESTINO_JA_EXISTE' }
    $emUso=DockerOutput @('ps','-a','--filter',"volume=$origem",'--format','{{.ID}}')
    if ($emUso.Code -ne 0 -or (@($emUso.Lines | Where-Object { $_.Trim() }).Count -gt 0)) { throw 'ERRO_CLONE_ORIGEM_EM_USO' }
    Docker @('volume','create',$VolumeBanco)
    Docker @('run','--rm','--pull=never','--network','none',
       '--mount',"type=volume,source=$origem,target=/orig,readonly",
       '--mount',"type=volume,source=$VolumeBanco,target=/dados",
       '--mount',"type=bind,source=$ScriptsDir,target=/scripts,readonly",
       '--entrypoint','sh','postgres:17-alpine','/scripts/clonar_pgdata_compat.sh')
    Write-Host 'PGDATA_COMPATIVEL_CLONADO_SEM_ALTERAR_ORIGEM=OK' -ForegroundColor Green
}
function BackupCompativel([string]$arquivo) {
    $r=DockerOutput @('run','--rm','--pull=never','--network','none',
        '--mount',"type=bind,source=$arquivo,target=/backup/input.tar.gz,readonly",
        '--mount',"type=bind,source=$ScriptsDir,target=/scripts,readonly",
        '--entrypoint','sh','postgres:17-alpine','/scripts/verificar_arquivo_pg17.sh')
    return ($r.Code -eq 0 -and $r.Lines -contains 'BACKUP_PG17_COMPATIVEL=OK')
}
function ArquivosBackup {
    $pastas = New-Object 'System.Collections.Generic.List[string]'
    if ($BackupDir) { $pastas.Add($BackupDir) }
    $pastas.Add((Join-Path $PSScriptRoot 'dados_importacao'))
    $pastas.Add($PSScriptRoot)
    $desktop=[Environment]::GetFolderPath('Desktop')
    foreach ($d in @(Get-ChildItem -LiteralPath $desktop -Directory -Filter 'BACKUP_SENTICO_*' -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending)) {
        $pastas.Add($d.FullName)
    }
    $pastas.Add($desktop)
    $pastas.Add((Join-Path ([Environment]::GetFolderPath('UserProfile')) 'Downloads'))
    $resultado = New-Object 'System.Collections.Generic.List[string]'
    foreach ($p in $pastas) {
        if (-not (Test-Path -LiteralPath $p -PathType Container)) { continue }
        # Qualquer .tar.gz e aceito pelo NOME; o conteudo fisico PostgreSQL 17 decide.
        $arquivos=Get-ChildItem -LiteralPath $p -File -Filter '*.tar.gz' -ErrorAction SilentlyContinue
        foreach ($f in $arquivos) {
            if (-not $resultado.Contains($f.FullName)) { $resultado.Add($f.FullName) }
        }
    }
    return @($resultado.ToArray())
}
function ImportarBancoEmVolumeVazio([string]$arquivo) {
    Write-Host ('ORIGEM_BACKUP=' + (Split-Path -Leaf $arquivo)) -ForegroundColor Yellow
    Docker @('run','--rm','--pull=never','--network','none',
        '--mount',"type=volume,source=$VolumeBanco,target=/dados",
        '--mount',"type=bind,source=$arquivo,target=/backup/input.tar.gz,readonly",
        '--mount',"type=bind,source=$ScriptsDir,target=/scripts,readonly",
        '--entrypoint','sh','postgres:17-alpine','/scripts/importar_pgdata_fixo.sh')
}
function ImportarUploads {
    if (-not (ExisteVolume $VolumeUploads)) { Docker @('volume','create',$VolumeUploads) }
    $estado=DockerOutput @('run','--rm','--pull=never','--network','none',
        '--mount',"type=volume,source=$VolumeUploads,target=/dados,readonly",
        '--entrypoint','sh','postgres:17-alpine','-c','test -z "$(ls -A /dados)"')
    if ($estado.Code -ne 0) { Write-Host 'UPLOADS_ORIGINAIS_V14=REUTILIZADOS' -ForegroundColor Green; return }
    $desktop=[Environment]::GetFolderPath('Desktop')
    $pastas=@((Join-Path $PSScriptRoot 'dados_importacao'),$PSScriptRoot)
    if ($BackupDir) { $pastas += $BackupDir }
    $pastas += @(Get-ChildItem -LiteralPath $desktop -Directory -Filter 'BACKUP_SENTICO_*' -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | ForEach-Object { $_.FullName })
    foreach ($p in $pastas) {
        foreach ($nome in @('sentico-v14-recuperado_uploads.tar.gz','uploads.tar.gz')) {
            $arquivo=Join-Path $p $nome
            if (-not (Test-Path -LiteralPath $arquivo -PathType Leaf)) { continue }
            Docker @('run','--rm','--pull=never','--network','none',
                '--mount',"type=volume,source=$VolumeUploads,target=/dados",
                '--mount',"type=bind,source=$arquivo,target=/backup/input.tar.gz,readonly",
                '--mount',"type=bind,source=$ScriptsDir,target=/scripts,readonly",
                '--entrypoint','sh','postgres:17-alpine','/scripts/importar_uploads_fixo.sh')
            Write-Host 'UPLOADS_RESTAURADOS=OK' -ForegroundColor Green
            return
        }
    }
    Write-Host 'UPLOADS_SEM_BACKUP=VOLUME_VAZIO' -ForegroundColor Yellow
}
function ExecutarScriptNoBanco([string]$nome) {
    return (ExecutarScriptNoBancoComArgumento $nome '')
}
function ExecutarScriptNoBancoComArgumento([string]$nome,[string]$argumento) {
    # Evita Get-Content -Raw | docker compose exec ... sh -s no PowerShell 5.1.
    # O script e copiado APENAS para /tmp do container, nunca para PGDATA.
    if ($nome -cnotmatch '^[a-z0-9_]+[.]sh$') { throw 'ERRO_NOME_SCRIPT_INVALIDO' }
    $caminho=Join-Path $ScriptsDir $nome
    if (-not (Test-Path -LiteralPath $caminho -PathType Leaf)) { throw "ERRO_SCRIPT_AUSENTE=$nome" }
    $psdb=ComposeOutput @('ps','-q','db')
    if ($psdb.Code -ne 0) {
        return @{ Code=90; Lines=@('ERRO_CATALOGO_CONTAINER_NAO_LOCALIZADO') }
    }
    $ids=@($psdb.Lines | ForEach-Object { $_.Trim() } |
        Where-Object { $_ -match '^[a-fA-F0-9]{12,64}$' })
    if ($ids.Count -ne 1) {
        return @{ Code=91; Lines=@('ERRO_CATALOGO_CONTAINER_INDETERMINADO') }
    }
    $container=$ids[0]
    $destino='/tmp/sentico_v14_' + $nome
    $copiar=DockerOutput @('cp',$caminho,"${container}:$destino")
    if ($copiar.Code -ne 0) {
        return @{ Code=92; Lines=@('ERRO_CATALOGO_COPIA_SCRIPT') }
    }
    $argsExec=@('exec',$container,'sh',$destino)
    if ($argumento) { $argsExec += $argumento }
    return (DockerOutput $argsExec)
}
function MelhorBanco([object[]]$candidatos) {
    if ($null -eq $candidatos -or $candidatos.Count -eq 0) { return $null }
    # Prioriza banco da configuracao, exceto 'postgres' como valor inicial nao confirmado.
    if ($BancoPreferido -ne 'postgres') {
        foreach ($c in $candidatos) { if ($c.Database -eq $BancoPreferido) { return $c } }
    }
    $melhor=$null
    $pontuacao=-1
    foreach ($c in $candidatos) {
        $idx=[array]::IndexOf($Revisoes,$c.Revisao)
        if ($idx -lt 0) { continue }
        $p=([long]$idx * [long]1000000000000) + ([math]::Min($c.OS,1000000)*10000) + ([math]::Min($c.Clientes,100000)*10) + [math]::Min($c.Compras,9)
        if ($p -gt $pontuacao -or ($p -eq $pontuacao -and ($null -eq $melhor -or [string]::CompareOrdinal($c.Database,$melhor.Database) -lt 0))) {
            $pontuacao=$p; $melhor=$c
        }
    }
    return $melhor
}
function DetectarRoleOffline {
    $r=DockerOutput @('run','--rm','--pull=never','--network','none','--user','postgres',
        '--mount',"type=volume,source=$VolumeBanco,target=/dados",
        '--mount',"type=bind,source=$ScriptsDir,target=/scripts,readonly",
        '--entrypoint','sh','postgres:17-alpine','/scripts/identificar_role_offline.sh')
    $roles=@($r.Lines | Where-Object { $_ -match '^ROLE_IDENTIFICADA=[a-zA-Z_][a-zA-Z0-9_]*$' })
    if ($r.Code -ne 0 -or $roles.Count -ne 1) { throw 'ERRO_DETECCAO_ROLE: role superuser ambigua ou inacessivel na copia V14.' }
    return $roles[0].Substring('ROLE_IDENTIFICADA='.Length)
}
function TestarTcp {
    $r=ExecutarScriptNoBanco 'verificar_tcp_copia.sh'
    if ($r.Code -eq 0 -and $r.Lines -contains 'AUTENTICACAO_TCP=OK') { return 'OK' }
    $e=@($r.Lines | Where-Object { $_ -match '^ERRO_TCP_[A-Z0-9_]+$' })
    if ($e.Count) { return $e[-1] }
    return 'ERRO_TCP_NAO_IDENTIFICADO'
}
function AguardarTcp {
    for ($tentativa=0; $tentativa -lt 20; $tentativa++) {
        $resultado=TestarTcp
        if ($resultado -eq 'OK') { return 'OK' }
        if ($resultado -notin @('ERRO_TCP_CONEXAO_RECUSADA','ERRO_TCP_TIMEOUT','ERRO_TCP_NAO_IDENTIFICADO')) { return $resultado }
        Start-Sleep -Seconds 1
    }
    return $resultado
}
function TestarEscritaApi {
    $r=ComposeOutput @('exec','-T','api','python','scripts/verificar_escrita_recuperacao.py')
    if ($r.Code -eq 0 -and $r.Lines -contains 'OK_API_ESCRITA_TRANSACIONAL') { return 'OK' }
    $e=@($r.Lines | Where-Object { $_ -match '^ERRO_API_[A-Z0-9_]+$' })
    if ($e.Count) { return $e[-1] }
    return 'ERRO_API_ESCRITA_INDETERMINADA'
}
function Http([string]$url,[string]$nome) {
    for ($i=0;$i -lt 24;$i++) {
        try {
            $r=Invoke-WebRequest -UseBasicParsing -Uri $url -TimeoutSec 5
            if ($r.StatusCode -eq 200) { Write-Host "${nome}_HTTP_200=OK" -ForegroundColor Green; return }
        } catch { Start-Sleep -Seconds 2 }
    }
    throw "ERRO_HTTP_$nome. Veja o status do Docker sem apagar volumes."
}

try {
    Etapa '01 - INSTALACAO EXISTENTE E COMPATIBILIDADE DE VOLUMES'
    $ProjectDir=(Resolve-Path -LiteralPath $ProjectDir).Path
    Set-Location -LiteralPath $ProjectDir
    if (-not (Get-Command docker.exe -ErrorAction SilentlyContinue)) { throw 'Docker Desktop nao encontrado.' }
    $info=DockerOutput @('info','--format','{{.OSType}}')
    if ($info.Code -ne 0 -or $info.Lines -notcontains 'linux') { throw 'Docker Desktop com Linux containers nao esta iniciado.' }
    $yaml=Get-Content -LiteralPath $ComposeFile -Raw
    foreach ($texto in @('name: sentico-v14-recuperado','SENTICO_PGDATA_VOLUME','SENTICO_UPLOADS_VOLUME','SENTICO_NODE_VOLUME','external: true')) {
        if (-not $yaml.Contains($texto)) { throw "ERRO_COMPOSE_SEM_COMPATIBILIDADE=$texto" }
    }
    if ($yaml.Contains('sentico-dev-entrega_dev_postgres_data')) { throw 'ERRO_COMPOSE_REFERENCIA_VOLUME_ORIGINAL' }

    Etapa '02 - REUTILIZAR CREDENCIAIS E DETECTAR VOLUMES SEM DEPENDER DO NOME'
    if (-not (Test-Path -LiteralPath $ConfigDir -PathType Container)) { New-Item -ItemType Directory -Path $ConfigDir -Force | Out-Null }
    $envAtual=@{}
    if (Test-Path -LiteralPath $EnvFile -PathType Leaf) {
        $envAtual=LerEnv
        $Senha=$envAtual['SENTICO_RECOVERY_DB_PASSWORD']
        Write-Host 'ENV_EXISTENTE=REUTILIZADO' -ForegroundColor Green
    } else {
        $bytes=New-Object byte[] 32
        $rng=[System.Security.Cryptography.RandomNumberGenerator]::Create()
        try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
        $Senha=([BitConverter]::ToString($bytes) -replace '-', '').ToLowerInvariant()
        Write-Host 'ENV_NOVO=CRIADO' -ForegroundColor Yellow
    }
    if ($envAtual.ContainsKey('SENTICO_DB_ROLE') -and (NomeSeguro $envAtual['SENTICO_DB_ROLE'])) { $Role=$envAtual['SENTICO_DB_ROLE'] }
    if ($envAtual.ContainsKey('SENTICO_DB_NAME') -and (NomeSeguro $envAtual['SENTICO_DB_NAME'])) { $BancoPreferido=$envAtual['SENTICO_DB_NAME'] }
    foreach ($entrada in @(@('db','/var/lib/postgresql/data','SENTICO_PGDATA_VOLUME'),@('api','/app/storage','SENTICO_UPLOADS_VOLUME'),@('web','/app/node_modules','SENTICO_NODE_VOLUME'))) {
        $v=VolumeDoProjeto $entrada[0] $entrada[1]
        if (-not $v -and $envAtual.ContainsKey($entrada[2]) -and (NomeVolumeSeguro $envAtual[$entrada[2]])) { $v=$envAtual[$entrada[2]] }
        if ($v) {
            switch ($entrada[0]) { 'db' {$VolumeBanco=$v}; 'api' {$VolumeUploads=$v}; 'web' {$VolumeNode=$v} }
        }
    }
    # Nao inventar novos nomes: os defaults permanecem os nomes originais do usuario.
    if ($VolumeBanco -match 'sentico-dev-entrega|[-_]blue([-_]|$)|[-_]prod([-_]|$)') { throw 'ERRO_VOLUME_PRODUCAO_PROTEGIDO' }
    EscreverEnv $Senha $BancoPreferido
    Write-Host "VOLUMES_REUTILIZADOS=$VolumeBanco / $VolumeUploads / $VolumeNode" -ForegroundColor Green
    Etapa '03 - REUTILIZAR VOLUME POSTGRESQL, SEM EXIGIR INSPECAO DE BACKUP'
    $jaExiste=ExisteVolume $VolumeBanco
    if (-not $jaExiste) {
        $origem=AcharOrigemIsoladaCompativel
        if ($origem) { ClonarOrigemCompativel $origem }
        else {
            $arquivos=@(ArquivosBackup)
            if (-not $arquivos.Count) { throw 'ERRO_SEM_PGDATA_COMPATIVEL_E_SEM_ARQUIVO_BACKUP' }
            Docker @('volume','create',$VolumeBanco)
            Write-Host 'VOLUME_V14_CRIADO_PARA_BACKUP_COMPATIVEL=OK' -ForegroundColor Green
        }
    }
    $estado=EstadoVolume $VolumeBanco
    if ($estado -eq 'VAZIO') {
        $arquivos=@(ArquivosBackup)
        $aceito=$null
        foreach ($arquivo in $arquivos) {
            if (BackupCompativel $arquivo) { $aceito=$arquivo; break }
        }
        if (-not $aceito) { throw 'ERRO_VOLUME_VAZIO_SEM_ARQUIVO_PG17_COMPATIVEL: nao inicializar banco vazio.' }
        ImportarBancoEmVolumeVazio $aceito
        $estado=EstadoVolume $VolumeBanco
    }
    if ($estado -ne 'PG_VERSION=17') {
        throw "ERRO_VOLUME_POSTGRESQL_INCOMPATIVEL=$estado. Volume preservado; nao formatar nem remover."
    }
    Write-Host 'POSTGRESQL17_NO_MESMO_VOLUME=OK' -ForegroundColor Green
    if (-not (ExisteVolume $VolumeNode)) { Docker @('volume','create',$VolumeNode) }
    ImportarUploads

    Etapa '04 - SUBIR BANCO EXISTENTE E IDENTIFICAR O NOME REAL'
    ValidarExclusividadePgdata
    Compose @('config','--quiet')
    Compose @('up','-d','--no-build','db')
    $r=ComposeOutput @('ps','-q','db')
    if ($r.Code -ne 0 -or $r.Lines.Count -ne 1 -or -not $r.Lines[0].Trim()) { throw 'ERRO_CONTAINER_BANCO_NAO_LOCALIZADO' }
    $containerId=$r.Lines[0].Trim()
    $mounts=(DockerOutput @('inspect','--format','{{json .Mounts}}',$containerId)).Lines[0] | ConvertFrom-Json
    if ((@($mounts | Where-Object { $_.Name -eq $VolumeBanco -and $_.Destination -eq '/var/lib/postgresql/data' -and $_.RW }).Count) -eq 0) {
        throw 'ERRO_MONTAGEM_PGDATA_NAO_E_O_VOLUME_FIXO'
    }
    $healthy=$false
    for ($i=0;$i -lt 35;$i++) {
        $s=DockerOutput @('inspect','--format','{{.State.Health.Status}}',$containerId)
        if ($s.Code -eq 0 -and $s.Lines -contains 'healthy') { $healthy=$true; break }
        Start-Sleep -Seconds 2
    }
    if (-not $healthy) { throw 'ERRO_POSTGRESQL_NAO_INICIOU. Consulte docker logs sentico-v14-recuperado-db-1 (sem enviar senhas).' }
    Etapa '05 - VALIDAR AUTENTICACAO TCP ANTES DE ABRIR O BANCO'
    $tcp=AguardarTcp
    if ($tcp -eq 'ERRO_TCP_SENHA_REJEITADA' -or $tcp -eq 'ERRO_TCP_ROLE_AUSENTE') {
        Write-Host 'A role do volume V14 precisa ser alinhada com a senha persistida. Apenas volume V14.' -ForegroundColor Yellow
        Compose @('stop','db')
        $ocupantes=DockerOutput @('ps','--filter',"volume=$VolumeBanco",'--format','{{.ID}}')
        if ($ocupantes.Code -ne 0 -or ((@($ocupantes.Lines | Where-Object { $_.Trim() }).Count) -gt 0)) { throw 'ERRO_VOLUME_EM_USO: nao aplicar reset offline.' }
        if ($tcp -eq 'ERRO_TCP_ROLE_AUSENTE') {
            $Role=DetectarRoleOffline
            Write-Host 'ROLE_POSTGRESQL_COMPATIVEL=IDENTIFICADA_SEM_DEPENDER_DO_NOME' -ForegroundColor Green
            EscreverEnv $Senha $BancoPreferido
        }
        Docker @('run','--rm','--pull=never','--network','none','--user','postgres',
            '--env-file',$EnvFile,
            '--mount',"type=volume,source=$VolumeBanco,target=/dados",
            '--mount',"type=bind,source=$ScriptsDir,target=/scripts,readonly",
            '--entrypoint','sh','postgres:17-alpine','/scripts/configurar_senha_offline.sh')
        Compose @('up','-d','--no-build','db')
        $tcp=AguardarTcp
    }
    if ($tcp -ne 'OK') { throw "ERRO_AUTENTICACAO_TCP=$tcp. Nao executar migrations." }
    Write-Host 'AUTENTICACAO_TCP=OK' -ForegroundColor Green

    Etapa '06 - IDENTIFICAR BANCO SENTICO COMPATIVEL'
    $catalogo=ExecutarScriptNoBanco 'catalogar_bancos_existentes.sh'
    foreach ($linha in $catalogo.Lines) {
        # Exibir apenas marcadores seguros, jamais stderr bruto ou credenciais.
        if ($linha -match '^(ERRO_[A-Z0-9_]+|CATALOGO_BANCOS_ANALISADOS=[0-9]+|BANCO_DESCARTADO_[A-Z_]+=[a-z0-9_]+|BANCO_SEM_USUARIOS=[a-z0-9_]+|CANDIDATO[|][a-z0-9_|]+)$') {
            Write-Host "CATALOGO: $linha"
        }
    }
    if ($catalogo.Code -ne 0) {
        $erro=@($catalogo.Lines | Where-Object { $_ -match '^ERRO_[A-Z0-9_]+$' })
        if ($erro.Count) {
            if ($erro[-1] -eq 'ERRO_CATALOGO_NENHUM_BANCO_COMPATIVEL') {
                throw 'ERRO_CATALOGO_NENHUM_BANCO_COMPATIVEL: confira as linhas CATALOGO acima. O PostgreSQL iniciou, mas nenhum banco apresentou as 5 tabelas esperadas e uma revisao Alembic reconhecida. Nao criar banco vazio nem alterar volumes.'
            }
            throw $erro[-1]
        }
        throw "ERRO_CATALOGO_EXECUCAO (codigo $($catalogo.Code)). Nenhuma migration foi executada."
    }
    $opcoes=New-Object 'System.Collections.Generic.List[object]'
    foreach ($linha in $catalogo.Lines) {
        if ($linha -match '^CANDIDATO\|([^|]+)\|([^|]+)\|([0-9]+)\|([0-9]+)\|([0-9]+)\|([0-9]+)$') {
            $opcoes.Add([pscustomobject]@{Database=$Matches[1]; Revisao=$Matches[2]; Usuarios=[int]$Matches[3]; Clientes=[int]$Matches[4]; OS=[int]$Matches[5]; Compras=[int]$Matches[6]})
        }
    }
    $escolha=MelhorBanco -candidatos $opcoes.ToArray()
    if ($null -eq $escolha) { throw 'ERRO_NENHUM_BANCO_COM_SCHEMA_SENTICO_E_ALEMBIC_COMPATIVEIS. Nao criar banco vazio.' }
    $Banco=$escolha.Database
    Write-Host "BANCO_REAL=$Banco REVISAO=$($escolha.Revisao) USUARIOS=$($escolha.Usuarios) CLIENTES=$($escolha.Clientes) OS=$($escolha.OS) COMPRAS=$($escolha.Compras)" -ForegroundColor Green
    if ($escolha.Usuarios -eq 0) {
        Write-Host 'AVISO_BANCO_SEM_USUARIOS: sistema pode iniciar, mas nao ha conta cadastrada para login. Nenhuma conta sera criada automaticamente.' -ForegroundColor Yellow
    }
    $envEscolhido=LerEnv
    if ($envEscolhido['SENTICO_DB_NAME'] -ne $Banco) { EscreverEnv $Senha $Banco }

    Etapa '07 - CONSTRUIR API E WEB DO SENTICO'
    Compose @('build','api','web')
    Compose @('up','-d','--no-build','--force-recreate','api')
    $head=ComposeOutput @('exec','-T','api','alembic','heads')
    if ($head.Code -ne 0 -or ($head.Lines -join ' ') -notmatch '20261126_02') { throw 'ERRO_MIGRATIONS_V14_NAO_ENCONTRADAS' }
    $atual=ComposeOutput @('exec','-T','api','alembic','current')
    if ($atual.Code -ne 0 -or ($atual.Lines -join ' ') -notmatch [regex]::Escape($escolha.Revisao)) {
        throw 'ERRO_REVISAO_ATUAL_DIFERENTE_DA_COPIA. Nenhuma migration executada.'
    }

    Etapa '08 - VALIDAR ESCRITA REAL NA MESMA CONEXAO DO ALEMBIC'
    $write=TestarEscritaApi
    if ($write -eq 'ERRO_API_READ_ONLY') {
        Write-Host 'BANCO_V14_READ_ONLY: ajustando somente esta role neste banco; uma tentativa.' -ForegroundColor Yellow
        $ajuste=ExecutarScriptNoBancoComArgumento 'ajustar_read_only_v14.sh' $Banco
        if ($ajuste.Code -ne 0 -or $ajuste.Lines -notcontains 'ESCRITA_V14_LIBERADA=OK') {
            throw 'ERRO_AJUSTE_READ_ONLY_NA_COPIA. Nao executar migrations.'
        }
        Compose @('up','-d','--no-build','--force-recreate','api')
        $write=TestarEscritaApi
    }
    if ($write -ne 'OK') { throw "ERRO_PREVALIDACAO_ESCRITA=$write. Nenhuma migration executada." }
    Write-Host 'API_WRITE_PREFLIGHT=OK' -ForegroundColor Green

    Etapa '09 - CONFERIR MIGRATIONS DO BANCO EXISTENTE'
    if ($escolha.Revisao -ne '20261126_02') { Compose @('exec','-T','api','alembic','upgrade','head') }
    $depois=ComposeOutput @('exec','-T','api','alembic','current')
    if ($depois.Code -ne 0 -or ($depois.Lines -join ' ') -notmatch '20261126_02') { throw 'ERRO_ALEMBIC_NAO_CONCLUIU_V14' }
    $apos=ExecutarScriptNoBanco 'catalogar_bancos_existentes.sh'
    if ($apos.Code -ne 0 -or (@($apos.Lines | Where-Object { $_ -match "^CANDIDATO\|$([regex]::Escape($Banco))\|20261126_02\|" }).Count -eq 0)) {
        throw 'ERRO_VALIDACAO_CADASTROS_POS_MIGRATION'
    }
    Write-Host 'ALEMBIC_V48_E_DADOS_PRESERVADOS=OK' -ForegroundColor Green

    Etapa '10 - INICIAR SITE LOCAL'
    Compose @('up','-d','--no-build','web','gateway')
    Http 'http://127.0.0.1:8183/health/ready' 'API_E_BANCO'
    Http 'http://127.0.0.1:5184/' 'WEB'
    Compose @('ps')
    Write-Host "`nSENTICO_INICIADO=OK" -ForegroundColor Green
    Write-Host 'ACESSO=http://127.0.0.1:5184/' -ForegroundColor Green
    Write-Host "VOLUMES_PERSISTENTES=$VolumeBanco / $VolumeUploads / $VolumeNode" -ForegroundColor Green
} catch {
    Write-Host "`nSENTICO_INTERROMPIDO_SEM_APAGAR_VOLUMES" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    Write-Host 'Nao use docker compose down -v. Nenhum volume foi apagado.' -ForegroundColor Yellow
    Write-Host 'Nao envie senhas ou arquivos de banco.' -ForegroundColor Yellow
    exit 1
} finally { $Senha=$null }
