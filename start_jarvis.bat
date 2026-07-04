@echo off
cd /d "%~dp0"
title Orange Jarvis Ultimate
if not exist .venv (
    call install_windows.bat
)
call .venv\Scripts\activate
python app.py
pause
