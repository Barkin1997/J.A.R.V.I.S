@echo off
title JARVIS Direktmodus AUS
cd /d "%~dp0"

echo Direktmodus wird deaktiviert.
echo Danach wieder mit "Jarvis" ansprechen.
echo.

> "_direct_off.py" echo from pathlib import Path
>> "_direct_off.py" echo env=Path(".env")
>> "_direct_off.py" echo data={}
>> "_direct_off.py" echo if env.exists():
>> "_direct_off.py" echo ^    for line in env.read_text(encoding="utf-8", errors="ignore").splitlines():
>> "_direct_off.py" echo ^        if "=" in line and not line.strip().startswith("#"):
>> "_direct_off.py" echo ^            k,v=line.split("=",1); data[k.strip()]=v.strip()
>> "_direct_off.py" echo data["JARVIS_DIRECT_COMMAND_MODE"]="0"
>> "_direct_off.py" echo env.write_text("\n".join(f"{k}={v}" for k,v in data.items())+"\n", encoding="utf-8")
>> "_direct_off.py" echo print("Direktmodus AUS")

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" "_direct_off.py"
) else (
    python "_direct_off.py"
)
del "_direct_off.py" >nul 2>nul
pause
