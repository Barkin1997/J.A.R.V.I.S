@echo off
cd /d "%~dp0"
title Orange Jarvis - Ollama

set "OLLAMA_MODELS=E:\.ollama\models"
set "OLLAMA_LOAD_TIMEOUT=30m"
set "OLLAMA_KEEP_ALIVE=30m"
set "OLLAMA_CONTEXT_LENGTH=32768"
set "OLLAMA_NUM_PARALLEL=1"
set "OLLAMA_MAX_LOADED_MODELS=1"
set "OLLAMA_HOST=127.0.0.1:11434"

echo Ollama startet fuer Jarvis...
echo Modelle: %OLLAMA_MODELS%
echo Lade-Timeout: %OLLAMA_LOAD_TIMEOUT%
echo Keep-Alive: %OLLAMA_KEEP_ALIVE%
echo Kontext: %OLLAMA_CONTEXT_LENGTH%
echo.

ollama serve
