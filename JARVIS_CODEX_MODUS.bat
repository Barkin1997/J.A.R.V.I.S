@echo off
title JARVIS Lokaler Codex PRO
cd /d "%~dp0"

set OLLAMA_MODEL=qwen3-coder-next:latest
set OLLAMA_TEXT_MODEL=qwen3-coder-next:latest
set OLLAMA_CODE_MODEL=qwen3-coder-next:latest
set OLLAMA_BASE_URL=http://127.0.0.1:11434

if "%~1"=="" (
    echo Beispiele:
    echo JARVIS_CODEX_MODUS.bat status
    echo JARVIS_CODEX_MODUS.bat index
    echo JARVIS_CODEX_MODUS.bat suche OLLAMA_MODEL
    echo JARVIS_CODEX_MODUS.bat lese app.py
    echo JARVIS_CODEX_MODUS.bat pruefe dich
    echo JARVIS_CODEX_MODUS.bat repariere app.py
    echo.
    pause
    exit /b
)

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" local_codex_agent.py %*
) else (
    python local_codex_agent.py %*
)

echo.
pause
