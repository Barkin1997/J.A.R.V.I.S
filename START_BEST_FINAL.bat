@echo off
cd /d "%~dp0"
title Orange Jarvis BEST FINAL
color 0C

echo =====================================================
echo ORANGE JARVIS BEST FINAL
echo =====================================================
echo.
echo Aktiviert maximale lokale Version:
echo - qwen3-coder:480b fuer Beast-Coding
echo - qwen3-next:80b fuer Text
echo - qwen3-coder-next als schneller Agent
echo - Auto-Build-Test
echo - Auto-Fix-Runden
echo - Git-Snapshot
echo - Bild-KI
echo.

if not exist .env copy .env.example .env >nul

call switch_BEAST_480B.bat

echo Lade starke Modelle, falls sie fehlen...
call pull_models_BEAST_480B.bat

echo Starte alles...
call START_HIER_ALLES.bat
