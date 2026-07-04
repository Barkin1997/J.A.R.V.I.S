@echo off
title JARVIS ROO CODE
set "JARVIS_ROOT=E:\J.A.R.V.I.S\orange_jarvis_ultra_last_procontrol_easyname"
if exist "%~dp0app.py" set "JARVIS_ROOT=%~dp0"
if "%JARVIS_ROOT:~-1%"=="\" set "JARVIS_ROOT=%JARVIS_ROOT:~0,-1%"
cd /d "%JARVIS_ROOT%"

set OLLAMA_MODEL=qwen3-coder-next:latest
set OLLAMA_TEXT_MODEL=qwen3-coder-next:latest
set OLLAMA_CODE_MODEL=qwen3-coder-next:latest
set OLLAMA_NUM_CTX=16384
set OLLAMA_TEMPERATURE=0.03

where code >nul 2>nul
if errorlevel 1 (
    echo VS Code Befehl 'code' wurde nicht gefunden.
    echo Oeffne VS Code manuell und dann diesen Ordner:
    echo %JARVIS_ROOT%
    pause
    exit /b 1
)

code --install-extension rooveterinaryinc.roo-cline >nul 2>nul
start "" code "%JARVIS_ROOT%\Jarvis_Roo_Code.code-workspace"
echo VS Code mit Jarvis/Roo wurde gestartet.
echo Roo Provider einmal einstellen:
echo Provider: Ollama
echo Base URL: http://localhost:11434
echo Model: qwen3-coder-next:latest
echo Kontext nutzt Ollama num_ctx. Jarvis nutzt 16384.
