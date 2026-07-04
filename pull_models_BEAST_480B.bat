@echo off
cd /d "%~dp0"
title Orange Jarvis BEAST - 480B Modelle
color 0C

echo =====================================================
echo BEAST MODE MODELLE
echo =====================================================
echo.
echo Das laedt sehr grosse Modelle.
echo qwen3-coder:480b ist ca. 290 GB.
echo Nur starten, wenn genug Speicher/RAM vorhanden ist.
echo.

start "Ollama Server" /min cmd /c "ollama serve"
timeout /t 5 /nobreak >nul

echo [1/5] Textmodell qwen3-next:80b
ollama pull qwen3-next:80b

echo [2/5] Coding BEAST qwen3-coder:480b
ollama pull qwen3-coder:480b

echo [3/5] Coding Agent qwen3-coder-next
ollama pull qwen3-coder-next

echo [4/5] Fallback qwen3-coder:30b
ollama pull qwen3-coder:30b

echo [5/6] DeepSeek Coder V2 16B
ollama pull deepseek-coder-v2:16b

echo [6/6] Embedding-Modell
ollama pull nomic-embed-text

echo.
echo BEAST Modelle geladen.
pause


echo Embedding V2 MOE
ollama pull nomic-embed-text-v2-moe
