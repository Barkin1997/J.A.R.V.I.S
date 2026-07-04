@echo off
title TEST LOCAL CODEX
cd /d "%~dp0"

set OLLAMA_MODEL=qwen3-coder-next:latest
set OLLAMA_CODE_MODEL=qwen3-coder-next:latest
set OLLAMA_BASE_URL=http://127.0.0.1:11434

echo Teste Modell:
ollama run qwen3-coder-next:latest "Antworte nur mit: JARVIS CODEX OK"

echo.
echo Teste Codex-Datei:
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" local_codex_agent.py status
) else (
    python local_codex_agent.py status
)
echo.
pause
