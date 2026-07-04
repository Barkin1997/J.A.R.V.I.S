@echo off
cd /d "%~dp0"
title Orange Jarvis - Modell Manager Auto
color 0E

echo Warte auf Python-Umgebung...
for /l %%i in (1,1,120) do (
    if exist ".venv\Scripts\activate.bat" goto STARTMANAGER
    timeout /t 5 /nobreak >nul
)

echo Python-Umgebung wurde noch nicht erstellt.
echo Starte START_HIER_ALLES.bat zuerst fertig, danach nochmal Ein-Klick starten.
pause
exit /b 1

:STARTMANAGER
echo Starte Modell-Manager...
call .venv\Scripts\activate
python model_manager_gui.py
pause
