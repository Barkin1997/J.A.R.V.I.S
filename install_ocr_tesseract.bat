@echo off
title Orange Jarvis - OCR Tesseract Installation
color 0E

where winget >nul 2>&1
if errorlevel 1 (
    echo Winget fehlt. Tesseract bitte manuell installieren.
    pause
    exit /b 1
)

winget install -e --id UB-Mannheim.TesseractOCR

echo.
echo OCR installiert. Starte Windows/Jarvis neu, falls tesseract nicht sofort gefunden wird.
pause
