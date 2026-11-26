#Requires -Version 5.1
param(
    [ValidateSet('Iniciar','Parar')][string]$Acao = 'Iniciar',
    [int]$Porta = 0,
    [switch]$NaoAbrir
)
$ErrorActionPreference = 'Stop'
$ProjetoTeste = 'sentico-v48-teste-local'
$ArquivoCompose = Join-Path $PSScriptRoot 'compose.teste-local.yml'
$ContextoDocker = $null
$LogTeste = $null
$AmbienteAnterior = @{}
$CodigoResultado = 0
$MutexTeste = $null
$PossuiMutex = $false

function DockerSaida([string[]]$Argumentos) {
    $anterior = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        if ($ContextoDocker) { $saida = @(& docker.exe --context $ContextoDocker @Argumentos 2>&1) }
        else { $saida = @(& docker.exe @Argumentos 2>&1) }
        $codigo = $LASTEXITCODE
    } finally { $ErrorActionPreference = $anterior }
    if ($codigo -ne 0) { throw 'Docker nao respondeu. Abra o Docker Desktop e confira o contexto local.' }
    return (($saida | ForEach-Object { $_.ToString() }) -join "`n")
}

function DockerExecutar([string[]]$Argumentos) {
    $anterior = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        & docker.exe --context $ContextoDocker @Argumentos 2>&1 | ForEach-Object {
            $linha = $_.ToString()
            Write-Host $linha
            if ($LogTeste) { Add-Content -LiteralPath $LogTeste -Value $linha -Encoding UTF8 }
        }
        $codigo = $LASTEXITCODE
    } finally { $ErrorActionPreference = $anterior }
    if ($codigo -ne 0) { throw "Docker interrompeu esta etapa. Consulte o log do teste: $LogTeste" }
}

function ConfirmarDockerLocal {
    if (-not (Get-Command docker.exe -CommandType Application -ErrorAction SilentlyContinue)) {
        throw 'Instale e abra o Docker Desktop para Windows, usando containers Linux.'
    }
    # Nunca selecionar ou alterar o contexto do usuario. Aceitar apenas pipe local.
    if ($env:DOCKER_HOST -and $env:DOCKER_HOST -notmatch '^npipe:////\./pipe/[A-Za-z0-9_.-]+$') {
        throw 'DOCKER_HOST aponta para outro ambiente. Este teste aceita somente Docker Desktop local (npipe).'
    }
    $contexto = (DockerSaida @('context','show')).Trim()
    if (-not $contexto) { throw 'Contexto Docker nao identificado.' }
    $endpoint = DockerSaida @('context','inspect',$contexto,'--format','{{json .Endpoints.docker.Host}}') | ConvertFrom-Json
    if ($endpoint -notmatch '^npipe:////\./pipe/[A-Za-z0-9_.-]+$') {
        throw 'O contexto Docker atual nao e um pipe local do Docker Desktop. Nenhum container foi alterado.'
    }
    $script:ContextoDocker = $contexto
    if ((DockerSaida @('info','--format','{{.OSType}}')).Trim() -ne 'linux') {
        throw 'O Docker Desktop precisa estar no modo Linux containers.'
    }
    $null = DockerSaida @('compose','version')
}

function NovoSegredo([int]$Bytes) {
    $dados = New-Object byte[] $Bytes
    $gerador = [Security.Cryptography.RandomNumberGenerator]::Create()
    try { $gerador.GetBytes($dados) } finally { $gerador.Dispose() }
    return [BitConverter]::ToString($dados).Replace('-','').ToLowerInvariant()
}

function SalvarTextoAtomico([string]$Caminho, [string]$Conteudo) {
    $temporario = "$Caminho.$([Guid]::NewGuid().ToString('N')).tmp"
    try {
        [IO.File]::WriteAllText($temporario, $Conteudo, (New-Object Text.UTF8Encoding($false)))
        if (Test-Path -LiteralPath $Caminho) { [IO.File]::Replace($temporario, $Caminho, $null) }
        else { [IO.File]::Move($temporario, $Caminho) }
    } finally {
        if (Test-Path -LiteralPath $temporario) { Remove-Item -LiteralPath $temporario -Force }
    }
}

