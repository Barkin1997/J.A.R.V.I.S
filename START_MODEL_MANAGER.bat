@echo off
cd /d "%~dp0"
title Orange Jarvis - Modell Manager
if not exist .venv (
    echo .venv fehlt. Starte zuerst START_HIER_ALLES.bat
    pause
    exit /b 1
)
call .venv\Scripts\activate
python model_manager_gui.py
pause
