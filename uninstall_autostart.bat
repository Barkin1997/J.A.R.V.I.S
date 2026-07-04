@echo off
set "SHORTCUT=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\Orange Jarvis Ultimate.lnk"
if exist "%SHORTCUT%" del "%SHORTCUT%"
echo Autostart deaktiviert.
pause
