@echo off
title JARVIS Direktmodus AN
cd /d "%~dp0"

echo Direktmodus wird aktiviert.
echo Du musst nicht mehr "Jarvis" sagen.
echo.

> "_direct_on.py" echo from pathlib import Path
>> "_direct_on.py" echo env=Path(".env")
>> "_direct_on.py" echo data={}
>> "_direct_on.py" echo if env.exists():
>> "_direct_on.py" echo ^    for line in env.read_text(encoding="utf-8", errors="ignore").splitlines():
>> "_direct_on.py" echo ^        if "=" in line and not line.strip().startswith("#"):
>> "_direct_on.py" echo ^            k,v=line.split("=",1); data[k.strip()]=v.strip()
>> "_direct_on.py" echo data["JARVIS_DIRECT_COMMAND_MODE"]="1"
>> "_direct_on.py" echo env.write_text("\n".join(f"{k}={v}" for k,v in data.items())+"\n", encoding="utf-8")
>> "_direct_on.py" echo print("Direktmodus AN")

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" "_direct_on.py"
) else (
    python "_direct_on.py"
)
del "_direct_on.py" >nul 2>nul
pause
