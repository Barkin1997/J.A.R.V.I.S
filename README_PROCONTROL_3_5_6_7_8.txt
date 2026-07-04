ORANGE JARVIS ULTRA LAST PROCONTROL

Eingebaut nach deiner Auswahl:

3. Crash-Watcher
5. Windows-App-Agent V2
6. OCR-Screen-Reader
7. Projekt-Rollback
8. Autopilot Loop bis fertig

Hauptstart:

START_JARVIS_ALLES_EIN_KLICK.bat

Dieser Start nutzt jetzt automatisch den Crash-Watcher.
Wenn Jarvis abstürzt, wird er neu gestartet und der Crash wird in logs gespeichert.

Alternativer direkter Watcher:

START_JARVIS_CRASH_WATCHER.bat

OCR installieren:

install_ocr_tesseract.bat

Der Auto-Download versucht Tesseract OCR automatisch zu installieren.

Neue Befehle:

CRASH:
Jarvis, status komplett

WINDOWS-APP-AGENT V2:
Jarvis, fenster liste
Jarvis, fenster aktivieren Editor
Jarvis, programm öffnen notepad
Jarvis, schreibe in app Hallo Welt
Jarvis, hotkey ctrl s
Jarvis, klick text Speichern

OCR:
Jarvis, ocr bildschirm
Jarvis, lies bildschirm ocr

PROJEKT-ROLLBACK:
Jarvis, projekt backup C:\Pfad\Projekt | vor großer Änderung
Jarvis, projekt rollback C:\Pfad\Projekt
Jarvis, git rollback C:\Pfad\Projekt

AUTOPILOT LOOP:
Jarvis, autopilot loop baue eine komplette Webseite mit Login, Adminbereich und Datenbank
Jarvis, autopilot bis fertig erstelle ein C++ Banking System mit Tests und Datei-Speicherung
Jarvis, baue bis fertig ein Python GUI Tool zum Dateien sortieren

Hinweis:

Die OCR-Funktion nutzt Tesseract, wenn installiert.
Wenn Tesseract fehlt, versucht Jarvis den Screenshot mit dem lokalen Vision-Modell zu lesen.

Projekt-Rollback erstellt ZIP-Backups in:

project_backups

Crash-Logs liegen in:

logs
