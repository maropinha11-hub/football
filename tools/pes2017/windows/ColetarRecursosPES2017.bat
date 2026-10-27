@echo off
setlocal
cd /d "%~dp0"
echo Coleta seletiva de constantes e tabelas do PES 2017
echo Selecione o PES2017.exe da instalacao em que voce joga.
powershell.exe -NoLogo -NoProfile -STA -ExecutionPolicy Bypass -File "%~dp0coletar-recursos-pes2017.ps1" -Executavel "%~1"
set "PES17_RESULT=%ERRORLEVEL%"
echo.
pause
exit /b %PES17_RESULT%
