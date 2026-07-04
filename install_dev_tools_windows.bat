@echo off
title Orange Jarvis - Entwickler Tools
echo Installiert Entwicklerwerkzeuge mit winget.
echo.

where winget >nul 2>&1
if errorlevel 1 (
    echo Winget fehlt. Installation abgebrochen.
    pause
    exit /b 1
)

winget install -e --id Git.Git
winget install -e --id Python.Python.3.12
winget install -e --id OpenJS.NodeJS.LTS
winget install -e --id Microsoft.VisualStudioCode

echo.
echo Fuer C++ Compiler:
echo Installiere Visual Studio Build Tools mit C++ Workload.
echo Wenn winget die Workload nicht setzt, manuell im Installer "Desktop development with C++" waehlen.
winget install -e --id Microsoft.VisualStudio.2022.BuildTools

echo.
echo Danach PC neu starten.
pause
