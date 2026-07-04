@echo off
cd /d "%~dp0"
title Orange Jarvis - KI Video Installation
color 0E
echo =====================================================
echo ORANGE JARVIS KI VIDEO
echo =====================================================
echo Installiert ComfyUI Video-Erweiterungen.
echo Echte Videogenerierung braucht passende Video-Modelle.
echo.
where git >nul 2>&1
if errorlevel 1 winget install -e --id Git.Git
if not exist external mkdir external
if not exist "external\ComfyUI" (
    echo ComfyUI fehlt. Installiere ComfyUI...
    call install_comfyui.bat
)
if not exist "external\ComfyUI\custom_nodes" mkdir "external\ComfyUI\custom_nodes"
cd /d "%~dp0external\ComfyUI\custom_nodes"
if not exist "ComfyUI-Manager" git clone https://github.com/Comfy-Org/ComfyUI-Manager.git
if not exist "ComfyUI-VideoHelperSuite" git clone https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git
if not exist "ComfyUI-AnimateDiff-Evolved" git clone https://github.com/Kosinkadink/ComfyUI-AnimateDiff-Evolved.git
if not exist "ComfyUI-WanVideoWrapper" git clone https://github.com/kijai/ComfyUI-WanVideoWrapper.git
cd /d "%~dp0external\ComfyUI"
call venv\Scripts\activate
for /d %%D in (custom_nodes\*) do (
    if exist "%%D\requirements.txt" (
        echo Installiere requirements: %%D
        pip install -r "%%D\requirements.txt"
    )
)
echo.
echo KI Video Installation fertig.
echo Starte danach start_comfyui.bat.
echo Modelle kannst du ueber ComfyUI Manager laden oder in ComfyUI\models legen.
if /I not "%JARVIS_SKIP_PAUSE%"=="1" pause
