@echo off
setlocal EnableExtensions
cd /d "%~dp0"
if errorlevel 1 (
  echo ERRO_PASTA_PROJETO: nao foi possivel abrir a pasta do SENTICO.
  pause
  exit /b 1
)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0INSTALAR_SENTICO.ps1"
set "CODIGO=%ERRORLEVEL%"
echo.
if not "%CODIGO%"=="0" (
  echo Instalacao interrompida sem apagar volumes. Veja LEIA_PRIMEIRO_SENTICO.md
)
pause
exit /b %CODIGO%
