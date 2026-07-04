@echo off
title JARVIS 3D Desktop Engine installieren
cd /d "%~dp0"

echo.
echo ===============================================
echo  JARVIS 3D DESKTOP ENGINE REPARIEREN
echo ===============================================
echo.

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -m pip install --upgrade pip
    ".venv\Scripts\python.exe" -m pip install --upgrade PySide6 PySide6-Addons PySide6-Essentials
) else (
    python -m pip install --upgrade pip
    python -m pip install --upgrade PySide6 PySide6-Addons PySide6-Essentials
)

echo.
echo Fertig. Starte danach wieder: System einschalten
pause
