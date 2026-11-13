@echo off
rem Envia suas mudancas do Sentico Green (ERP) para o GitHub (push).
rem Rode na pasta do projeto (onde esta este arquivo). Depois, na VPS: bash infra/vps/atualizar.sh
if /i not "%~1"=="--dentro" (
  cmd /k ""%~f0" --dentro"
  exit /b
)
setlocal
cd /d "%~dp0"
color 0f
cls
echo ============================================================
echo   Sentico Green (ERP) - enviar mudancas para o GitHub
echo ============================================================
echo.

where git >nul 2>nul
if errorlevel 1 goto sem_git
if not exist ".git" goto sem_repo

echo Mudancas pendentes:
git status --short
echo.

set "MSG="
set /p MSG=Descreva a mudanca (enter = "atualizacao"):
if "%MSG%"=="" set "MSG=atualizacao"

git add -A
git commit -m "%MSG%"
if errorlevel 1 (
  echo.
  echo Nada para enviar (sem mudancas) ou o commit falhou.
  goto fim
)

echo.
echo Enviando para o GitHub...
git push origin main
if errorlevel 1 goto push_falhou

echo.
echo ------------------------------------------------------------
echo OK - enviado para o GitHub.
echo Agora, na VPS (como root), aplique a atualizacao:
echo   bash /opt/sentico-green/infra/vps/atualizar.sh
echo ------------------------------------------------------------
goto fim

:sem_git
echo [ERRO] O git nao foi encontrado. Instale o Git para Windows (git-scm.com).
goto fim
:sem_repo
echo [ERRO] Esta pasta nao e um repositorio git. Clone o ERPnexus primeiro:
echo   git clone git@github.com:caiancaio025-ai/ERPnexus.git
goto fim
:push_falhou
echo [ERRO] Falha ao enviar. Confira sua conexao e o acesso ao GitHub.
goto fim

:fim
echo.
echo Pode fechar esta janela.
endlocal
