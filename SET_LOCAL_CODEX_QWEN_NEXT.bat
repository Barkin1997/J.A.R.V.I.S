@echo off
title JARVIS Lokaler Codex Modus aktivieren
cd /d "%~dp0"

echo.
echo ===============================================
echo  JARVIS LOKALER CODEX-MODUS
echo ===============================================
echo Modell: qwen3-coder-next:latest
echo 3D wird NICHT geaendert.
echo.

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

> "_set_local_codex.py" echo from pathlib import Path
>> "_set_local_codex.py" echo model="qwen3-coder-next:latest"
>> "_set_local_codex.py" echo env=Path(".env")
>> "_set_local_codex.py" echo data={}
>> "_set_local_codex.py" echo if env.exists():
>> "_set_local_codex.py" echo ^    for line in env.read_text(encoding="utf-8", errors="ignore").splitlines():
>> "_set_local_codex.py" echo ^        line=line.strip("\ufeff")
>> "_set_local_codex.py" echo ^        if "=" in line and not line.strip().startswith("#"):
>> "_set_local_codex.py" echo ^            k,v=line.split("=",1); data[k.strip()]=v.strip()
>> "_set_local_codex.py" echo keys=["OLLAMA_MODEL","JARVIS_MODEL","MODEL_NAME","LLM_MODEL","OLLAMA_TEXT_MODEL","OLLAMA_CODE_MODEL","OLLAMA_MAX_CODE_MODEL","OLLAMA_AGENT_CODE_MODEL","OLLAMA_STRONG_CODE_MODEL","OLLAMA_BEAST_CODE_MODEL","MULTI_AGENT_MODEL","PLANNER_MODEL","TESTER_MODEL","FIXER_MODEL","SECURITY_MODEL","FEEDBACK_MODEL"]
>> "_set_local_codex.py" echo for k in keys:
>> "_set_local_codex.py" echo ^    data[k]=model
>> "_set_local_codex.py" echo data["OLLAMA_BASE_URL"]="http://127.0.0.1:11434"
>> "_set_local_codex.py" echo data["OLLAMA_URL"]="http://localhost:11434"
>> "_set_local_codex.py" echo env.write_text("\n".join(f"{k}={v}" for k,v in data.items())+"\n", encoding="utf-8")
>> "_set_local_codex.py" echo print("Lokaler Codex aktiv:", model)

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" "_set_local_codex.py"
) else (
    python "_set_local_codex.py"
)

del "_set_local_codex.py" >nul 2>nul

echo.
echo Teste lokaler Codex:
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" local_codex_agent.py status
) else (
    python local_codex_agent.py status
)

echo.
echo Fertig.
echo Danach Jarvis starten: System einschalten
echo.
pause
