@echo off
cd /d "%~dp0"
title Orange Jarvis ULTRA Strongest Internet
color 0C

if not exist .env copy .env.example .env >nul

call switch_ULTRA_STRONGEST.bat

echo Lade Ultra-Modelle...
call pull_models_BEAST_480B.bat

echo Starte alles mit Internet-Browser-Agent...
call START_HIER_ALLES.bat
