@echo off
cd /d "%~dp0"
title Orange Jarvis - ComfyUI
set "LOCK_DIR=%~dp0data\comfyui_start.lock"
if not exist "%~dp0data" mkdir "%~dp0data"
powershell -NoProfile -ExecutionPolicy Bypass -Command "if(Get-NetTCPConnection -LocalPort 8188 -State Listen -ErrorAction SilentlyContinue){exit 0}else{exit 1}" >nul 2>nul
if not errorlevel 1 (
    echo ComfyUI laeuft schon auf Port 8188.
    exit /b 0
)
if exist "%LOCK_DIR%" (
    rmdir "%LOCK_DIR%" >nul 2>nul
)
mkdir "%LOCK_DIR%" >nul 2>nul
if errorlevel 1 (
    echo ComfyUI startet bereits. Kein zweiter Start.
    exit /b 0
)
if not exist external\ComfyUI (
    echo ComfyUI fehlt. install_comfyui.bat starten.
    pause
    rmdir "%LOCK_DIR%" >nul 2>nul
    exit /b 1
)
cd external\ComfyUI
call venv\Scripts\activate
python main.py --listen 127.0.0.1 --port 8188
rmdir "%LOCK_DIR%" >nul 2>nul
pause
