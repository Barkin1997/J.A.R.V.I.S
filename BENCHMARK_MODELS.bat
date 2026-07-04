@echo off
cd /d "%~dp0"
title Orange Jarvis - Modell Benchmark
call .venv\Scripts\activate
python benchmark_models.py
pause
