JARVIS LOKALER CODEX-PRO-MODUS

Das ist die bessere Version mit mehr Tool-Steuerung und mehr Kontext.

Modell:
qwen3-coder-next:latest

Wichtig:
- 3D wird NICHT geändert.
- Diese ZIP enthält KEINEN jarvis_3d_webgl Ordner.
- Deine Oberfläche bleibt gleich.
- Nur Codex/Backend-Funktionen werden erweitert.

Was neu besser ist:
- Projektindex wie Codex
- Dateisuche im ganzen Projekt
- Dateien gezielt lesen
- Tool-Schleife: Modell kann Tools anfordern
- sichere Commands: py_compile, ollama list, ollama test
- Dateiänderungen mit Backup
- 3D-Schutz: jarvis_3d_webgl bleibt blockiert, außer du sagst ausdrücklich 3D/UI/Design
- mehr Kontext: relevante Dateien + Suchtreffer + Projektindex

Neue Befehle:
- Jarvis, codex status
- Jarvis, codex index
- Jarvis, codex suche OLLAMA_MODEL
- Jarvis, codex lese app.py
- Jarvis, codex prüfe dich
- Jarvis, codex finde warum du nicht antwortest
- Jarvis, codex repariere app.py
- Jarvis, codex ändere brain.py: ...
- Jarvis, codex test

Installation:
1. Jarvis komplett schließen.
2. ZIP entpacken.
3. Inhalt in deinen Jarvis-Hauptordner kopieren.
4. Ersetzen: Ja.
5. Einmal starten:
   SET_LOCAL_CODEX_QWEN_NEXT.bat
6. Danach:
   System einschalten

Backups:
codex_backups/

Logs:
data\codex_logs/
