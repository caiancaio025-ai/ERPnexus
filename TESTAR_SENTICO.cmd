@echo off
setlocal EnableExtensions
cd /d "%~dp0"
if errorlevel 1 exit /b 1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0TESTAR_SENTICO.ps1"
set "CODIGO_TESTE=%ERRORLEVEL%"
echo.
pause
exit /b %CODIGO_TESTE%
