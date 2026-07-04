# GitHub Release fuer Modelle

Der Code liegt normal im GitHub-Repository. Die grossen Modelle gehoeren nicht
in den normalen Git-Branch, sondern in GitHub Releases.

Warum:

- GitHub blockt normale Repository-Dateien ueber 100 MiB.
- GitHub empfiehlt Repositories klein zu halten.
- Release-Assets duerfen bis zu 2 GiB pro Datei haben, bis zu 1000 Assets pro
  Release und ohne Gesamtlimit.

## Upload vorbereiten

Du brauchst einen GitHub Token mit Schreibrecht fuer Releases/Contents.

PowerShell:

```powershell
setx GITHUB_TOKEN "DEIN_TOKEN"
```

Danach neues Terminal oeffnen.

## Full-Paket hochladen

```powershell
cd "E:\J.A.R.V.I.S\orange_jarvis_ultra_last_procontrol_easyname\release\Jarvis_PUBLIC_GITHUB_20260704_090920"

python tools\github_release_full_upload.py ^
  --full "E:\J.A.R.V.I.S\orange_jarvis_ultra_last_procontrol_easyname\release\Jarvis_FULL_WITH_MODELS_20260703_232834" ^
  --owner Barkin1997 ^
  --repo J.A.R.V.I.S ^
  --tag jarvis-full-models-20260704 ^
  --chunk-mib 1800 ^
  --draft
```

Das Skript erstellt eine Draft-Release und laedt das Full-Paket als viele
`.tar.part` Dateien hoch. Es braucht nur Speicher fuer einen Teil auf einmal.

Wenn alles hochgeladen ist, auf GitHub die Release pruefen und veroeffentlichen.

## Nutzer installieren Full-Paket

1. Alle `.tar.part` Dateien aus der Release herunterladen.
2. In einen Ordner legen.
3. Restore ausfuehren:

```powershell
python tools\restore_full_release_package.py ^
  --parts "C:\Downloads\jarvis_parts" ^
  --out "C:\Jarvis_FULL_WITH_MODELS"
```

Danach kann der Nutzer die Ordner aus `C:\Jarvis_FULL_WITH_MODELS` in seinen
Jarvis-Ordner kopieren.
