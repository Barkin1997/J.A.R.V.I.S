@echo off
cd /d "%~dp0"
title ORANGE JARVIS AI - EIN KLICK WATCHED
color 0E

echo Starte Ein-Klick-Installation...
call DOWNLOAD_ALLES_AUTOMATISCH.bat
if errorlevel 1 (
    echo Auto-Download hatte einen Fehler.
    pause
    exit /b 1
)

echo Starte Modell-Manager...
start "Orange Jarvis Modell Manager" cmd /c "cd /d %~dp0 && call START_MODEL_MANAGER_WAIT.bat"

echo Starte Bild-KI API...
start "Orange Jarvis Bild-KI" cmd /c "cd /d %~dp0external\stable-diffusion-webui && webui-user.bat --xformers --api --listen"

if exist "external\ComfyUI" (
    echo Starte ComfyUI...
    start "Orange Jarvis ComfyUI" cmd /c "cd /d %~dp0 && call start_comfyui.bat"
)

echo Starte Jarvis mit Crash-Watcher...
call .venv\Scripts\activate
python crash_watcher.py
pause
