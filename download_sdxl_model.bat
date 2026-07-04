@echo off
cd /d "%~dp0"
title Orange Jarvis - SDXL Bildmodell Download
color 0E

set "MODEL_DIR=%~dp0external\stable-diffusion-webui\models\Stable-diffusion"
set "MODEL_FILE=%MODEL_DIR%\sd_xl_base_1.0.safetensors"
set "MODEL_URL=https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/resolve/main/sd_xl_base_1.0.safetensors?download=true"

if not exist "%MODEL_DIR%" mkdir "%MODEL_DIR%"

if exist "%MODEL_FILE%" (
    echo SDXL Modell ist schon vorhanden:
    echo %MODEL_FILE%
    pause
    exit /b 0
)

echo SDXL Base 1.0 wird heruntergeladen.
echo Datei: ca. 6-7 GB
echo Ziel:
echo %MODEL_FILE%
echo.
echo Download startet...
echo.

curl.exe -L --retry 5 --retry-delay 10 -C - -o "%MODEL_FILE%" "%MODEL_URL%"

if errorlevel 1 (
    echo.
    echo Download fehlgeschlagen.
    echo Loesche unvollstaendige Datei nicht automatisch.
    echo Du kannst den Befehl erneut starten; curl versucht fortzusetzen.
    echo.
    pause
    exit /b 1
)

echo.
echo Fertig:
echo %MODEL_FILE%
pause