function LerConfiguracao([string]$Caminho) {
    $valores = @{}
    foreach ($linha in Get-Content -LiteralPath $Caminho -Encoding UTF8) {
        if (-not $linha.Trim() -or $linha.TrimStart().StartsWith('#')) { continue }
        if ($linha -notmatch '^([A-Z0-9_]+)=([^\r\n]*)$' -or $valores.ContainsKey($Matches[1])) {
            throw 'Configuracao do teste invalida. Preserve a pasta de teste; nao gere outra senha sobre o banco existente.'
        }
        $valores[$Matches[1]] = $Matches[2]
    }
    $regras = @{
        SENTICO_V48_TEST_DB_PASSWORD = '^[a-f0-9]{64}$'
        SENTICO_V48_TEST_PASSWORD = '^[a-f0-9]{32}$'
        SENTICO_V48_TEST_INSTANCE = '^[a-f0-9]{48}$'
        SENTICO_V48_TEST_PORT = '^[0-9]{4,5}$'
    }
    if ($valores.Count -ne $regras.Count) { throw 'Configuracao local incompleta ou com campos inesperados.' }
    foreach ($chave in $regras.Keys) {
        if (-not $valores.ContainsKey($chave) -or $valores[$chave] -notmatch $regras[$chave]) {
            throw 'Configuracao local invalida; senhas e dados existentes foram preservados.'
        }
    }
    if ([int]$valores.SENTICO_V48_TEST_PORT -lt 1024 -or [int]$valores.SENTICO_V48_TEST_PORT -gt 65535) {
        throw 'Porta salva invalida. Use -Porta entre 1024 e 65535.'
    }
    return $valores
}

function SalvarConfiguracao([string]$Caminho, [hashtable]$Valores) {
    $linhas = @('SENTICO_V48_TEST_DB_PASSWORD','SENTICO_V48_TEST_PASSWORD','SENTICO_V48_TEST_INSTANCE','SENTICO_V48_TEST_PORT') |
        ForEach-Object { "$_=$($Valores[$_])" }
    SalvarTextoAtomico $Caminho (($linhas -join "`n") + "`n")
}

function PortaDisponivel([int]$Numero) {
    $ouvinte = New-Object -TypeName Net.Sockets.TcpListener -ArgumentList @([Net.IPAddress]::Loopback, $Numero)
    try {
        $ouvinte.ExclusiveAddressUse = $true
        $ouvinte.Start()
        return $true
    } catch [Net.Sockets.SocketException] { return $false }
    finally { $ouvinte.Stop() }
}

function PortaDoProprioTeste([int]$Numero) {
    $ids = DockerSaida @('ps','--quiet','--filter',"label=com.docker.compose.project=$ProjetoTeste",'--filter','label=com.docker.compose.service=web')
    foreach ($id in ($ids -split "`n")) {
        if ($id -match '^[a-f0-9]{12,64}$') {
            $publicacao = DockerSaida @('port',$id,'8080/tcp')
            if ($publicacao.Trim() -eq "127.0.0.1:$Numero") { return $true }
        }
    }
    return $false
}

function EscolherPorta([int]$Desejada, [bool]$Explicita) {
    if ($Desejada -lt 1024 -or $Desejada -gt 65535) { throw 'Use uma porta entre 1024 e 65535.' }
    if ((PortaDisponivel $Desejada) -or (PortaDoProprioTeste $Desejada)) { return $Desejada }
    if ($Explicita) { throw "A porta $Desejada esta ocupada. Execute novamente com -Porta 5186 (ou outra porta livre)." }
    for ($candidata = $Desejada + 1; $candidata -le [Math]::Min($Desejada + 20, 65535); $candidata++) {
        if (PortaDisponivel $candidata) {
            Write-Host "Porta $Desejada ocupada; o teste usara $candidata." -ForegroundColor Yellow
            return $candidata
        }
    }
    throw 'Nenhuma porta livre no intervalo local. Execute novamente com -Porta e uma porta disponivel.'
}

