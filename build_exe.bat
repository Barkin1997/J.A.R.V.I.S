@echo off
cd /d "%~dp0"
call .venv\Scripts\activate
pip install pyinstaller
pyinstaller --noconsole --onefile --name OrangeJarvisUltimate app.py
echo Fertig: dist\OrangeJarvisUltimate.exe
pause
