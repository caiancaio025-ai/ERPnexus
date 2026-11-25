#Requires -Version 5.1
# Todos os comandos usam exclusivamente o projeto de testes, sem portas publicadas.
$ErrorActionPreference = 'Stop'
$ProjetoTeste = 'sentico-v48-testes'
$ArquivoTeste = Join-Path $PSScriptRoot 'compose.tests.yml'
$CodigoTeste = 1
New-Item -ItemType Directory -Force -Path (Join-Path $PSScriptRoot 'resultados_testes') | Out-Null
function TestCompose([string[]]$ArgumentosTeste) {
    & docker.exe compose -p $ProjetoTeste -f $ArquivoTeste @ArgumentosTeste
    if ($LASTEXITCODE -ne 0) { throw "TESTE_FALHOU (codigo $LASTEXITCODE). Consulte a saida acima." }
}
try {
    Write-Host 'SENTICO V48 - TESTES EM BANCO DESCARTAVEL' -ForegroundColor Cyan
    TestCompose @('build','api-tests','web-tests')
    TestCompose @('up','-d','db')
    TestCompose @('run','--rm','api-tests')
    TestCompose @('run','--rm','--no-deps','web-tests')
    $CodigoTeste = 0
    Write-Host 'TESTES_SENTICO_V48=OK' -ForegroundColor Green
} catch {
    Write-Host $_.Exception.Message -ForegroundColor Red
} finally {
    # Sem down -v. O banco efemero de teste usa tmpfs, nao volumes operacionais.
    & docker.exe compose -p $ProjetoTeste -f $ArquivoTeste down --remove-orphans
}
exit $CodigoTeste
