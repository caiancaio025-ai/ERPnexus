@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0DIAGNOSTICAR_VOLUME_SENTICO.ps1" -ProjectDir "%~dp0codigo-fonte"
echo.
pause
