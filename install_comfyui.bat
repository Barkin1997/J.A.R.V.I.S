@echo off
cd /d "%~dp0"
title Orange Jarvis - ComfyUI Installation
color 0E

if not exist external mkdir external

where git >nul 2>&1
if errorlevel 1 winget install -e --id Git.Git

cd external

if not exist ComfyUI (
    git clone https://github.com/comfyanonymous/ComfyUI.git
)

cd ComfyUI

py -3 -m venv venv
call venv\Scripts\activate
python -m pip install --upgrade pip
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
pip install -r requirements.txt

echo.
echo ComfyUI installiert.
echo Modelle nach external\ComfyUI\models\checkpoints kopieren.
pause
