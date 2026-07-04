@echo off
title Orange Jarvis Ultimate - Modelle RTX5080
echo Ollama muss installiert und gestartet sein.
echo Modelle werden geladen. Das kann lange dauern.
echo.

ollama pull qwen2.5:14b
ollama pull qwen2.5-coder:14b
ollama pull qwen2.5-coder:32b
ollama pull llava:13b

echo.
echo Modelle fertig.
echo Standard bleibt 14B fuer Geschwindigkeit.
echo 32B kann mit switch_max_quality_32b.bat aktiviert werden.
pause
