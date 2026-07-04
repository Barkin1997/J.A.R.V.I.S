@echo off
cd /d "%~dp0"
title ORANGE JARVIS - ALLES AUTOMATISCH STARTEN
color 0E

echo =====================================================
echo ORANGE JARVIS - ALLES AUTOMATISCH
echo =====================================================
echo.
echo Starte Ollama, ComfyUI und Jarvis automatisch.
echo Fenster bitte nicht schliessen, wenn Bild/KI-Video laufen soll.
echo.

echo [1/4] Starte Ollama...
where ollama >nul 2>&1
if %errorlevel%==0 (
    start "Ollama Server" /min cmd /c "ollama serve"
) else (
    echo Ollama wurde nicht im PATH gefunden. Jarvis startet trotzdem.
)

timeout /t 4 /nobreak >nul

echo [2/4] Starte ComfyUI fuer KI-Bilder/KI-Videos...
if exist "start_comfyui.bat" (
    start "ComfyUI - NICHT SCHLIESSEN" cmd /k call "start_comfyui.bat"
) else (
    echo start_comfyui.bat nicht gefunden. Ueberspringe ComfyUI.
)

timeout /t 8 /nobreak >nul

echo [3/4] Oeffne ComfyUI im Browser...
start "" "http://127.0.0.1:8188"

timeout /t 2 /nobreak >nul

echo [4/4] Starte Jarvis...
if exist "Starte Jarvis KI.bat" (
    call "Starte Jarvis KI.bat"
) else if exist "START_JARVIS_ALLES_EIN_KLICK.bat" (
    call "START_JARVIS_ALLES_EIN_KLICK.bat"
) else if exist "START_HIER_ALLES.bat" (
    call "START_HIER_ALLES.bat"
) else if exist "start_jarvis.bat" (
    call "start_jarvis.bat"
) else (
    echo Keine Jarvis-Startdatei gefunden.
    pause
)
