@echo off
title JARVIS DEBUG START
cd /d "%~dp0"

set OLLAMA_MODEL=qwen3-coder-next:latest
set JARVIS_MODEL=qwen3-coder-next:latest
set MODEL_NAME=qwen3-coder-next:latest
set LLM_MODEL=qwen3-coder-next:latest
set OLLAMA_TEXT_MODEL=qwen3-coder-next:latest
set OLLAMA_CODE_MODEL=qwen3-coder-next:latest
set OLLAMA_MAX_CODE_MODEL=qwen3-coder-next:latest
set OLLAMA_AGENT_CODE_MODEL=qwen3-coder-next:latest
set OLLAMA_STRONG_CODE_MODEL=qwen3-coder-next:latest
set OLLAMA_BEAST_CODE_MODEL=qwen3-coder-next:latest
set OLLAMA_BASE_URL=http://127.0.0.1:11434
set JARVIS_DIRECT_COMMAND_MODE=1

echo DEBUG START - Fenster bleibt offen
echo KI/Codex-Modell: qwen3-coder-next:latest
echo 3D bleibt unveraendert.
echo.

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" app.py
) else (
    python app.py
)

echo.
pause
