@echo off
setlocal
chcp 65001 >nul
echo Coletor de recursos PES 3 para FPSoccer
echo Selecione a pasta da ISO extraida. A coleta pode levar alguns minutos.
powershell.exe -NoLogo -NoProfile -STA -ExecutionPolicy Bypass -File "%~dp0coletar-pes3.ps1" -PastaIso "%~1"
set "PES3_EXIT=%ERRORLEVEL%"
echo.
if not "%PES3_EXIT%"=="0" echo A coleta terminou com codigo %PES3_EXIT%. A mensagem acima explica o motivo.
pause
exit /b %PES3_EXIT%
