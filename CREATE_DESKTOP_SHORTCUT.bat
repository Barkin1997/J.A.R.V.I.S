@echo off
cd /d "%~dp0"
set "SHORTCUT=%USERPROFILE%\Desktop\Orange Jarvis Ultimate.lnk"
set "TARGET=%~dp0ONE_KEY_START_HIDDEN.vbs"

powershell -NoProfile -ExecutionPolicy Bypass -Command "$s=(New-Object -COM WScript.Shell).CreateShortcut('%SHORTCUT%'); $s.TargetPath='wscript.exe'; $s.Arguments='""%TARGET%""'; $s.WorkingDirectory='%~dp0'; $s.IconLocation='%SystemRoot%\System32\Shell32.dll,220'; $s.Save()"

echo Desktop-Verknuepfung erstellt:
echo %SHORTCUT%
pause
