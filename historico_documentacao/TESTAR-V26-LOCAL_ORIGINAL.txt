@echo off
setlocal enabledelayedexpansion
title Testar Sentico V26 (local, isolado)

echo ============================================================
echo  TESTE LOCAL DA V26 - ambiente Docker isolado (nao toca
echo  nos seus dados reais nem na producao).
echo ============================================================
echo.

cd /d "%~dp0"

REM --- 1. Docker ligado? ---
docker info >nul 2>&1
if errorlevel 1 (
  echo [ERRO] O Docker Desktop nao esta rodando. Abra o Docker Desktop e tente de novo.
  pause
  exit /b 1
)

REM --- 2. Pegar a branch V26 ---
echo [1/5] Atualizando a branch feat/v16-v26-outro-dev...
git fetch origin || goto :erro
git checkout feat/v16-v26-outro-dev || goto :erro
git pull || goto :erro

REM --- 3. .env.dev (primeira vez) ---
set PRIMEIRA=0
if not exist ".env.dev" (
  set PRIMEIRA=1
  echo [2/5] Criando .env.dev local ^(senha so pra este ambiente isolado^)...
  >  .env.dev echo SENTICO_V14_PASSWORD=senticolocaldev2026
  >> .env.dev echo SENTICO_DB_NAME=postgres
) else (
  echo [2/5] .env.dev ja existe, mantendo.
)

REM --- 3b. Criar os volumes externos (idempotente; na primeira vez nao existem) ---
echo [3/5] Garantindo os volumes locais isolados...
docker volume create sentico_v14_local_pgdata >nul 2>&1
docker volume create sentico_v14_local_uploads >nul 2>&1
docker volume create sentico_v14_local_node_modules >nul 2>&1

REM --- 4. Subir o ambiente ---
echo       Subindo containers (pode demorar na primeira vez)...
docker compose -f compose.dev.yml --env-file .env.dev up -d --build || goto :erro

REM --- 5. Esperar a API responder ---
echo [4/5] Aguardando a API ficar pronta...
set /a TENT=0
:espera
set /a TENT+=1
docker compose -f compose.dev.yml --env-file .env.dev exec -T api python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/health/live')" >nul 2>&1
if not errorlevel 1 goto :pronta
if %TENT% geq 40 (
  echo [ERRO] A API nao respondeu a tempo. Veja os logs: docker compose -f compose.dev.yml logs api
  pause
  exit /b 1
)
timeout /t 3 >nul
goto :espera
:pronta

REM --- 6. Bootstrap do banco (idempotente: pode rodar quantas vezes quiser) ---
echo [5/5] Preparando o banco (migrations + admin padrao)...
echo   - migrando ate 20261009_01
docker compose -f compose.dev.yml --env-file .env.dev exec -T api alembic upgrade 20261009_01 || goto :erro
echo   - garantindo o admin padrao (so cria se o banco estiver vazio)
docker compose -f compose.dev.yml --env-file .env.dev exec -T api python scripts/criar_admin_padrao.py || goto :erro
echo   - migrando ate o head (inclui as migrations novas da V26)
docker compose -f compose.dev.yml --env-file .env.dev exec -T api alembic upgrade head || goto :erro

echo.
echo ============================================================
echo  PRONTO! Abra:  http://127.0.0.1:5284/
echo.
echo  Login padrao de teste:
echo     usuario: admin
echo     senha:   senticolocal2026
echo  (troque depois de entrar; vale so neste ambiente local)
echo.
echo  Para parar:    docker compose -f compose.dev.yml down
echo ============================================================
start "" "http://127.0.0.1:5284/"
pause
exit /b 0

:erro
echo.
echo [ERRO] Algo falhou no passo acima. Copie a mensagem e me mande.
pause
exit /b 1
