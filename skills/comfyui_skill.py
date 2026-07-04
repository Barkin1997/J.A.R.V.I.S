import json
import subprocess
import time
import webbrowser
from pathlib import Path

import requests

from config import COMFYUI_URL, COMFYUI_DIR, PROJECT_DIR


class ComfyUISkill:
    def status(self) -> str:
        try:
            r = requests.get(f"{COMFYUI_URL}/system_stats", timeout=5)
            if r.ok:
                return f"ComfyUI erreichbar: {COMFYUI_URL}"
            return f"ComfyUI antwortet mit HTTP {r.status_code}"
        except Exception:
            return "ComfyUI nicht erreichbar. Starte start_comfyui.bat."

    def open(self) -> str:
        webbrowser.open(COMFYUI_URL, new=2)
        return f"ComfyUI geöffnet: {COMFYUI_URL}"

    def start_hint(self) -> str:
        return (
            "ComfyUI Start:\n"
            "install_comfyui.bat\n"
            "start_comfyui.bat\n\n"
            "Modelle liegen in:\n"
            "external\\ComfyUI\\models\\checkpoints"
        )
