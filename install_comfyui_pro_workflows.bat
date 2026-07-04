@echo off
cd /d "%~dp0"
title Orange Jarvis - ComfyUI Pro Workflows
color 0E

if not exist external\ComfyUI (
    echo ComfyUI fehlt. Starte zuerst install_comfyui.bat
    pause
    exit /b 1
)

echo Workflow-Vorlagen liegen hier:
echo %~dp0comfyui_workflows
echo.
echo Ziehe die JSON-Dateien per Drag and Drop in ComfyUI.
echo.
pause
