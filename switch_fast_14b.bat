@echo off
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
 "$p='.env'; $t=Get-Content $p -Raw; $t=$t -replace 'OLLAMA_CODE_MODEL=.*','OLLAMA_CODE_MODEL=qwen2.5-coder:14b'; $t=$t -replace 'OLLAMA_NUM_CTX=.*','OLLAMA_NUM_CTX=16384'; Set-Content $p $t -Encoding UTF8"
echo Aktiv: schneller 14B Coding-Modus.
pause
