# Open Source Upload Guide

## Was auf GitHub soll

- Code-Dateien
- `README.md`
- `LICENSE`
- `requirements.txt`
- Workflows und Startskripte
- kleine UI-Assets

## Was nicht direkt ins GitHub-Repo soll

- `.env`
- private Chats und Datenbanken
- Logs
- `Jarvis_Projects`
- `external`
- lokale KI-Modelle
- generierte Bilder/Videos

## GitHub-Paket bauen

```powershell
.\PUBLIC_GITHUB_PAKET_ERSTELLEN.bat
```

Die fertige ZIP liegt danach in `release`.

## Full-Download mit Modellen

```powershell
.\FULL_DOWNLOAD_MIT_MODELLEN_ERSTELLEN.bat
```

Dieses Paket ist fuer grosse Downloads gedacht, nicht fuer normales GitHub-Git.
Am besten auf Drive, Mega, Hugging Face, GitHub Releases oder einen eigenen
Download-Server hochladen.

## GitHub hochladen

```powershell
git status
git add .
git commit -m "Open source Jarvis release"
git branch -M main
git remote add origin https://github.com/DEIN_NAME/DEIN_REPO.git
git push -u origin main
```

Wenn `remote origin already exists` kommt:

```powershell
git remote set-url origin https://github.com/DEIN_NAME/DEIN_REPO.git
git push -u origin main
```
