@echo off
cd /d "%~dp0"
title Orange Jarvis - KI Video Update anwenden
color 0E
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate
    python apply_ki_video_update.py
) else (
    py -3 apply_ki_video_update.py
)
pause
