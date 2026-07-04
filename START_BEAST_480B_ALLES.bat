@echo off
cd /d "%~dp0"
title Orange Jarvis BEAST 480B - Alles Starten
color 0C

echo =====================================================
echo ORANGE JARVIS BEAST 480B
echo =====================================================
echo.
echo Startet Installation, Bild-KI und BEAST-Modelle.
echo Der erste Start kann sehr lange dauern.
echo.

if not exist .env copy .env.example .env >nul

call switch_BEAST_480B.bat

echo Starte Basisinstallation...
call START_HIER_ALLES.bat

echo Lade BEAST-Modelle...
call pull_models_BEAST_480B.bat

echo Starte Jarvis im BEAST-Modus...
call START_NUR_JARVIS.bat
