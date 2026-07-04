@echo off
cd /d "%~dp0"
title Orange Jarvis - KI Bildgenerator Installation

echo ==========================================
echo KI-Bildgenerator lokal installieren
echo Stable Diffusion WebUI + API
echo ==========================================
echo.

if not exist external mkdir external

where git >nul 2>&1
if errorlevel 1 (
    echo Git fehlt. Installation mit winget...
    winget install -e --id Git.Git
)

where python >nul 2>&1
if errorlevel 1 (
    echo Python fehlt. Installation mit winget...
    winget install -e --id Python.Python.3.10
)

cd external

if not exist stable-diffusion-webui (
    git clone https://github.com/AUTOMATIC1111/stable-diffusion-webui.git
)

cd stable-diffusion-webui

echo.
echo SDXL-Modell muss in diesen Ordner:
echo external\stable-diffusion-webui\models\Stable-diffusion
echo.
echo Du kannst eine .safetensors Datei dort hineinlegen.
echo Danach start_image_generator.bat starten.
echo.
echo WebUI-Erststart wird vorbereitet...
call webui-user.bat --skip-torch-cuda-test --xformers --api

pause
