@echo off
title ORANGE JARVIS - Autostart entfernen
color 0E

set "DST=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\START_JARVIS_ALLES_AUTOMATISCH_HIDDEN.vbs"

if exist "%DST%" (
    del "%DST%"
    echo Autostart entfernt.
) else (
    echo Kein Jarvis-Autostart gefunden.
)

pause
