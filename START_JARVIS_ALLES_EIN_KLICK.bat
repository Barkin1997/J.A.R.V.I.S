@echo off
cd /d "%~dp0"
title ORANGE JARVIS AI - EIN KLICK START
color 0E

echo =====================================================
echo ORANGE JARVIS AI - EIN KLICK START
echo =====================================================
echo.
echo Startet und installiert automatisch:
echo - Ultra Strongest Profil
echo - Python Pakete
echo - Playwright Browser
echo - Ollama
echo - alle starken KI-Modelle
echo - Vosk Sprache
echo - Stable Diffusion WebUI
echo - SDXL Bildmodell
echo - ComfyUI
echo - Jarvis GUI
echo - Modell-Manager
echo.

if not exist .env copy .env.example .env >nul

echo Aktiviere Ultra Strongest Profil...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
 "$p='.env'; $t=Get-Content $p -Raw; $t=$t -replace 'OLLAMA_TEXT_MODEL=.*','OLLAMA_TEXT_MODEL=qwen3-coder:480b'; $t=$t -replace 'OLLAMA_CODE_MODEL=.*','OLLAMA_CODE_MODEL=qwen3-coder:480b'; $t=$t -replace 'OLLAMA_AGENT_CODE_MODEL=.*','OLLAMA_AGENT_CODE_MODEL=qwen3-coder:480b'; $t=$t -replace 'OLLAMA_STRONG_CODE_MODEL=.*','OLLAMA_STRONG_CODE_MODEL=qwen3-coder:480b'; $t=$t -replace 'OLLAMA_BEAST_CODE_MODEL=.*','OLLAMA_BEAST_CODE_MODEL=qwen3-coder:480b'; $t=$t -replace 'MULTI_AGENT_MODEL=.*','MULTI_AGENT_MODEL=qwen3-coder:480b'; $t=$t -replace 'PLANNER_MODEL=.*','PLANNER_MODEL=qwen3-coder:480b'; $t=$t -replace 'TESTER_MODEL=.*','TESTER_MODEL=qwen3-coder:480b'; $t=$t -replace 'FIXER_MODEL=.*','FIXER_MODEL=qwen3-coder:480b'; $t=$t -replace 'SECURITY_MODEL=.*','SECURITY_MODEL=qwen3-coder:480b'; $t=$t -replace 'INTERNET_RESEARCH_MODEL=.*','INTERNET_RESEARCH_MODEL=qwen3-coder:480b'; $t=$t -replace 'OLLAMA_EMBED_MODEL=.*','OLLAMA_EMBED_MODEL=nomic-embed-text-v2-moe'; $t=$t -replace 'OLLAMA_NUM_CTX=.*','OLLAMA_NUM_CTX=65536'; $t=$t -replace 'OLLAMA_TEMPERATURE=.*','OLLAMA_TEMPERATURE=0.04'; $t=$t -replace 'MODEL_MANAGER_PROFILE=.*','MODEL_MANAGER_PROFILE=ultra'; Set-Content $p $t -Encoding UTF8"

echo Lade alles automatisch...
call DOWNLOAD_ALLES_AUTOMATISCH.bat
if errorlevel 1 (
    echo Auto-Download hatte einen Fehler.
    pause
    exit /b 1
)

echo Starte Modell-Manager...
start "Orange Jarvis Modell Manager" cmd /c "cd /d %~dp0 && call START_MODEL_MANAGER_WAIT.bat"

echo Starte Bild-KI API...
start "Orange Jarvis Bild-KI" cmd /c "cd /d %~dp0external\stable-diffusion-webui && webui-user.bat --xformers --api --listen"

if exist "external\ComfyUI" (
    echo Starte ComfyUI...
    start "Orange Jarvis ComfyUI" cmd /c "cd /d %~dp0 && call start_comfyui.bat"
)

echo Starte Jarvis mit Crash-Watcher...
call .venv\Scripts\activate
python crash_watcher.py
pause
