@echo off
cd /d "%~dp0"
title Orange Jarvis AI - Alles automatisch laden
color 0E

echo =====================================================
echo ORANGE JARVIS AI - AUTO DOWNLOAD ALL
echo =====================================================
echo.

if not exist external mkdir external
if not exist models mkdir models
if not exist data mkdir data

echo [1/10] Python pruefen/installieren...
py -3 --version >nul 2>&1
if errorlevel 1 (
    where winget >nul 2>&1
    if errorlevel 1 (
        echo Winget fehlt. Python bitte manuell installieren.
        pause
        exit /b 1
    )
    winget install -e --id Python.Python.3.12
)

echo [2/10] Git pruefen/installieren...
where git >nul 2>&1
if errorlevel 1 (
    winget install -e --id Git.Git
)

echo [3/10] Ollama pruefen/installieren...
where ollama >nul 2>&1
if errorlevel 1 (
    winget install -e --id Ollama.Ollama
)

echo [4/10] Python venv + Pakete...
if not exist .venv (
    py -3 -m venv .venv
)
call .venv\Scripts\activate
python -m pip install --upgrade pip setuptools wheel
pip install -r requirements.txt

echo [5/10] Playwright Chromium...
python -m playwright install chromium

echo [6/10] Ollama Server starten...
start "Ollama Server" /min cmd /c "ollama serve"
timeout /t 7 /nobreak >nul

echo [7/10] Alle lokalen KI-Modelle laden...
echo Das kann SEHR lange dauern.
echo qwen3-coder:480b ist extrem gross.
echo.

ollama pull qwen3-coder:480b
ollama pull qwen3-next:80b
ollama pull qwen3-coder-next
ollama pull qwen3-coder:30b
ollama pull deepseek-coder-v2:16b
ollama pull llava:13b
ollama pull nomic-embed-text-v2-moe

echo [8/10] Offline Sprache Vosk Deutsch...
if not exist "models\vosk-model-small-de-0.15" (
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Invoke-WebRequest -Uri 'https://alphacephei.com/vosk/models/vosk-model-small-de-0.15.zip' -OutFile 'models\vosk-model-small-de-0.15.zip'"
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -Path 'models\vosk-model-small-de-0.15.zip' -DestinationPath 'models' -Force"
)

echo [9/10] Stable Diffusion WebUI + SDXL...
if not exist "external\stable-diffusion-webui" (
    git clone https://github.com/AUTOMATIC1111/stable-diffusion-webui.git "external\stable-diffusion-webui"
)

dir /b "external\stable-diffusion-webui\models\Stable-diffusion\*.safetensors" >nul 2>&1
if errorlevel 1 (
    call download_sdxl_model.bat
)

echo [10/11] Tesseract OCR pruefen/installieren...
where tesseract >nul 2>&1
if errorlevel 1 (
    winget install -e --id UB-Mannheim.TesseractOCR
)

echo [11/11] ComfyUI automatisch installieren...
if not exist "external\ComfyUI" (
    call install_comfyui.bat
)

echo.
echo =====================================================
echo AUTO DOWNLOAD FERTIG
echo =====================================================
echo.
exit /b 0
