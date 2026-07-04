# Orange Jarvis Ultra

Lokaler KI-Assistent fuer Windows mit Sprache, 3D-Hologramm, Coding-Modus,
Projekt-Gedaechtnis, PC-Steuerung, KI-Bild, KI-Video, Dashboards,
Zuverlaessigkeits-Check und Auto-Reparatur.

> Public Hinweis: Dieses Repository enthaelt den Code und die Workflows. Grosse
> KI-Modelle, lokale Caches, private Chats, `.env`, Logs und generierte Projekte
> gehoeren nicht in das GitHub-Repo. Fuer ein Komplettpaket mit Modellen gibt es
> das Full-Download-Skript.

## Funktionen

- Lokaler Chatbot mit Ollama-Modellen
- Spracheingabe und Sprachausgabe
- 3D-WebGL-Jarvis mit Live-Status
- Coding-Modus mit Plan, Diff, Test, Backup und Reparaturversuch
- Projekt-Gedaechtnis pro Ordner
- Dashboard fuer Status, Coding und KI-Video
- KI-Bild-Integration mit Presets und Upscale-Zielen
- KI-Video-Integration mit ComfyUI/Wan-Workflows, VRAM-Schutz und Fortschritt
- Service-Waechter fuer Ollama, ComfyUI, Bildgenerator und Aider
- Auto-Reparatur fuer Locks, kaputte JSON-Dateien, Statusdaten und Syntaxchecks
- PC- und Browser-Automation fuer lokale Aufgaben

## Schnellstart

1. Repository klonen oder ZIP entpacken.
2. `.env.example` zu `.env` kopieren und lokale Pfade/Modelle eintragen.
3. Python-Abhaengigkeiten installieren:

```powershell
pip install -r requirements.txt
```

4. Ollama installieren und ein Modell laden, zum Beispiel:

```powershell
ollama pull qwen3-coder-next:latest
```

5. Starten:

```powershell
.\System einschalten.bat
```

## Wichtige Befehle in Jarvis

- `Jarvis, Status`
- `Jarvis, pruefe dich`
- `Jarvis, auto reparatur`
- `Jarvis, Coding Dashboard`
- `Jarvis, Video Dashboard`
- `Jarvis, erstelle KI Bild ...`
- `Jarvis, erstelle KI Video ...`

## Full-Download mit Modellen

Wenn du wirklich alles inklusive lokaler Modelle weitergeben willst:

```powershell
.\FULL_DOWNLOAD_MIT_MODELLEN_ERSTELLEN.bat
```

Das erstellt einen Release-Ordner mit Code, Workflows, `external`, `models` und
lokalen Modell-Caches, aber ohne private `.env`, Chats, Logs, Browserprofile und
persoenliche Arbeitsprojekte.

Mehr dazu steht in `MODEL_DOWNLOAD_INFO.md`. Das GitHub-Repo bleibt klein und
sauber; das grosse Modellpaket wird separat als Download verlinkt.

Fuer GitHub selbst besser:

```powershell
.\PUBLIC_GITHUB_PAKET_ERSTELLEN.bat
```

## Nicht ins oeffentliche Repo hochladen

- `.env` und `.env.backup_*`
- `data/chat_history.jsonl`
- `data/*.sqlite`
- `logs/`
- `Jarvis_Projects/`
- `external/`
- grosse Modell-Dateien wie `.safetensors`, `.gguf`, `.ckpt`, `.pt`

## Sicherheit

Nutze Security- und Coding-Funktionen nur fuer eigene Projekte oder Systeme, fuer
die du ausdruecklich berechtigt bist. Jarvis soll Fehler finden, testen und
reparieren, aber jede oeffentliche Version sollte vor dem Upload geprueft werden.

## Lizenz

Dieses Projekt ist unter der MIT-Lizenz veroeffentlicht. Andere duerfen den Code
verwenden, kopieren, veraendern und weitergeben, solange der Copyright- und
Lizenzhinweis erhalten bleibt.
