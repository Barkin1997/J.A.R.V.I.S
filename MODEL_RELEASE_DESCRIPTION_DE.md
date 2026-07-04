# Release-Beschreibung fuer GitHub

Titel:

```text
Jarvis Full Package With Models
```

Beschreibung:

```text
Das ist das Full-Paket fuer J.A.R.V.I.S mit lokalen KI-Modellen.

Wichtig:
- Der normale Code liegt im Repository.
- Diese Release enthaelt die grossen Modell-Dateien als gesplittete .tar.part Dateien.
- Lade alle .tar.part Dateien herunter.
- Danach stelle das Paket mit restore_full_release_package.py wieder her.

Installation:

1. Code herunterladen:
   https://github.com/Barkin1997/J.A.R.V.I.S

2. Alle Dateien dieser Release herunterladen.

3. In einen Ordner legen, z.B.:
   C:\JARVIS_MODEL_PARTS

4. Wiederherstellen:
   python tools\restore_full_release_package.py --parts C:\JARVIS_MODEL_PARTS --out C:\JARVIS_FULL_WITH_MODELS

5. Aus C:\JARVIS_FULL_WITH_MODELS diese Ordner in deinen Jarvis-Ordner kopieren:
   - external
   - models
   - data\huggingface_cache

6. Jarvis starten:
   System einschalten.bat

Hinweis:
Der Code ist MIT-lizenziert. Externe Modelle koennen eigene Lizenzen haben.
```
