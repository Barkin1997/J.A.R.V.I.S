@echo off
cd /d "%~dp0"
title Orange Jarvis Ultimate - ALLES STARTEN
color 0E

echo =====================================================
echo ORANGE JARVIS ULTIMATE
echo EIN BUTTON: INSTALLIEREN + STARTEN + MODELLE + BILD-KI
echo =====================================================
echo.

if not exist .env (
    copy .env.example .env >nul
)

if not exist data mkdir data
if not exist models mkdir models
if not exist external mkdir external

echo [1/11] Python pruefen...
py -3 --version >nul 2>&1
if errorlevel 1 (
    echo Python fehlt.
    echo Installation mit winget wird versucht.
    where winget >nul 2>&1
    if errorlevel 1 (
        echo Winget fehlt. Installiere Python manuell:
        echo https://www.python.org/downloads/windows/
        pause
        exit /b 1
    )
    winget install -e --id Python.Python.3.12
)

echo [2/11] Python-Umgebung vorbereiten...
if not exist .venv (
    py -3 -m venv .venv
)
call .venv\Scripts\activate

echo [3/11] Python-Pakete installieren...
python -m pip install --upgrade pip setuptools wheel
pip install -r requirements.txt

echo [4/11] Playwright Browser installieren...
python -m playwright install chromium

echo [5/11] Git pruefen...
where git >nul 2>&1
if errorlevel 1 (
    echo Git fehlt. Installation mit winget wird versucht.
    where winget >nul 2>&1
    if errorlevel 1 (
        echo Winget fehlt. Git manuell installieren.
        pause
        exit /b 1
    )
    winget install -e --id Git.Git
)

echo [6/11] Ollama pruefen...
where ollama >nul 2>&1
if errorlevel 1 (
    echo Ollama fehlt. Installation mit winget wird versucht.
    where winget >nul 2>&1
    if errorlevel 1 (
        echo Winget fehlt. Installiere Ollama manuell:
        echo https://ollama.com/download/windows
        pause
        exit /b 1
    )
    winget install -e --id Ollama.Ollama
)

echo [7/11] Ollama Server starten...
start "Ollama Server" /min cmd /c "ollama serve"
timeout /t 5 /nobreak >nul

echo [8/11] Ollama Modelle laden/pruefen...
ollama list | findstr /i "qwen2.5:14b" >nul 2>&1
if errorlevel 1 ollama pull qwen2.5:14b

ollama list | findstr /i "qwen2.5-coder:14b" >nul 2>&1
if errorlevel 1 ollama pull qwen2.5-coder:14b

ollama list | findstr /i "llava:13b" >nul 2>&1
if errorlevel 1 ollama pull llava:13b

echo [9/11] Offline-Sprachmodell pruefen...
if not exist "models\vosk-model-small-de-0.15" (
    echo Vosk Deutsch wird geladen...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Invoke-WebRequest -Uri 'https://alphacephei.com/vosk/models/vosk-model-small-de-0.15.zip' -OutFile 'models\vosk-model-small-de-0.15.zip'"
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -Path 'models\vosk-model-small-de-0.15.zip' -DestinationPath 'models' -Force"
)

echo [10/11] Stable Diffusion WebUI pruefen...
if not exist "external\stable-diffusion-webui" (
    echo Stable Diffusion WebUI wird installiert...
    git clone https://github.com/AUTOMATIC1111/stable-diffusion-webui.git "external\stable-diffusion-webui"
)

echo [11/11] SDXL Bildmodell pruefen/herunterladen...
dir /b "external\stable-diffusion-webui\models\Stable-diffusion\*.safetensors" >nul 2>&1
if errorlevel 1 (
    echo Kein Bildmodell gefunden.
    echo SDXL Base 1.0 wird automatisch geladen. Das sind ca. 6-7 GB.
    call download_sdxl_model.bat
) else (
    echo Bildmodell gefunden.
)

echo Starte Bild-KI API in eigenem Fenster...
start "Orange Jarvis Bild-KI" cmd /c "cd /d %~dp0external\stable-diffusion-webui && webui-user.bat --xformers --api --listen"

if exist "external\ComfyUI" (
    echo ComfyUI starten...
    start "Orange Jarvis ComfyUI" cmd /c start_comfyui.bat
)

echo Warte auf Bild-KI Start...
timeout /t 8 /nobreak >nul

echo Starte Jarvis...
python app.py
pause
