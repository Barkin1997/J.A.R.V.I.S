@echo off
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0MAKE_PUBLIC_RELEASE.ps1" -Mode Github -Zip
pause
