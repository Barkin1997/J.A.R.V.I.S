# Model Download Info

This GitHub repository contains the Jarvis source code, workflows, dashboards,
start scripts, and documentation.

Large local AI models are not stored directly in the Git repository because
GitHub blocks very large regular Git files and large model folders make cloning
slow and unreliable.

## Full package with models

The local full package is here:

```text
E:\J.A.R.V.I.S\orange_jarvis_ultra_last_procontrol_easyname\release\Jarvis_FULL_WITH_MODELS_20260703_232834
```

Upload this full package separately, for example as:

- GitHub Release assets
- Hugging Face dataset/model repo
- Google Drive
- MEGA
- your own download server

Then paste the public download link here:

```text
FULL_MODEL_DOWNLOAD_URL=PASTE_LINK_HERE
```

For GitHub Releases, see `GITHUB_MODELS_RELEASE.md`. It contains the prepared
upload and restore scripts for splitting the full package into release assets
under GitHub's file-size limit.

## Install idea for users

1. Download the GitHub source code.
2. Download the separate full model package.
3. Copy/extract the model folders into the Jarvis folder.
4. Copy `.env.example` to `.env`.
5. Start `System einschalten.bat`.

## Not included in the public Git repository

- `.env`
- private chats
- memory databases
- logs
- generated projects
- local model caches
- huge `.safetensors`, `.gguf`, `.ckpt`, `.pt`, `.pth` model files
