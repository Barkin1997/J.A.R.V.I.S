@echo off
cd /d "%~dp0"
if not exist .env copy .env.example .env >nul
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
 "$p='.env'; $t=Get-Content $p -Raw; $t=$t -replace 'OLLAMA_TEXT_MODEL=.*','OLLAMA_TEXT_MODEL=qwen3-next:80b'; $t=$t -replace 'OLLAMA_CODE_MODEL=.*','OLLAMA_CODE_MODEL=qwen3-coder:480b'; $t=$t -replace 'OLLAMA_MAX_CODE_MODEL=.*','OLLAMA_MAX_CODE_MODEL=qwen3-coder:480b'; $t=$t -replace 'OLLAMA_NUM_CTX=.*','OLLAMA_NUM_CTX=65536'; $t=$t -replace 'OLLAMA_TEMPERATURE=.*','OLLAMA_TEMPERATURE=0.08'; Set-Content $p $t -Encoding UTF8"
echo BEAST aktiv:
echo Text: qwen3-next:80b
echo Code: qwen3-coder:480b
echo Context: 65536
pause
