@echo off
cd /d "%~dp0"
if not exist .env copy .env.example .env >nul
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
 "$p='.env'; $t=Get-Content $p -Raw; $t=$t -replace 'OLLAMA_TEXT_MODEL=.*','OLLAMA_TEXT_MODEL=qwen3-coder:480b'; $t=$t -replace 'OLLAMA_CODE_MODEL=.*','OLLAMA_CODE_MODEL=qwen3-coder:480b'; $t=$t -replace 'OLLAMA_AGENT_CODE_MODEL=.*','OLLAMA_AGENT_CODE_MODEL=qwen3-coder:480b'; $t=$t -replace 'OLLAMA_STRONG_CODE_MODEL=.*','OLLAMA_STRONG_CODE_MODEL=qwen3-coder:480b'; $t=$t -replace 'OLLAMA_BEAST_CODE_MODEL=.*','OLLAMA_BEAST_CODE_MODEL=qwen3-coder:480b'; $t=$t -replace 'MULTI_AGENT_MODEL=.*','MULTI_AGENT_MODEL=qwen3-coder:480b'; $t=$t -replace 'PLANNER_MODEL=.*','PLANNER_MODEL=qwen3-coder:480b'; $t=$t -replace 'TESTER_MODEL=.*','TESTER_MODEL=qwen3-coder:480b'; $t=$t -replace 'FIXER_MODEL=.*','FIXER_MODEL=qwen3-coder:480b'; $t=$t -replace 'SECURITY_MODEL=.*','SECURITY_MODEL=qwen3-coder:480b'; $t=$t -replace 'INTERNET_RESEARCH_MODEL=.*','INTERNET_RESEARCH_MODEL=qwen3-coder:480b'; $t=$t -replace 'OLLAMA_EMBED_MODEL=.*','OLLAMA_EMBED_MODEL=nomic-embed-text-v2-moe'; $t=$t -replace 'OLLAMA_NUM_CTX=.*','OLLAMA_NUM_CTX=65536'; $t=$t -replace 'OLLAMA_TEMPERATURE=.*','OLLAMA_TEMPERATURE=0.04'; Set-Content $p $t -Encoding UTF8"
echo ULTRA STRONGEST aktiv: 480B fuer Text, Code, Agenten und Internet-Recherche.
pause
