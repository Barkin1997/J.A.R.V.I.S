@echo off
cd /d "%~dp0"
title Orange Jarvis Ultimate - Installation

echo [1/5] Python-Venv erstellen...
if not exist .venv (
    py -3 -m venv .venv
)
call .venv\Scripts\activate

echo [2/5] Pip aktualisieren...
python -m pip install --upgrade pip setuptools wheel

echo [3/5] Pakete installieren...
pip install -r requirements.txt

echo [4/5] Playwright Browser installieren...
python -m playwright install chromium

echo [5/5] Ordner und .env...
if not exist .env copy .env.example .env
if not exist data mkdir data
if not exist models mkdir models

echo.
echo Fertig.
echo Danach pull_models_rtx5080.bat starten.
pause
