import json
import os
import subprocess
import time
import urllib.request
from pathlib import Path

from config import BASE_DIR, OLLAMA_URL, COMFYUI_URL, IMAGE_API_URL, STATUS_CHECK_TIMEOUT


class ServiceWatcher:
    def __init__(self):
        self.root = Path(BASE_DIR).resolve()
        self.data_file = self.root / "data" / "service_status.json"
        self.data_file.parent.mkdir(parents=True, exist_ok=True)

    def check(self) -> str:
        status = self.snapshot()
        self._write_status(status)
        lines = ["SERVICE-WAECHTER"]
        for name, info in status["services"].items():
            state = "OK" if info.get("ok") else "AUS"
            lines.append(f"- {name}: {state} - {info.get('detail', '')}")
        return "\n".join(lines)

    def ensure_all(self) -> str:
        status = self.snapshot()
        started = []
        for name, info in status["services"].items():
            if info.get("ok"):
                continue
            bat = info.get("start_bat")
            if bat and self._start_bat(bat):
                started.append(name)
        time.sleep(2)
        new_status = self.snapshot()
        self._write_status(new_status)
        lines = ["SERVICE-WAECHTER START"]
        lines.append("Gestartet: " + (", ".join(started) if started else "nichts neu gestartet"))
        for name, info in new_status["services"].items():
            state = "OK" if info.get("ok") else "AUS"
            lines.append(f"- {name}: {state} - {info.get('detail', '')}")
        return "\n".join(lines)

    def snapshot(self) -> dict:
        return {
            "updated_at": time.time(),
            "services": {
                "Ollama": self._service(
                    OLLAMA_URL.replace("/api", "") + "/api/tags",
                    "start_ollama.bat",
                    "Lokale Modelle/Coding",
                ),
                "ComfyUI": self._service(
                    COMFYUI_URL + "/system_stats",
                    "start_comfyui.bat",
                    "KI-Video/Workflows",
                ),
                "Bildgenerator": self._service(
                    IMAGE_API_URL + "/sdapi/v1/sd-models",
                    "start_image_generator.bat",
                    "KI-Bilder/Stable Diffusion",
                ),
                "Coding": self._coding_service(),
            },
        }

    def _service(self, url: str, bat_name: str, label: str) -> dict:
        try:
            urllib.request.urlopen(url, timeout=STATUS_CHECK_TIMEOUT)
            return {"ok": True, "detail": f"{label} erreichbar", "url": url, "start_bat": bat_name}
        except Exception as e:
            return {"ok": False, "detail": f"{label} nicht erreichbar: {e}", "url": url, "start_bat": bat_name}

    def _coding_service(self) -> dict:
        lock = self.root / "data" / "aider_job.lock"
        conf = self.root / ".aider.conf.yml"
        if lock.exists():
            age = int(time.time() - lock.stat().st_mtime)
            return {"ok": True, "detail": f"Coding laeuft seit {age}s", "start_bat": ""}
        if conf.exists():
            return {"ok": True, "detail": "Aider/Codex bereit", "start_bat": ""}
        return {"ok": False, "detail": ".aider.conf.yml fehlt", "start_bat": ""}

    def _start_bat(self, bat_name: str) -> bool:
        bat = self.root / bat_name
        if not bat.exists():
            return False
        try:
            subprocess.Popen(
                ["cmd.exe", "/c", "start", "/min", "", str(bat)],
                cwd=str(self.root),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            return True
        except Exception:
            return False

    def _write_status(self, data: dict) -> None:
        try:
            self.data_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass
