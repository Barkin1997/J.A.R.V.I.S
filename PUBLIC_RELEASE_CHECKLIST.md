# Public Release Checklist

## 1. Code-Paket fuer GitHub erstellen

```powershell
.\PUBLIC_GITHUB_PAKET_ERSTELLEN.bat
```

Das Paket liegt danach unter `release\Jarvis_PUBLIC_GITHUB_*`.

## 2. Full-Paket mit Modellen erstellen

```powershell
.\FULL_DOWNLOAD_MIT_MODELLEN_ERSTELLEN.bat
```

Das Paket liegt danach unter `release\Jarvis_FULL_WITH_MODELS_*`.

Wenn du daraus eine ZIP machen willst und 7-Zip installiert ist:

```powershell
powershell -ExecutionPolicy Bypass -File .\MAKE_PUBLIC_RELEASE.ps1 -Mode Full -Zip
```

## 3. Vor GitHub pruefen

Nicht hochladen:

- `.env`
- `.env.backup_*`
- private Chats
- SQLite-Gedaechtnisse
- Logs
- Browserprofile
- generierte Projekte
- riesige Modell-Dateien im normalen Git-Verlauf

## 4. Wenn Git schon private/grosse Dateien vorgemerkt hat

Dieses Skript entfernt sie nur aus dem Git-Index, nicht von der Festplatte:

```powershell
.\PUBLIC_GIT_INDEX_AUFRAEUMEN.ps1
```

Danach:

```powershell
git status
git add .
git commit -m "Prepare public Jarvis release"
```

## 5. Empfehlung fuer oeffentlichen Download

- GitHub-Repo: Code, Workflows, Dokumentation
- Separater Full-Download: Modelle und grosse Runtime-Ordner
- README-Link vom GitHub-Repo zum Full-Download

## 6. Open Source

Das Projekt nutzt `LICENSE` mit MIT-Lizenz. Damit ist der Code oeffentlich
nutzbar, veraenderbar und teilbar. Grosse Modelle koennen eigene Lizenzen haben;
beim Full-Download muss jede Modell-Lizenz separat beachtet werden.