function ConferirCompose([string[]]$Base) {
    # Capturar em memoria: config contem a senha do banco e nunca vai para o log.
    $config = DockerSaida ($Base + @('config','--format','json')) | ConvertFrom-Json
    if ($config.name -ne $ProjetoTeste -or
        $config.volumes.pgdata.name -ne 'sentico-v48-teste-local_pgdata' -or
        $config.volumes.uploads.name -ne 'sentico-v48-teste-local_uploads' -or
        $config.volumes.pgdata.external -or $config.volumes.uploads.external -or
        $config.networks.teste_local.name -ne 'sentico-v48-teste-local_rede' -or
        -not $config.networks.teste_local.internal -or $config.networks.teste_local.external -or
        $config.services.db.ports -or $config.services.api.ports) {
        throw 'A configuracao nao corresponde ao teste isolado. Nenhum servico sera iniciado.'
    }
    $portas = @($config.services.web.ports)
    if ($portas.Count -ne 1 -or $portas[0].host_ip -ne '127.0.0.1' -or [int]$portas[0].target -ne 8080) {
        throw 'Publicacao de porta diferente do teste local esperado.'
    }
    $dbVolumes = @($config.services.db.volumes)
    $apiVolumes = @($config.services.api.volumes)
    if ($dbVolumes.Count -ne 1 -or $dbVolumes[0].type -ne 'volume' -or $dbVolumes[0].source -ne 'pgdata' -or
        $dbVolumes[0].target -ne '/var/lib/postgresql/data' -or
        $apiVolumes.Count -ne 1 -or $apiVolumes[0].type -ne 'volume' -or $apiVolumes[0].source -ne 'uploads' -or
        $apiVolumes[0].target -ne '/app/storage') {
        throw 'Volumes do teste divergentes. Nenhum volume operacional pode ser utilizado.'
    }
}

function EsperarAplicacao([string]$Url) {
    $limite = [DateTime]::UtcNow.AddSeconds(180)
    while ([DateTime]::UtcNow -lt $limite) {
        try {
            $pronto = Invoke-RestMethod -Uri "$Url/api/health/ready" -TimeoutSec 5
            $versao = Invoke-RestMethod -Uri "$Url/api/health/version" -TimeoutSec 5
            if ($pronto.status -eq 'ok' -and $versao.version -eq '48') { return }
        } catch { }
        Start-Sleep -Seconds 2
    }
    throw 'A API V48 nao confirmou prontidao em 180 segundos. Consulte o log; os dados do teste foram preservados.'
}

