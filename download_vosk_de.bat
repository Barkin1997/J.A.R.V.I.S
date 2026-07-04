@echo off
cd /d "%~dp0"
if not exist models mkdir models
cd models
echo Deutsches Offline-Sprachmodell wird geladen...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
 "Invoke-WebRequest -Uri 'https://alphacephei.com/vosk/models/vosk-model-small-de-0.15.zip' -OutFile 'vosk-model-small-de-0.15.zip'"
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
 "Expand-Archive -Path 'vosk-model-small-de-0.15.zip' -DestinationPath '.' -Force"
echo Fertig.
pause
