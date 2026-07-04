@echo off
setlocal
cd /d "%~dp0"
echo.
echo J.A.R.V.I.S Modelle von GitHub installieren
echo ==========================================
echo.
echo Das kann sehr lange dauern, weil die Modelle sehr gross sind.
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\install_models_from_github.ps1"
echo.
pause
