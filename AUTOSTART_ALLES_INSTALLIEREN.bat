@echo off
cd /d "%~dp0"
title ORANGE JARVIS - Autostart installieren
color 0E

set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "SRC=%~dp0START_JARVIS_ALLES_AUTOMATISCH_HIDDEN.vbs"
set "DST=%STARTUP%\START_JARVIS_ALLES_AUTOMATISCH_HIDDEN.vbs"

if not exist "%SRC%" (
    echo START_JARVIS_ALLES_AUTOMATISCH_HIDDEN.vbs nicht gefunden.
    pause
    exit /b 1
)

copy /Y "%SRC%" "%DST%" >nul

echo.
echo Fertig. Jarvis startet ab jetzt automatisch mit Windows.
echo.
echo Entfernen:
echo %DST%
echo Datei dort loeschen.
echo.
pause
