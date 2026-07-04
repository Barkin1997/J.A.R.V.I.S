@echo off
cd /d "%~dp0"
title Orange Jarvis - KI Bildgenerator
set "LOCK_DIR=%~dp0data\image_generator_start.lock"
if not exist "%~dp0data" mkdir "%~dp0data"
if not exist "%~dp0logs" mkdir "%~dp0logs"
set "LOG_OUT=%~dp0logs\image_generator_last_start.out.log"
set "LOG_ERR=%~dp0logs\image_generator_last_start.err.log"
set "HF_HOME=E:\.cache\huggingface"
set "XDG_CACHE_HOME=E:\.cache"
set "PIP_CACHE_DIR=E:\.cache\pip"
set "TRANSFORMERS_CACHE=E:\.cache\huggingface\transformers"

powershell -NoProfile -ExecutionPolicy Bypass -Command "if(Get-NetTCPConnection -LocalPort 7860 -State Listen -ErrorAction SilentlyContinue){exit 0}else{exit 1}" >nul 2>nul
if not errorlevel 1 (
    echo KI-Bildgenerator laeuft schon auf Port 7860.
    exit /b 0
)

if exist "%LOCK_DIR%" (
    echo KI-Bildgenerator startet bereits. Bitte warten.
    exit /b 0
)
mkdir "%LOCK_DIR%" >nul 2>nul
if errorlevel 1 (
    echo KI-Bildgenerator startet bereits. Bitte warten.
    exit /b 0
)

if not exist external\stable-diffusion-webui (
    echo Stable Diffusion WebUI fehlt.
    echo Starte zuerst install_image_generator.bat
    rmdir "%LOCK_DIR%" >nul 2>nul
    if /I not "%JARVIS_NO_PAUSE%"=="1" pause
    exit /b 1
)

cd external\stable-diffusion-webui
echo Starte lokalen KI-Bildgenerator mit API...
if exist "C:\Users\barki\AppData\Local\Programs\Python\Python310\python.exe" (
    set "PYTHON=C:\Users\barki\AppData\Local\Programs\Python\Python310\python.exe"
) else if exist "%~dp0.venv\Scripts\python.exe" (
    set "PYTHON=%~dp0.venv\Scripts\python.exe"
) else (
    set "PYTHON=python"
)
set PIP_NO_BUILD_ISOLATION=1
set "TORCH_COMMAND=pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128"
set "STABLE_DIFFUSION_REPO=https://github.com/CompVis/stable-diffusion.git"
set "STABLE_DIFFUSION_COMMIT_HASH=21f890f9da3cfbeaba8e2ac3c425ee9e998d5229"
echo Start: %date% %time% > "%LOG_OUT%"
echo Cache: %HF_HOME% >> "%LOG_OUT%"
echo Python: %PYTHON% >> "%LOG_OUT%"
call webui.bat --api --listen --port 7860 --opt-sdp-attention --skip-version-check >> "%LOG_OUT%" 2>> "%LOG_ERR%"
rmdir "%LOCK_DIR%" >nul 2>nul
if /I not "%JARVIS_NO_PAUSE%"=="1" pause
