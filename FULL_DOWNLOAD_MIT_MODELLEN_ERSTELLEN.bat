@echo off
setlocal
cd /d "%~dp0"
echo Erstellt ein Full-Download-Verzeichnis MIT Modellen, aber OHNE private Chats, .env und Logs.
echo Das kann je nach Groesse sehr lange dauern.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0MAKE_PUBLIC_RELEASE.ps1" -Mode Full
pause
