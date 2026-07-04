@echo off
cd /d "%~dp0"
title Orange Jarvis - Crash Watcher
color 0E

if not exist .venv (
    echo .venv fehlt. Starte zuerst START_JARVIS_ALLES_EIN_KLICK.bat
    pause
    exit /b 1
)

call .venv\Scripts\activate
python crash_watcher.py
pause
