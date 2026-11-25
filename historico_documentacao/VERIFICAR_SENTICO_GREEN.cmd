@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0codigo-fonte"
if not exist "%LOCALAPPDATA%\Sentico\RecuperacaoV14\.env.recuperacao" (
 echo Ambiente recuperado ainda nao preparado. Execute INICIAR_SENTICO_GREEN.cmd
 goto :fim
)
echo === Containers SENTICO V14 RECUPERADO ===
docker compose --env-file "%LOCALAPPDATA%\Sentico\RecuperacaoV14\.env.recuperacao" -f compose.recuperacao.yml ps
if errorlevel 1 goto :fim
echo.
echo === Alembic ===
docker compose --env-file "%LOCALAPPDATA%\Sentico\RecuperacaoV14\.env.recuperacao" -f compose.recuperacao.yml exec -T api alembic current
:fim
echo.
echo ERP: http://127.0.0.1:5184/
pause