try {
    if ($env:OS -ne 'Windows_NT' -or -not $env:LOCALAPPDATA) { throw 'Este iniciador foi preparado para Windows com Docker Desktop.' }
    $MutexTeste = New-Object -TypeName Threading.Mutex -ArgumentList @($false, 'Local\SenticoV48TesteLocal')
    try { $PossuiMutex = $MutexTeste.WaitOne(0) }
    catch [Threading.AbandonedMutexException] { $PossuiMutex = $true }
    if (-not $PossuiMutex) { throw 'Outro iniciador do teste esta em andamento. Aguarde sua conclusao.' }
    ConfirmarDockerLocal
    if ($Acao -eq 'Parar') {
        $ids = @((DockerSaida @('ps','--quiet','--filter',"label=com.docker.compose.project=$ProjetoTeste")) -split "`n" |
            Where-Object { $_ -match '^[a-f0-9]{12,64}$' })
        if ($ids.Count -gt 0) { DockerExecutar (@('stop','--time','30') + $ids) }
        Write-Host 'SENTICO_TESTE_V48=PARADO' -ForegroundColor Green
        Write-Host 'Banco e anexos do teste foram mantidos. Use INICIAR_TESTE_V48.cmd para continuar.'
    } else {
        foreach ($arquivo in @($ArquivoCompose, (Join-Path $PSScriptRoot 'infra/teste-local/bootstrap_v48.py'))) {
            if (-not (Test-Path -LiteralPath $arquivo -PathType Leaf)) { throw 'Pacote incompleto. Extraia todos os arquivos do ZIP antes de iniciar.' }
        }
        $PastaTeste = Join-Path $env:LOCALAPPDATA 'Sentico\TesteLocalV48'
        $ArquivoAmbiente = Join-Path $PastaTeste '.env.teste-local-v48'
        $ArquivoAcesso = Join-Path $PastaTeste 'acesso.txt'
        New-Item -ItemType Directory -Force -Path $PastaTeste | Out-Null
        $LogTeste = Join-Path $PastaTeste 'ultimo-log.txt'
        Set-Content -LiteralPath $LogTeste -Value "TESTE LOCAL V48 - $([DateTime]::Now.ToString('s'))" -Encoding UTF8
        if (Test-Path -LiteralPath $ArquivoAmbiente) { $valores = LerConfiguracao $ArquivoAmbiente }
        else {
            $volumes = DockerSaida @('volume','ls','--quiet','--filter','name=sentico-v48-teste-local_')
            $existentes = @(($volumes -split "`n") | Where-Object { $_ -in @('sentico-v48-teste-local_pgdata','sentico-v48-teste-local_uploads') })
            if ($existentes.Count -gt 0) { throw 'Ja existem volumes do teste sem sua configuracao local. Recupere a pasta TesteLocalV48 original; nenhum dado sera apagado ou redefinido.' }
            $valores = @{
                SENTICO_V48_TEST_DB_PASSWORD = NovoSegredo 32
                SENTICO_V48_TEST_PASSWORD = NovoSegredo 16
                SENTICO_V48_TEST_INSTANCE = NovoSegredo 24
                SENTICO_V48_TEST_PORT = '5185'
            }
        }
        $explicita = $PSBoundParameters.ContainsKey('Porta')
        $desejada = if ($explicita) { $Porta } else { [int]$valores.SENTICO_V48_TEST_PORT }
        $PortaFinal = EscolherPorta $desejada $explicita
        $valores.SENTICO_V48_TEST_PORT = [string]$PortaFinal
        SalvarConfiguracao $ArquivoAmbiente $valores
        foreach ($chave in $valores.Keys) {
            $AmbienteAnterior[$chave] = [Environment]::GetEnvironmentVariable($chave, 'Process')
            [Environment]::SetEnvironmentVariable($chave, $valores[$chave], 'Process')
        }
        $BaseCompose = @('compose','--project-directory',$PSScriptRoot,'-p',$ProjetoTeste,'--env-file',$ArquivoAmbiente,'-f',$ArquivoCompose)
        ConferirCompose $BaseCompose
        Write-Host 'Construindo API e interface do ZIP. A primeira execucao precisa baixar dependencias; aguarde.' -ForegroundColor Cyan
        DockerExecutar ($BaseCompose + @('build','api','web'))
        DockerExecutar ($BaseCompose + @('stop','-t','45','api','web'))
        DockerExecutar ($BaseCompose + @('up','-d','--no-build','--wait','--wait-timeout','120','db'))
        DockerExecutar ($BaseCompose + @('run','--rm','--no-deps','--pull','never','bootstrap'))
        DockerExecutar ($BaseCompose + @('up','-d','--no-deps','--no-build','api','web'))
        $UrlTeste = "http://127.0.0.1:$PortaFinal"
        Write-Host 'Aguardando a API, o banco e a interface responderem pela porta local...'
        EsperarAplicacao $UrlTeste
        $acesso = "SENTICO V48 - AMBIENTE DE TESTE LOCAL`r`nURL: $UrlTeste/`r`nUsuario: teste_v48`r`nSenha inicial: $($valores.SENTICO_V48_TEST_PASSWORD)`r`n`r`nSe voce alterou a senha no sistema, use a senha que escolheu. Reiniciar nao redefine a conta.`r`nBanco e anexos deste teste sao separados da instalacao operacional.`r`nPara parar sem apagar dados, execute PARAR_TESTE_V48.cmd.`r`n"
        SalvarTextoAtomico $ArquivoAcesso $acesso
        Write-Host 'SENTICO_TESTE_V48=OK' -ForegroundColor Green
        Write-Host "URL=$UrlTeste/"
        Write-Host 'USUARIO=teste_v48'
        Write-Host "SENHA_INICIAL=$($valores.SENTICO_V48_TEST_PASSWORD)"
        Write-Host 'Se a senha foi alterada no sistema, use a senha escolhida; ela nao foi redefinida.'
        Write-Host "ACESSO=$ArquivoAcesso"
        if (-not $NaoAbrir) {
            try { Start-Process $UrlTeste } catch { Write-Host "Abra manualmente: $UrlTeste/" }
        }
    }
} catch {
    $CodigoResultado = 1
    Write-Host "TESTE_LOCAL_INTERROMPIDO: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host 'A instalacao operacional nao foi utilizada. Os volumes existentes foram preservados.'
} finally {
    foreach ($chave in $AmbienteAnterior.Keys) {
        [Environment]::SetEnvironmentVariable($chave, $AmbienteAnterior[$chave], 'Process')
    }
    if ($PossuiMutex -and $MutexTeste) { $MutexTeste.ReleaseMutex() }
    if ($MutexTeste) { $MutexTeste.Dispose() }
}
exit $CodigoResultado
