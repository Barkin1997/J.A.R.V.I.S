@echo off
title Orange Jarvis ULTRA - Full Dev Tools
color 0E

where winget >nul 2>&1
if errorlevel 1 (
    echo Winget fehlt. Installation abgebrochen.
    pause
    exit /b 1
)

echo Installiere komplette Entwickler-Werkzeuge...
winget install -e --id Git.Git
winget install -e --id Python.Python.3.12
winget install -e --id OpenJS.NodeJS.LTS
winget install -e --id Microsoft.DotNet.SDK.8
winget install -e --id EclipseAdoptium.Temurin.21.JDK
winget install -e --id Rustlang.Rustup
winget install -e --id GoLang.Go
winget install -e --id Kitware.CMake
winget install -e --id Ninja-build.Ninja
winget install -e --id Microsoft.VisualStudioCode
winget install -e --id Microsoft.VisualStudio.2022.BuildTools

echo.
echo Wichtig fuer C++:
echo Visual Studio Installer oeffnen und Workload "Desktop development with C++" aktivieren.
echo Danach PC neu starten.
pause
