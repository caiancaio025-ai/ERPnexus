@echo off
setlocal EnableExtensions
cd /d "%~dp0"
if errorlevel 1 exit /b 1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0TESTE_LOCAL_V48.ps1" -Acao Iniciar %*
set "CODIGO_TESTE=%ERRORLEVEL%"
echo.
pause
exit /b %CODIGO_TESTE%
