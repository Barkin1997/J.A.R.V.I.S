@echo off
title JARVIS CODING FAST
cd /d "E:\J.A.R.V.I.S\orange_jarvis_ultra_last_procontrol_easyname"

set OLLAMA_MODEL=qwen3-coder-next:latest
set JARVIS_MODEL=qwen3-coder-next:latest
set OLLAMA_TEXT_MODEL=qwen3-coder-next:latest
set OLLAMA_CODE_MODEL=qwen3-coder-next:latest
set OLLAMA_AGENT_CODE_MODEL=qwen3-coder-next:latest
set OLLAMA_STRONG_CODE_MODEL=qwen3-coder-next:latest
set OLLAMA_BEAST_CODE_MODEL=qwen3-coder-next:latest
set MULTI_AGENT_MODEL=qwen3-coder-next:latest
set PLANNER_MODEL=qwen3-coder-next:latest
set TESTER_MODEL=qwen3-coder-next:latest
set FIXER_MODEL=qwen3-coder-next:latest
set OLLAMA_NUM_CTX=16384
set OLLAMA_TEMPERATURE=0.03
set OLLAMA_TIMEOUT=600
set JARVIS_WORK_TIMEOUT=600
set JARVIS_WORK_STUCK_WARN=90
set JARVIS_AIDER_TIMEOUT=600

echo Starte nur Jarvis Coding. Kein ComfyUI. Kein Stable Diffusion.
echo Modell: qwen3-coder-next:latest
echo Kontext: 16384
echo.

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" app.py
) else (
    python app.py
)

pause
