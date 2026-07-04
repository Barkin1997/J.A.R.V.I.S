@echo off
cd /d "%~dp0"
title Orange Jarvis Ultimate - Schnellstart
start "Ollama Server" /min cmd /c "ollama serve"

if exist "external\stable-diffusion-webui" (
    start "Orange Jarvis Bild-KI" cmd /c "cd /d %~dp0external\stable-diffusion-webui && webui-user.bat --xformers --api --listen"
)

if not exist .venv (
    call START_HIER_ALLES.bat
    exit /b
)

call .venv\Scripts\activate
echo BEAST-Modell pruefen...
findstr /i "OLLAMA_CODE_MODEL=qwen3-coder:480b" .env >nul 2>&1
if not errorlevel 1 (
    ollama list | findstr /i "qwen3-coder:480b" >nul 2>&1
    if errorlevel 1 (
        echo WARNUNG: qwen3-coder:480b ist nicht geladen.
        echo Starte pull_models_BEAST_480B.bat oder switch_AGENT_FAST.bat.
    )
)
python app.py
pause
