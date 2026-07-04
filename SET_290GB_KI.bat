@echo off
title JARVIS 290GB KI aktivieren
cd /d "%~dp0"

echo.
echo ===============================================
echo  JARVIS 290GB KI AKTIVIEREN
echo ===============================================
echo Modell: qwen3-coder:480b
echo.

set OLLAMA_MODEL=qwen3-coder:480b
set JARVIS_MODEL=qwen3-coder:480b
set MODEL_NAME=qwen3-coder:480b
set LLM_MODEL=qwen3-coder:480b
set OLLAMA_BASE_URL=http://127.0.0.1:11434

> "_set_290gb_env.py" echo from pathlib import Path
>> "_set_290gb_env.py" echo model="qwen3-coder:480b"
>> "_set_290gb_env.py" echo env=Path(".env")
>> "_set_290gb_env.py" echo data={}
>> "_set_290gb_env.py" echo if env.exists():
>> "_set_290gb_env.py" echo ^    for line in env.read_text(encoding="utf-8", errors="ignore").splitlines():
>> "_set_290gb_env.py" echo ^        if "=" in line and not line.strip().startswith("#"):
>> "_set_290gb_env.py" echo ^            k,v=line.split("=",1)
>> "_set_290gb_env.py" echo ^            data[k.strip()]=v.strip()
>> "_set_290gb_env.py" echo data["OLLAMA_MODEL"]=model
>> "_set_290gb_env.py" echo data["JARVIS_MODEL"]=model
>> "_set_290gb_env.py" echo data["MODEL_NAME"]=model
>> "_set_290gb_env.py" echo data["LLM_MODEL"]=model
>> "_set_290gb_env.py" echo data["OLLAMA_BASE_URL"]="http://127.0.0.1:11434"
>> "_set_290gb_env.py" echo env.write_text("\n".join(f"{k}={v}" for k,v in data.items())+"\n", encoding="utf-8")
>> "_set_290gb_env.py" echo print(".env aktualisiert:", model)

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" "_set_290gb_env.py"
) else (
    python "_set_290gb_env.py"
)

del "_set_290gb_env.py" >nul 2>nul

echo.
echo Teste Ollama...
ollama list
echo.
echo Wenn oben qwen3-coder:480b steht, passt alles.
echo.
pause
