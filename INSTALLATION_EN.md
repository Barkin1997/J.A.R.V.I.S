# Install J.A.R.V.I.S

This guide is for users who want to download and run J.A.R.V.I.S from GitHub.

## 1. Download the code

1. Open the GitHub repository:
   `https://github.com/Barkin1997/J.A.R.V.I.S`
2. Click `Code`.
3. Choose `Download ZIP`.
4. Extract it, for example to:

```text
C:\JARVIS
```

Or clone with Git:

```powershell
git clone https://github.com/Barkin1997/J.A.R.V.I.S.git C:\JARVIS
```

## 2. Install Python dependencies

Open PowerShell in the Jarvis folder:

```powershell
cd C:\JARVIS
python -m pip install -r requirements.txt
```

## 3. Prepare settings

```powershell
copy .env.example .env
```

Open `.env` and adjust local paths/models if needed.

## 4. Install Ollama

Install Ollama and pull a model:

```powershell
ollama pull qwen3-coder-next:latest
```

## 5. Download models

The large AI models are not inside the normal GitHub source ZIP. They are
distributed as GitHub Release assets.

When the release `jarvis-full-models-20260704` is visible, download all model
parts like this:

```powershell
cd C:\JARVIS
python tools\download_full_release_assets.py --out C:\JARVIS_MODEL_PARTS
```

## 6. Restore the full package

```powershell
cd C:\JARVIS
python tools\restore_full_release_package.py --parts C:\JARVIS_MODEL_PARTS --out C:\JARVIS_FULL_WITH_MODELS
```

Then copy these folders from `C:\JARVIS_FULL_WITH_MODELS` into your Jarvis
folder:

- `external`
- `models`
- `data\huggingface_cache`

## 7. Start Jarvis

```powershell
cd C:\JARVIS
.\System einschalten.bat
```

## Notes

- The code is open source under the MIT license.
- Large AI models may have their own licenses.
- `.env`, private chats, logs, and personal projects are not included in GitHub.
- If something is missing, ask Jarvis: `Jarvis, pruefe dich`.
