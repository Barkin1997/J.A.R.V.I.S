@echo off
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
 "$p='.env'; $t=Get-Content $p -Raw; $t=$t -replace 'OLLAMA_CODE_MODEL=.*','OLLAMA_CODE_MODEL=qwen2.5-coder:32b'; $t=$t -replace 'OLLAMA_NUM_CTX=.*','OLLAMA_NUM_CTX=8192'; Set-Content $p $t -Encoding UTF8"
echo Aktiv: maximaler 32B Coding-Modus. Langsamer, aber staerker.
pause
