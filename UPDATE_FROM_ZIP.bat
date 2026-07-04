@echo off
cd /d "%~dp0"
set /p ZIPPFAD=Pfad zur neuen ZIP-Datei eingeben: 
call .venv\Scripts\activate
python updater.py "%ZIPPFAD%"
pause
