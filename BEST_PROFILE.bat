@echo off
cd /d "%~dp0"
if not exist .env copy .env.example .env >nul
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
 "$p='.env'; $t=Get-Content $p -Raw; $t=$t -replace 'OLLAMA_TEXT_MODEL=.*','OLLAMA_TEXT_MODEL=qwen3-next:80b'; $t=$t -replace 'OLLAMA_CODE_MODEL=.*','OLLAMA_CODE_MODEL=qwen3-coder:480b'; $t=$t -replace 'OLLAMA_MAX_CODE_MODEL=.*','OLLAMA_MAX_CODE_MODEL=qwen3-coder:480b'; $t=$t -replace 'OLLAMA_AGENT_CODE_MODEL=.*','OLLAMA_AGENT_CODE_MODEL=qwen3-coder-next'; $t=$t -replace 'OLLAMA_STRONG_CODE_MODEL=.*','OLLAMA_STRONG_CODE_MODEL=qwen3-coder:30b'; $t=$t -replace 'OLLAMA_BEAST_CODE_MODEL=.*','OLLAMA_BEAST_CODE_MODEL=qwen3-coder:480b'; $t=$t -replace 'OLLAMA_NUM_CTX=.*','OLLAMA_NUM_CTX=65536'; $t=$t -replace 'AUTO_BUILD_TEST=.*','AUTO_BUILD_TEST=1'; $t=$t -replace 'AUTO_FIX_ROUNDS=.*','AUTO_FIX_ROUNDS=2'; $t=$t -replace 'AUTO_GIT_SNAPSHOT=.*','AUTO_GIT_SNAPSHOT=1'; Set-Content $p $t -Encoding UTF8"
echo Best Profile aktiviert.
pause
