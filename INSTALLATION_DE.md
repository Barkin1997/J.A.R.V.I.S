# J.A.R.V.I.S installieren

Diese Anleitung ist fuer Leute, die J.A.R.V.I.S von GitHub herunterladen und
starten wollen.

## 1. Code herunterladen

1. GitHub Repository oeffnen:
   `https://github.com/Barkin1997/J.A.R.V.I.S`
2. Auf `Code` klicken.
3. `Download ZIP` waehlen.
4. ZIP entpacken, zum Beispiel nach:

```text
C:\JARVIS
```

Alternativ mit Git:

```powershell
git clone https://github.com/Barkin1997/J.A.R.V.I.S.git C:\JARVIS
```

## 2. Python-Abhaengigkeiten installieren

PowerShell im Jarvis-Ordner oeffnen:

```powershell
cd C:\JARVIS
python -m pip install -r requirements.txt
```

## 3. Einstellungen vorbereiten

```powershell
copy .env.example .env
```

Dann `.env` oeffnen und lokale Pfade/Modelle anpassen, falls noetig.

## 4. Ollama installieren

Ollama installieren und ein Modell laden:

```powershell
ollama pull qwen3-coder-next:latest
```

## 5. Modelle herunterladen

Die grossen KI-Modelle sind nicht im normalen GitHub-Code-ZIP. Sie werden als
GitHub Release heruntergeladen.

Einfachste Variante:

```powershell
cd C:\JARVIS
.\INSTALL_MODELS_FROM_GITHUB.bat
```

Das Skript laedt alle Modellteile automatisch von GitHub, setzt sie zusammen und
kopiert die Modellordner an die richtige Stelle.

Manuelle Variante:

```powershell
cd C:\JARVIS
python tools\download_full_release_assets.py --out C:\JARVIS_MODEL_PARTS
```

Das laedt alle `.tar.part` Dateien in:

```text
C:\JARVIS_MODEL_PARTS
```

## 6. Full-Paket wiederherstellen

Nur noetig, wenn du die manuelle Variante nutzt:

```powershell
cd C:\JARVIS
python tools\restore_full_release_package.py --parts C:\JARVIS_MODEL_PARTS --out C:\JARVIS_FULL_WITH_MODELS
```

Danach liegen die Modell-Ordner in:

```text
C:\JARVIS_FULL_WITH_MODELS
```

Kopiere daraus die Ordner in deinen Jarvis-Ordner, vor allem:

- `external`
- `models`
- `data\huggingface_cache`

## 7. Starten

```powershell
cd C:\JARVIS
.\System einschalten.bat
```

## Wichtig

- Der Code ist Open Source unter MIT-Lizenz.
- Die grossen Modelle koennen eigene Lizenzen haben.
- `.env`, private Chats, Logs und eigene Projekte gehoeren nicht ins GitHub-Repo.
- Wenn ein Dienst fehlt, in Jarvis sagen: `Jarvis, pruefe dich`.
