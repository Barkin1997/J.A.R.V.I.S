@echo off
cd /d "%~dp0"
title SYSTEM EINSCHALTEN - Desktop Button erstellen
color 0E

set "TARGET=%~dp0System einschalten.bat"
set "ICON=%~dp0assets\system_einschalten.ico"
set "NAME=System einschalten.lnk"

if not exist "%TARGET%" (
    echo System einschalten.bat wurde nicht gefunden.
    pause
    exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -Command "$Desktop=[Environment]::GetFolderPath('Desktop'); $Wsh=New-Object -ComObject WScript.Shell; $Shortcut=$Wsh.CreateShortcut((Join-Path $Desktop '%NAME%')); $Shortcut.TargetPath='%TARGET%'; $Shortcut.WorkingDirectory='%~dp0'; $Shortcut.Description='Startet Ollama, ComfyUI, KI-Video und Jarvis'; if(Test-Path '%ICON%'){ $Shortcut.IconLocation='%ICON%' } ; $Shortcut.Save()"

echo.
echo Fertig.
echo Auf deinem Desktop ist jetzt der Button:
echo System einschalten
echo.
pause
