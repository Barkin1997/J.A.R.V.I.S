@echo off
title JARVIS CODEX AIDER - Kostenlos Lokal
color 0A

echo ===============================================
echo   JARVIS CODEX AIDER - Kostenloser Codex-Modus
echo ===============================================
echo.
echo Ordner:
echo E:\J.A.R.V.I.S\orange_jarvis_ultra_last_procontrol_easyname
echo.
echo Modell:
echo qwen3-coder-next:latest
echo.

cd /d "E:\J.A.R.V.I.S\orange_jarvis_ultra_last_procontrol_easyname"

set OLLAMA_API_BASE=http://127.0.0.1:11434

echo Pruefe Ollama...
set OLLAMA_READY=0
for /L %%I in (1,1,30) do (
    ollama list >nul 2>&1
    if not errorlevel 1 (
        set OLLAMA_READY=1
        goto :ollama_ready
    )
    echo Warte auf Ollama... %%I/30
    timeout /t 2 /nobreak >nul
)

:ollama_ready
if not "%OLLAMA_READY%"=="1" (
    echo.
    echo FEHLER: Ollama antwortet nicht.
    echo Starte zuerst Ollama oder oeffne die Ollama-App.
    echo.
    pause
    exit /b
)

echo.
echo Starte Aider im Jarvis-Ordner...
echo.
echo Gute Start-Befehle in Aider:
echo - Pruefe Jarvis und sag mir nur Verbesserungen. Nichts aendern.
echo - Lade nur voice.py. Erklaere zuerst, was du aendern wuerdest. Noch nichts aendern.
echo - Lade nur app.py. Mach vorher Backup und aendere nur diese Datei.
echo.
echo WICHTIG: Nicht A druecken, wenn Aider fragt. Erstmal N oder nur einzelne Datei laden.
echo.

aider --config .aider.conf.yml

pause
