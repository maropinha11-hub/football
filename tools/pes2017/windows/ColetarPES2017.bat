@echo off
setlocal
cd /d "%~dp0"
echo Coleta de inventario local do PES 2017
echo Selecione PES2017.exe. O programa nao sera executado ou alterado.
powershell.exe -NoLogo -NoProfile -STA -ExecutionPolicy Bypass -File "%~dp0coletar-pes2017.ps1" -Executavel "%~1"
set "PES17_RESULT=%ERRORLEVEL%"
echo.
pause
exit /b %PES17_RESULT%
