import os
import json
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from config import BASE_DIR, OLLAMA_URL, COMFYUI_URL, IMAGE_API_URL, STATUS_CHECK_TIMEOUT

try:
    from skills.model_router import ModelRouter
    from skills.service_watcher import ServiceWatcher
    from skills.reliability_guard import ReliabilityGuard
    from skills.auto_repair import AutoRepair
except Exception:
    ModelRouter = None
    ServiceWatcher = None
    ReliabilityGuard = None
    AutoRepair = None


class StatusCenter:
    def check(self) -> str:
        ollama_api = self._http(OLLAMA_URL.replace("/api", "") + "/api/tags")
        ollama_models = self._ollama_models()
        coding_status = self._coding_status()
        image_status = self._image_status()
        comfy_status = self._http(COMFYUI_URL + "/system_stats")
        comfy_queue = self._comfy_queue_status()
        video_status = self._video_status(comfy_queue=comfy_queue)
        service_status = self._service_watcher_status()
        coding_dashboard_status = self._coding_dashboard_status()
        model_router_status = self._model_router_status()
        video_progress_status = self._video_progress_status()
        reliability_status = self._reliability_status()
        auto_repair_status = self._auto_repair_status()
        quick = [
            ("Ollama", "OK" if ollama_api == "OK" and ollama_models.startswith("OK") else "PROBLEM", self._status_detail(ollama_models)),
            ("Coding", "BEREIT" if coding_status.startswith("OK") else "PRUEFEN", self._status_detail(coding_status)),
            ("Zuverlaessigkeit", "OK" if reliability_status.startswith("OK") else "PRUEFEN", self._status_detail(reliability_status)),
            ("Auto-Reparatur", "OK" if auto_repair_status.startswith("OK") else "PRUEFEN", self._status_detail(auto_repair_status)),
            ("Dienste", "OK" if service_status.startswith("OK") else "PRUEFEN", self._status_detail(service_status)),
            ("Coding-Dashboard", "OK" if coding_dashboard_status.startswith("OK") else "PRUEFEN", self._status_detail(coding_dashboard_status)),
            ("ComfyUI", "OK" if comfy_status == "OK" else "AUS", comfy_queue if comfy_status == "OK" else "start_comfyui.bat starten"),
            ("Bildgenerator", "OK" if image_status == "OK" else "AUS", "bereit" if image_status == "OK" else "start_image_generator.bat starten"),
            ("KI-Video", "BEREIT" if "ReadyDatei=OK" in video_status else "PRUEFEN", video_status),
        ]
        rows = [
            ("Internet", self._internet()),
            ("Ollama API", ollama_api),
            ("Ollama Modelle", ollama_models),
            ("Modell-Router", model_router_status),
            ("Zuverlaessigkeits-Guard", reliability_status),
            ("Auto-Reparatur", auto_repair_status),
            ("Coding-Modus", coding_status),
            ("Coding-Dashboard", coding_dashboard_status),
            ("Service-Waechter", service_status),
            ("PC-Steuerung", self._pc_control_status()),
            ("GPU/VRAM", self._gpu_status()),
            ("Bildgenerator", image_status),
            ("ComfyUI", comfy_status),
            ("ComfyUI Queue", comfy_queue),
            ("KI-Video Ultra", video_status),
            ("KI-Video Fortschritt", video_progress_status),
            ("Speicher auf E", self._storage_status()),
            ("Aktive Jobs", self._active_jobs_status()),
            ("Letzter Fehler", self._last_error_status()),
            ("Chat/Voice", self._chat_voice_status()),
            ("ffmpeg", self._which_version("ffmpeg", "-version")),
            ("Python", sys.version.split()[0]),
            ("Git", self._which_version("git", "--version")),
            ("Node", self._which_version("node", "--version")),
            ("NPM", self._which_version("npm", "--version")),
            ("CMake", self._which_version("cmake", "--version")),
            ("Java", self._which_version("javac", "-version")),
            ("Rust", self._which_version("cargo", "--version")),
            ("Go", self._which_version("go", "version")),
        ]
        commands = [
            "Jarvis, status komplett",
            "Jarvis, was kannst du alles",
            "Jarvis, aendere in diesem Ordner ...",
            "Jarvis, oeffne app notepad",
            "Jarvis, klick text Speichern",
            "Jarvis, hotkey ctrl+s",
            "Jarvis, mach KI Video ...",
            "Jarvis, KI Video Ladebalken",
            "Jarvis, Video Dashboard",
            "Jarvis, erstelle KI Bild ...",
            "Jarvis, Dienste pruefen",
            "Jarvis, Coding Dashboard",
            "Jarvis, Modell Router",
            "Jarvis, Zuverlaessigkeit pruefen",
            "Jarvis, Auto Reparatur",
            "Jarvis, aufraeumen",
        ]
        return (
            "JARVIS KOMPLETT-CHECK\n"
            + "\nSTATUS-AMPEL:\n"
            + "\n".join([f"- {name}: {state} - {detail}" for name, state, detail in quick])
            + "\n\nDETAILS:\n"
            + "\n".join([f"- {k}: {v}" for k, v in rows])
            + "\n\nFAEHIGKEITEN:\n"
            + "- Dateien automatisch aendern: JA, ueber Aider/Codex-Modus im aktiven Projektordner.\n"
            + "- Coding live anzeigen: JA, Aider schreibt in das Live-Arbeitsfenster und prueft danach Diff/Test.\n"
            + "- Coding-Dashboard: JA, zeigt Aufgabe, Modell, Diff, Tests, geaenderte Dateien und Backup.\n"
            + "- PC steuern: JA, Apps/Fenster oeffnen, fokussieren, Screenshot, OCR, Klick auf Text, Tippen, Hotkeys.\n"
            + "- Webseiten/Spiele pruefen: JA, Browser-Smoke-Test ist im Aider-Agent eingebaut.\n"
            + "- KI-Bilder/KI-Videos: JA, wenn die lokalen Generatoren laufen und Modelle vorhanden sind.\n"
            + "- Video-Ladebalken: JA, ueber Jarvis, KI Video Ladebalken oder Video Dashboard.\n"
            + "- Zuverlaessigkeits-Guard: JA, prueft Kernmodule, Dashboards, Locks, letzte Fehler und Coding-Schutz.\n"
            + "- Auto-Reparatur: JA, repariert sichere Runtime-Probleme automatisch und schreibt einen Report.\n"
            + "\nBEFEHLE:\n"
            + "\n".join([f"- {c}" for c in commands])
        )

    def _status_detail(self, text: str) -> str:
        text = str(text or "")
        for prefix in ("OK - ", "PRUEFEN - ", "FEHLT - "):
            if text.startswith(prefix):
                return text[len(prefix):]
        return text

    def _internet(self) -> str:
        try:
            urllib.request.urlopen("https://www.google.com", timeout=STATUS_CHECK_TIMEOUT)
            return "OK"
        except Exception as e:
            return f"Nicht erreichbar: {e}"

    def _http(self, url: str) -> str:
        try:
            urllib.request.urlopen(url, timeout=STATUS_CHECK_TIMEOUT)
            return "OK"
        except Exception as e:
            return f"Nicht erreichbar: {e}"

    def _image_status(self) -> str:
        status = self._http(IMAGE_API_URL + "/sdapi/v1/sd-models")
        if status == "OK":
            return "OK"
        return "AUS - Stable Diffusion WebUI/API nicht erreichbar. Starte start_image_generator.bat."

    def _ollama_models(self) -> str:
        if not shutil.which("ollama"):
            return "ollama.exe fehlt"
        try:
            env = os.environ.copy()
            env.setdefault("OLLAMA_MODELS", r"E:\.ollama\models")
            result = subprocess.run(
                ["ollama", "list"],
                text=True,
                capture_output=True,
                timeout=max(8, STATUS_CHECK_TIMEOUT),
                env=env,
            )
            text = (result.stdout or result.stderr or "").lower()
            if result.returncode != 0:
                return "Fehler: " + (result.stderr or result.stdout or "").strip()[:180]
            found = []
            for name in ["qwen3-coder-next:latest", "qwen3-coder:480b", "qwen3-next:80b"]:
                if name in text:
                    found.append(name)
            return "OK - " + (", ".join(found) if found else "Modelle gefunden, Zielmodelle nicht erkannt")
        except Exception as e:
            return f"Nicht pruefbar: {e}"

    def _coding_status(self) -> str:
        root = Path(BASE_DIR)
        aider_conf = root / ".aider.conf.yml"
        model = os.getenv("JARVIS_AIDER_MODEL", "ollama_chat/qwen3-coder-next:latest")
        timeout = os.getenv("JARVIS_AIDER_TIMEOUT", "600")
        live = os.getenv("JARVIS_AIDER_LIVE_WINDOW", "1")
        auto_fix = os.getenv("JARVIS_AIDER_AUTO_FIX_ERRORS", "1")
        internet = os.getenv("JARVIS_ALWAYS_RESEARCH_CODE", "1")
        pages = os.getenv("JARVIS_CODE_RESEARCH_PAGES", "10")
        resources = os.getenv("JARVIS_USE_ALL_CODE_RESOURCES", "1")
        parts = [
            f"Modell={model}",
            f"Timeout={timeout}s",
            f"LiveFenster={'AN' if live == '1' else 'AUS'}",
            f"AutoFix={'AN' if auto_fix == '1' else 'AUS'}",
            f"InternetKontext={'AN' if internet == '1' else 'AUS'}",
            f"RechercheSeiten={pages}",
            f"AlleRessourcen={'AN' if resources == '1' else 'AUS'}",
            f"AiderConfig={'OK' if aider_conf.exists() else 'FEHLT'}",
        ]
        return "OK - " + ", ".join(parts)

    def _service_watcher_status(self) -> str:
        if ServiceWatcher is None:
            return "FEHLT - ServiceWatcher konnte nicht geladen werden"
        try:
            data = ServiceWatcher().snapshot()
            services = data.get("services", {})
            off = [name for name, info in services.items() if not info.get("ok")]
            if off:
                return "PRUEFEN - aus: " + ", ".join(off)
            return "OK - Ollama, ComfyUI, Bildgenerator und Coding erreichbar/bereit"
        except Exception as e:
            return f"PRUEFEN - {e}"

    def _coding_dashboard_status(self) -> str:
        root = Path(BASE_DIR)
        page = root / "jarvis_3d_webgl" / "coding_dashboard.html"
        data_file = root / "data" / "coding_dashboard.json"
        if not page.exists():
            return "FEHLT - coding_dashboard.html fehlt"
        if not data_file.exists():
            return "OK - Seite bereit, noch kein Coding-Auftrag"
        try:
            data = json.loads(data_file.read_text(encoding="utf-8", errors="replace") or "{}")
            state = data.get("state", "idle")
            model = data.get("model", "")
            changed = data.get("changed_files") or []
            return f"OK - Status={state}, Modell={model or 'unbekannt'}, geaendert={len(changed)}"
        except Exception as e:
            return f"PRUEFEN - Dashboard JSON nicht lesbar: {e}"

    def _model_router_status(self) -> str:
        if ModelRouter is None:
            return "FEHLT - ModelRouter konnte nicht geladen werden"
        try:
            return ModelRouter().status().replace("\n", "; ")
        except Exception as e:
            return f"PRUEFEN - {e}"

    def _reliability_status(self) -> str:
        if ReliabilityGuard is None:
            return "FEHLT - ReliabilityGuard konnte nicht geladen werden"
        try:
            guard = ReliabilityGuard()
            status = guard.short_status()
            if status.startswith("OK"):
                return status
            if status.startswith("noch kein"):
                return "PRUEFEN - noch kein Report, sage: Jarvis, Zuverlaessigkeit pruefen"
            return status
        except Exception as e:
            return f"PRUEFEN - {e}"

    def _auto_repair_status(self) -> str:
        if AutoRepair is None:
            return "FEHLT - AutoRepair konnte nicht geladen werden"
        try:
            status = AutoRepair().status()
            if status.startswith("OK"):
                return status
            if status.startswith("noch kein"):
                return "PRUEFEN - noch kein Report, Auto-Reparatur laeuft beim Start"
            return status
        except Exception as e:
            return f"PRUEFEN - {e}"

    def _video_progress_status(self) -> str:
        root = Path(BASE_DIR)
        video_root = root / "Jarvis_Projects" / "ki_videos"
        if not video_root.exists():
            return "noch kein Video-Projekt"
        projects = [p for p in video_root.glob("video_*") if p.is_dir()]
        if not projects:
            return "noch kein Video-Projekt"
        project = max(projects, key=lambda p: p.stat().st_mtime)
        final_files = [
            project / "final_4k_audio.mp4",
            project / "final_video.mp4",
            project / "final_2k_audio.mp4",
        ]
        final = next((p for p in final_files if p.exists()), None)
        if final:
            size_mb = round(final.stat().st_size / (1024 * 1024), 1)
            return f"fertig - {final.name}, {size_mb} MB, Projekt={project.name}"
        status_file = project / "video_render_status.json"
        if not status_file.exists():
            return f"Projekt={project.name}, noch kein Renderstatus"
        try:
            data = json.loads(status_file.read_text(encoding="utf-8", errors="replace") or "{}")
            state = data.get("state", "unbekannt")
            prompt_id = data.get("prompt_id", "")
            queued_at = float(data.get("queued_at") or 0)
            age = int(time.time() - queued_at) if queued_at else 0
            return f"Projekt={project.name}, Status={state}, Laufzeit={age}s, Prompt-ID={prompt_id or 'unbekannt'}"
        except Exception as e:
            return f"Projekt={project.name}, Renderstatus nicht lesbar: {e}"

    def _pc_control_status(self) -> str:
        needed = ["pyautogui", "PIL", "pytesseract"]
        state = []
        for module in needed:
            try:
                __import__(module)
                state.append(f"{module}=OK")
            except Exception:
                state.append(f"{module}=FEHLT")
        return ", ".join(state)

    def _video_status(self, comfy_queue: str = None) -> str:
        ready = Path(BASE_DIR) / "data" / "real_video_models_ready.txt"
        lock = Path(BASE_DIR) / "data" / "ki_video_job.lock"
        parts = []
        parts.append("ReadyDatei=OK" if ready.exists() else "ReadyDatei=FEHLT")
        parts.append("Job=frei" if not lock.exists() else "Job laeuft")
        parts.append(f"OutputFinder={'AN' if os.getenv('JARVIS_VIDEO_OUTPUT_FINDER', '1') == '1' else 'AUS'}")
        parts.append(f"AutoFinalizer={'AN' if os.getenv('JARVIS_VIDEO_AUTO_FINALIZE', '1') == '1' else 'AUS'}")
        parts.append(f"RenderWaechter={'AN' if os.getenv('JARVIS_VIDEO_RENDER_WATCHDOG', '1') == '1' else 'AUS'}")
        parts.append(f"VRAMUnload={'AN' if os.getenv('JARVIS_VIDEO_UNLOAD_OLLAMA', '1') == '1' else 'AUS'}")
        parts.append(comfy_queue if comfy_queue is not None else self._comfy_queue_status())
        return ", ".join(parts)

    def _gpu_status(self) -> str:
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.used,memory.total,utilization.gpu", "--format=csv,noheader,nounits"],
                text=True,
                capture_output=True,
                timeout=max(8, STATUS_CHECK_TIMEOUT),
            )
            text = (result.stdout or result.stderr or "").strip()
            if result.returncode != 0 or not text:
                return "nicht pruefbar"
            first = text.splitlines()[0]
            parts = [p.strip() for p in first.split(",")]
            if len(parts) >= 4:
                name, used, total, util = parts[:4]
                try:
                    free = max(0, int(float(total)) - int(float(used)))
                    return f"{name}: benutzt {used}/{total} MB, frei {free} MB, GPU {util}%"
                except Exception:
                    pass
            return first[:180]
        except Exception as e:
            return f"nicht pruefbar: {e}"

    def _comfy_queue_status(self) -> str:
        try:
            with urllib.request.urlopen(COMFYUI_URL + "/queue", timeout=STATUS_CHECK_TIMEOUT) as response:
                data = json.loads(response.read().decode("utf-8", errors="replace") or "{}")
            running = data.get("queue_running") or []
            pending = data.get("queue_pending") or []
            if running:
                prompt_id = running[0][1] if isinstance(running[0], list) and len(running[0]) > 1 else "unbekannt"
                return f"rendert, Prompt-ID={prompt_id}, wartend={len(pending)}"
            if pending:
                prompt_id = pending[0][1] if isinstance(pending[0], list) and len(pending[0]) > 1 else "unbekannt"
                return f"wartet, Prompt-ID={prompt_id}, wartend={len(pending)}"
            return "frei"
        except Exception as e:
            return f"nicht erreichbar: {e}"

    def _active_jobs_status(self) -> str:
        data_dir = Path(BASE_DIR) / "data"
        jobs = []
        for name, label in [
            ("jarvis_app.lock", "Jarvis App"),
            ("ki_video_job.lock", "KI-Video"),
            ("install_real_video_models.lock", "Video-Download"),
            ("aider_job.lock", "Coding"),
        ]:
            path = data_dir / name
            if path.exists():
                age = int(time.time() - path.stat().st_mtime)
                jobs.append(f"{label} aktiv/Lock {age}s")
        return ", ".join(jobs) if jobs else "frei"

    def _last_error_status(self) -> str:
        logs = Path(BASE_DIR) / "logs"
        candidates = []
        if logs.exists():
            candidates.extend(p for p in logs.glob("*.err.log") if p.is_file())
            candidates.extend(p for p in logs.glob("*error*.log") if p.is_file())
        if not candidates:
            return "kein Error-Log gefunden"
        latest = max(candidates, key=lambda p: p.stat().st_mtime)
        try:
            text = latest.read_text(encoding="utf-8", errors="replace").strip()
            tail = text.splitlines()[-1] if text else "leer"
        except Exception as e:
            tail = f"nicht lesbar: {e}"
        return f"{latest.name}: {tail[:180]}"

    def _chat_voice_status(self) -> str:
        root = Path(BASE_DIR)
        chat = root / "data" / "chat_history.jsonl"
        sessions = root / "data" / "chat_sessions.json"
        voice = root / "voice.py"
        details = [
            f"ChatHistory={'OK' if chat.exists() else 'FEHLT'}",
            f"ChatSessions={'OK' if sessions.exists() else 'FEHLT'}",
            f"VoiceModul={'OK' if voice.exists() else 'FEHLT'}",
        ]
        try:
            import pyttsx3  # noqa: F401
            details.append("TTS=OK")
        except Exception:
            details.append("TTS=FEHLT")
        return ", ".join(details)

    def _storage_status(self) -> str:
        checks = {
            "OLLAMA_MODELS": os.getenv("OLLAMA_MODELS", r"E:\.ollama\models"),
            "HF_HOME": os.getenv("HF_HOME", r"E:\.cache\huggingface"),
            "XDG_CACHE_HOME": os.getenv("XDG_CACHE_HOME", r"E:\.cache"),
        }
        rows = []
        try:
            total, used, free = shutil.disk_usage("E:\\")
            rows.append(
                f"E frei={round(free / (1024 ** 3), 1)} GB von {round(total / (1024 ** 3), 1)} GB"
            )
        except Exception:
            pass
        for key, value in checks.items():
            ok = Path(value).exists() if value else False
            rows.append(f"{key}={value} ({'OK' if ok else 'FEHLT'})")
        return "; ".join(rows)

    def _which_version(self, exe: str, arg: str) -> str:
        if not shutil.which(exe):
            return "fehlt"
        try:
            cmd = f"{exe} {arg}".strip()
            result = subprocess.run(cmd, shell=True, text=True, capture_output=True, timeout=STATUS_CHECK_TIMEOUT)
            out = (result.stdout or result.stderr or "gefunden").splitlines()
            return out[0][:140] if out else "gefunden"
        except Exception:
            return "gefunden"
