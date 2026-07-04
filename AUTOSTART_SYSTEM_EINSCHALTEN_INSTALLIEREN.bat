@echo off
cd /d "%~dp0"
title SYSTEM EINSCHALTEN - Autostart installieren
color 0E

set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "SRC=%~dp0System einschalten.bat"
set "DST=%STARTUP%\System einschalten.bat"

if not exist "%SRC%" (
    echo System einschalten.bat nicht gefunden.
    pause
    exit /b 1
)

copy /Y "%SRC%" "%DST%" >nul

echo.
echo Fertig. Beim Windows-Start wird jetzt "System einschalten" ausgefuehrt.
echo.
pause
