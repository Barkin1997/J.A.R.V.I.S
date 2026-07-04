@echo off
cd /d "%~dp0"
title Orange Jarvis - Echtes KI Video TikTok Alles
color 0E
echo =====================================================
echo ORANGE JARVIS - ECHTES KI VIDEO / TIKTOK / FIGUREN
echo =====================================================
echo.
echo Das installiert echte Video-Modelle:
echo - Text zu Video
echo - Bild/Person zu Video
echo - sprechende Figuren mit Lippenbewegung
echo - 4K+Audio Postprocess bleibt aktiv
echo.
echo Hinweis: Das sind grosse Downloads. Best Pack ca. 50 GB.
echo Ultra optional laedt noch mehr.
echo.
if not exist "external\ComfyUI" (
    echo ComfyUI fehlt. Installiere zuerst Basis...
    call install_comfyui.bat
)
set "JARVIS_SKIP_PAUSE=1"
set "HF_HOME=%~dp0data\huggingface_cache"
set "HF_HUB_CACHE=%~dp0data\huggingface_cache\hub"
set "TRANSFORMERS_CACHE=%~dp0data\huggingface_cache\transformers"
set "HF_XET_CACHE=%~dp0data\huggingface_cache\xet"
call install_video_ai.bat
set "PY=external\ComfyUI\venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"
"%PY%" install_real_video_models.py
if errorlevel 1 (
    echo.
    echo FEHLER beim Best Pack. Siehe Meldung oben.
    pause
    exit /b 1
)
echo.
choice /c JN /m "Ultra-Pack auch laden? Das braucht noch viel mehr Speicher/Zeit"
if errorlevel 2 goto done
"%PY%" install_real_video_models.py --ultra
:done
echo.
echo Fertig. Starte danach start_comfyui.bat.
pause
