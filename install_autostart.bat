@echo off
cd /d "%~dp0"
set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "SHORTCUT=%STARTUP%\Orange Jarvis Ultimate.lnk"
set "TARGET=%~dp0START_NUR_JARVIS.bat"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$s=(New-Object -COM WScript.Shell).CreateShortcut('%SHORTCUT%'); $s.TargetPath='%TARGET%'; $s.WorkingDirectory='%~dp0'; $s.IconLocation='%SystemRoot%\System32\Shell32.dll,220'; $s.Save()"
echo Autostart aktiviert.
echo Jarvis startet ab jetzt beim Windows-Login.
pause
