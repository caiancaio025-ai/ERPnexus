@echo off
rem Compatibilidade: o atalho antigo agora executa os testes isolados da V48.
echo Este atalho foi substituido por TESTAR_SENTICO.cmd na V48.
echo O teste usa um banco separado e preserva sua branch atual.
call "%~dp0TESTAR_SENTICO.cmd"
exit /b %ERRORLEVEL%
