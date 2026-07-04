@echo off
cd /d "%~dp0"
title Starte Jarvis KI - Desktop Button
color 0E

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
 "$Desktop=[Environment]::GetFolderPath('Desktop');" ^
 "$Target=(Resolve-Path '.\Starte Jarvis KI.bat').Path;" ^
 "$Icon=(Resolve-Path '.\assets\ORANGE_JARVIS_AI.ico').Path;" ^
 "$Shortcut=Join-Path $Desktop 'Starte Jarvis KI.lnk';" ^
 "$Wsh=New-Object -ComObject WScript.Shell;" ^
 "$Lnk=$Wsh.CreateShortcut($Shortcut);" ^
 "$Lnk.TargetPath=$Target;" ^
 "$Lnk.WorkingDirectory=(Get-Location).Path;" ^
 "$Lnk.IconLocation=$Icon;" ^
 "$Lnk.Description='Starte Jarvis KI';" ^
 "$Lnk.Save();"

echo Desktop-Button erstellt:
echo Starte Jarvis KI
pause
