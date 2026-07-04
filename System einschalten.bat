@echo off
title System einschalten
set "JARVIS_ROOT=E:\J.A.R.V.I.S\orange_jarvis_ultra_last_procontrol_easyname"
if exist "%~dp0app.py" set "JARVIS_ROOT=%~dp0"
if "%JARVIS_ROOT:~-1%"=="\" set "JARVIS_ROOT=%JARVIS_ROOT:~0,-1%"
cd /d "%JARVIS_ROOT%"

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
set MULTI_AGENT_MODEL=qwen3-coder-next:latest
set PLANNER_MODEL=qwen3-coder-next:latest
set TESTER_MODEL=qwen3-coder-next:latest
set FIXER_MODEL=qwen3-coder-next:latest
set SECURITY_MODEL=qwen3-coder-next:latest
set INTERNET_RESEARCH_MODEL=qwen3-coder-next:latest
set OLLAMA_BASE_URL=http://127.0.0.1:11434
set OLLAMA_NUM_CTX=32768
set OLLAMA_TEMPERATURE=0.03
set OLLAMA_TIMEOUT=600
set JARVIS_WORK_TIMEOUT=600
set JARVIS_WORK_STUCK_WARN=90
set JARVIS_AIDER_TIMEOUT=600
set JARVIS_AIDER_AUTO_ROLLBACK=1
set JARVIS_AIDER_LIVE_WINDOW=1
set JARVIS_AIDER_STUCK_WARN=75
set JARVIS_BROWSER_SMOKE_TEST=1
set JARVIS_CODEX_FOCUS_FILES=1
set JARVIS_IMAGE_AUTO_START=1
set JARVIS_VIDEO_AUTO_START=1
set JARVIS_DIRECT_COMMAND_MODE=1
set JARVIS_ALWAYS_RESEARCH_CODE=1
set JARVIS_AUTO_PROJECT_TESTS=1
set JARVIS_START_ROO_CODE=1
set JARVIS_MINIMIZE_ROO_CODE=1
set JARVIS_NO_PAUSE=1

echo Starte JARVIS...
echo KI/Codex-Modell: qwen3-coder-next:latest
echo Coding-Kontext: 32768
echo Direktmodus aktiv: kein Jarvis-Wort noetig.
echo Internet-Recherche fuer Code: aktiv.
echo Auto-Projekttests/Fehlerdatenbank: aktiv.
echo Aider laeuft in Jarvis integriert. Kein extra Aider-Fenster noetig.
if "%JARVIS_START_ROO_CODE%"=="1" (
    echo Roo Code/VS Code wird minimiert mit dem Jarvis-Workspace geoeffnet.
) else (
    echo Roo Code/VS Code Autostart ist aus.
)
echo 3D bleibt unveraendert.
echo.

if exist "start_ollama.bat" start /min "" "start_ollama.bat"

powershell -NoProfile -ExecutionPolicy Bypass -Command "if(Get-NetTCPConnection -LocalPort 8188 -State Listen -ErrorAction SilentlyContinue){exit 0}else{exit 1}" >nul 2>nul
if errorlevel 1 (
    if exist "start_comfyui.bat" start /min "" "start_comfyui.bat"
) else (
    echo ComfyUI laeuft schon auf Port 8188 - starte nicht doppelt.
)

if exist "start_image_generator.bat" start /min "" "start_image_generator.bat"
if exist "start_stable_diffusion.bat" start /min "" "start_stable_diffusion.bat"
if exist "start_services.bat" start /min "" "start_services.bat"

timeout /t 2 /nobreak >nul

if "%JARVIS_START_ROO_CODE%"=="1" (
    where code >nul 2>nul
    if not errorlevel 1 (
        if "%JARVIS_MINIMIZE_ROO_CODE%"=="1" (
            start /min "" code "%JARVIS_ROOT%\Jarvis_Roo_Code.code-workspace"
        ) else (
            start "" code "%JARVIS_ROOT%\Jarvis_Roo_Code.code-workspace"
        )
    )
)

powershell -NoProfile -ExecutionPolicy Bypass -Command "$p=Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -like '*app.py*' }; if($p){exit 0}else{exit 1}" >nul 2>nul
if not errorlevel 1 (
    echo Jarvis app.py laeuft schon - starte nicht doppelt.
    echo Du kannst das vorhandene Jarvis-Fenster benutzen.
) else if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" app.py
) else (
    python app.py
)

echo.
echo JARVIS wurde beendet oder hatte einen Fehler.
echo Bitte Screenshot von diesem Fenster senden.
pause
