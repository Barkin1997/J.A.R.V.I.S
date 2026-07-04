import base64
import json
import math
import os
import re
import shutil
import struct
import subprocess
import sys
import time
import unicodedata
import wave
import webbrowser
from pathlib import Path

import requests

try:
    from config import (
        BASE_DIR,
        COMFYUI_URL,
        VIDEO_OUTPUT_DIR,
        VIDEO_DEFAULT_SECONDS,
        VIDEO_DEFAULT_FPS,
        VIDEO_DEFAULT_WIDTH,
        VIDEO_DEFAULT_HEIGHT,
        VIDEO_TARGET_WIDTH,
        VIDEO_TARGET_HEIGHT,
        VIDEO_ENABLE_AUDIO,
        VIDEO_ENABLE_SPEECH,
        VIDEO_AUDIO_VOICE,
        VIDEO_AUDIO_MALE_VOICE,
        VIDEO_AUDIO_FEMALE_VOICE,
        VIDEO_AUDIO_AUTO_GENDER,
        IMAGE_API_URL,
        IMAGE_STEPS,
        IMAGE_CFG_SCALE,
        IMAGE_SAMPLER,
    )
except Exception:
    BASE_DIR = Path(".")
    COMFYUI_URL = "http://127.0.0.1:8188"
    VIDEO_OUTPUT_DIR = Path("Jarvis_Projects/ki_videos")
    VIDEO_DEFAULT_SECONDS = 4
    VIDEO_DEFAULT_FPS = 16
    VIDEO_DEFAULT_WIDTH = 1024
    VIDEO_DEFAULT_HEIGHT = 576
    VIDEO_TARGET_WIDTH = 3840
    VIDEO_TARGET_HEIGHT = 2160
    VIDEO_ENABLE_AUDIO = True
    VIDEO_ENABLE_SPEECH = True
    VIDEO_AUDIO_VOICE = "Microsoft Michael"
    VIDEO_AUDIO_MALE_VOICE = "Microsoft Michael"
    VIDEO_AUDIO_FEMALE_VOICE = "Microsoft Katja"
    VIDEO_AUDIO_AUTO_GENDER = True
    IMAGE_API_URL = "http://127.0.0.1:7860"
    IMAGE_STEPS = 30
    IMAGE_CFG_SCALE = 7
    IMAGE_SAMPLER = "DPM++ 2M Karras"


VIDEO_SUFFIXES = {".mp4", ".mov", ".mkv", ".webm", ".avi"}


class VideoAISkill:
    def __init__(self):
        self.auto_start = os.getenv("JARVIS_VIDEO_AUTO_START", "1") == "1"
        self.auto_workflow = os.getenv("JARVIS_VIDEO_AUTO_WORKFLOW", "1") == "1"
        self.vram_guard = os.getenv("JARVIS_VIDEO_VRAM_GUARD", "1") == "1"
        self.vram_gb = self._int_env("JARVIS_VIDEO_VRAM_GB", 16)
        self.default_2k = os.getenv("JARVIS_VIDEO_DEFAULT_4K", os.getenv("JARVIS_VIDEO_DEFAULT_2K", "1")) == "1"
        self.unload_ollama_for_video = os.getenv("JARVIS_VIDEO_UNLOAD_OLLAMA", "1") == "1"
        self.render_watchdog = os.getenv("JARVIS_VIDEO_RENDER_WATCHDOG", "1") == "1"
        self.auto_retry_render = os.getenv("JARVIS_VIDEO_AUTO_RETRY", "1") == "1"
        self.max_render_retries = self._int_env("JARVIS_VIDEO_MAX_RETRIES", 1)
        self.workflow_preflight = os.getenv("JARVIS_VIDEO_WORKFLOW_PREFLIGHT", "1") == "1"
        self.output_finder = os.getenv("JARVIS_VIDEO_OUTPUT_FINDER", "1") == "1"
        self.auto_finalize = os.getenv("JARVIS_VIDEO_AUTO_FINALIZE", "1") == "1"
        self._force_storage_env()
        self._output_dir().mkdir(parents=True, exist_ok=True)

    def _int_env(self, name: str, default: int) -> int:
        try:
            return int(os.getenv(name, str(default)))
        except Exception:
            return default

    def status(self) -> str:
        ok, message = self._ensure_comfyui(wait_seconds=5)
        ffmpeg = self._ffmpeg_path()
        model_status = self._model_status_summary()
        storage_status = self._storage_status_summary()
        job_status = self._video_job_status_summary()
        vram_status = self._vram_status_summary()
        if ok:
            return (
                f"KI-Video bereit ueber ComfyUI: {COMFYUI_URL}\n"
                f"Ausgabeordner: {self._output_dir()}\n"
                f"Basis: {VIDEO_DEFAULT_WIDTH}x{VIDEO_DEFAULT_HEIGHT}, Ziel: {VIDEO_TARGET_WIDTH}x{VIDEO_TARGET_HEIGHT}\n"
                f"Audio/Sprache: {'aktiv' if VIDEO_ENABLE_AUDIO else 'aus'}\n"
                f"ffmpeg: {ffmpeg or 'fehlt'}\n"
                f"{job_status}\n{vram_status}\n{model_status}\n{storage_status}"
            )
        return message + f"\nffmpeg: {ffmpeg or 'fehlt'}\n{job_status}\n{vram_status}\n{model_status}\n{storage_status}"

    def ready_status(self, path_text: str = "") -> str:
        project = self._project_from_text(path_text)
        project_text = f"\nProjekt: {project}" if project else ""
        render = self._load_render_status(project)
        queue_data = self._comfyui_queue_data()
        queue = self._comfyui_queue_status(queue_data)
        prompt_id = render.get("prompt_id") or self._active_prompt_id_from_queue(queue_data)
        progress = self._comfyui_progress_data()
        percent = self._progress_percent(progress, prompt_id)
        progress_line = self._progress_bar(percent)
        elapsed_line, eta_line = self._render_timing_lines(project, render, percent)
        prompt_text = f"\nPrompt-ID: {prompt_id}" if prompt_id else ""

        history_state = self._history_state(self._history_for_prompt(prompt_id), prompt_id) if prompt_id else ""
        if history_state == "error":
            return (
                "KI-Video ist fehlgeschlagen.\n"
                f"Fortschritt: {self._progress_bar(0)}\n"
                f"{elapsed_line}\n"
                f"{queue}{prompt_text}{project_text}"
            )

        final_video = self._final_video_for_project(project)
        if final_video:
            self._update_render_status(project, state="finalized", final_video=str(final_video))
            return (
                "KI-Video ist komplett fertig.\n"
                f"Fortschritt: {self._progress_bar(100)}\n"
                f"{elapsed_line}\n"
                f"Final-Datei: {final_video}\n"
                f"{self._final_video_check(final_video)}{project_text}"
            )

        project_video = self._find_video_output_for_project(project)
        if project_video:
            copied = self._copy_video_to_project(project, project_video)
            self._update_render_status(project, state="rendered", source_video=str(copied), completed_at=time.time())
            finalize_note = self._auto_finalize_if_ready(project, copied)
            return (
                "KI-Video ist fertig gerendert.\n"
                f"Fortschritt: {self._progress_bar(100)}\n"
                f"{elapsed_line}\n"
                f"Datei: {copied}\n"
                f"Groesse: {round(copied.stat().st_size / (1024 * 1024), 1)} MB"
                f"{project_text}\n"
                f"{finalize_note}\n\n"
                "Jarvis findet und finalisiert das Video automatisch. Du kannst trotzdem sagen:\n"
                f"Jarvis, KI Video fertigstellen {project or copied.parent}"
            )

        videos = self._recent_output_videos(limit=5)
        if history_state == "success" and videos:
            newest = videos[0]
            return (
                "KI-Video ist fertig gerendert.\n"
                f"Fortschritt: {self._progress_bar(100)}\n"
                f"{elapsed_line}\n"
                f"Datei: {newest}\n"
                f"Groesse: {round(newest.stat().st_size / (1024 * 1024), 1)} MB"
                f"{project_text}\n\n"
                "Jetzt kannst du sagen:\n"
                f"Jarvis, KI Video fertigstellen {project or newest.parent}"
            )

        if "laeuft" in queue.lower() or "wartet" in queue.lower():
            self._update_render_status(
                project,
                state="running" if "laeuft" in queue.lower() else "pending",
                prompt_id=prompt_id or render.get("prompt_id") or "",
                last_queue_status=queue,
            )
            return (
                "KI-Video rendert noch.\n"
                f"Fortschritt: {progress_line}\n"
                f"{elapsed_line}\n"
                f"{eta_line}\n"
                f"{queue}{prompt_text}{project_text}\n"
                "Noch nicht finalisieren. Warte, bis ComfyUI fertig ist und eine Video-Datei erzeugt."
            )
        error = self._latest_comfyui_error()
        if error:
            return f"KI-Video ist fehlgeschlagen.\n{error}{project_text}"
        if videos:
            newest = videos[0]
            return (
                "KI-Video ist fertig gerendert.\n"
                f"Datei: {newest}\n"
                f"Groesse: {round(newest.stat().st_size / (1024 * 1024), 1)} MB"
                f"{project_text}\n\n"
                "Jetzt kannst du sagen:\n"
                f"Jarvis, KI Video fertigstellen {project or newest.parent}"
            )
        watchdog = self._render_watchdog_status(project, render, queue_data, history_state)
        if watchdog:
            return watchdog
        return (
            "Noch kein fertiges KI-Video gefunden.\n"
            f"Fortschritt: {progress_line}\n"
            f"{elapsed_line}\n"
            f"{queue}"
            f"{prompt_text}{project_text}\n"
            "Wenn ComfyUI nicht laeuft, starte ComfyUI erneut. Wenn es laeuft, warte weiter."
        )

    def open(self) -> str:
        self._ensure_comfyui(wait_seconds=10)
        webbrowser.open(COMFYUI_URL, new=2)
        return f"ComfyUI geoeffnet: {COMFYUI_URL}"

    def _force_storage_env(self) -> None:
        if os.getenv("JARVIS_STORAGE_FORCE_E", "1") != "1":
            return
        hf_cache = (Path(BASE_DIR) / "data" / "huggingface_cache").resolve()
        for name, value in {
            "HF_HOME": hf_cache,
            "HF_HUB_CACHE": hf_cache / "hub",
            "TRANSFORMERS_CACHE": hf_cache / "transformers",
            "HF_XET_CACHE": hf_cache / "xet",
        }.items():
            os.environ[name] = str(value)
        e_ollama_models = Path("E:/") / ".ollama" / "models"
        if e_ollama_models.exists():
            os.environ["OLLAMA_MODELS"] = str(e_ollama_models)

    def _video_job_lock_path(self) -> Path:
        data_dir = Path(BASE_DIR) / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        return data_dir / "ki_video_job.lock"

    def _video_job_status_path(self) -> Path:
        data_dir = Path(BASE_DIR) / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        return data_dir / "ki_video_job_status.json"

    def _acquire_video_job(self, prompt: str):
        lock = self._video_job_lock_path()
        status = self._video_job_status_path()
        info = {
            "started": time.strftime("%Y-%m-%d %H:%M:%S"),
            "pid": os.getpid(),
            "prompt": prompt[:500],
        }
        try:
            fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(info, handle, ensure_ascii=False, indent=2)
            status.write_text(json.dumps({"state": "running", **info}, ensure_ascii=False, indent=2), encoding="utf-8")
            return lock
        except FileExistsError:
            age = ""
            try:
                age_seconds = max(0, int(time.time() - lock.stat().st_mtime))
                age = f" seit {age_seconds}s"
            except Exception:
                pass
            return f"Videoauftrag laeuft schon{age}. Ich starte keinen zweiten Job, damit nichts doppelt flackert."
        except Exception as e:
            return f"Videoauftrag konnte nicht gesperrt werden: {e}"

    def _release_video_job(self, lock: Path) -> None:
        try:
            if lock and lock.exists():
                lock.unlink()
            self._video_job_status_path().write_text(
                json.dumps({"state": "idle", "updated": time.strftime("%Y-%m-%d %H:%M:%S")}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass

    def _video_job_status_summary(self) -> str:
        lock = self._video_job_lock_path()
        if not lock.exists():
            return "Video-Job: frei"
        try:
            data = json.loads(lock.read_text(encoding="utf-8", errors="replace"))
            prompt = data.get("prompt", "")
            return f"Video-Job: laeuft seit {data.get('started', '?')} - {prompt[:90]}"
        except Exception:
            return "Video-Job: laeuft"

    def _comfyui_queue_data(self) -> dict:
        try:
            r = requests.get(f"{COMFYUI_URL}/queue", timeout=8)
            if not r.ok:
                return {"_error": f"HTTP {r.status_code}"}
            return r.json()
        except Exception as e:
            return {"_error": str(e)}

    def _comfyui_queue_status(self, data: dict | None = None) -> str:
        data = data if isinstance(data, dict) else self._comfyui_queue_data()
        if data.get("_error"):
            return f"ComfyUI nicht erreichbar: {data['_error']}"
        running = data.get("queue_running") or []
        pending = data.get("queue_pending") or []
        if running:
            prompt_id = self._queue_entry_prompt_id(running[0]) or "unbekannt"
            return f"ComfyUI: laeuft gerade. Prompt-ID: {prompt_id}. Wartend: {len(pending)}"
        if pending:
            prompt_id = self._queue_entry_prompt_id(pending[0]) or "unbekannt"
            return f"ComfyUI: wartet in Queue. Prompt-ID: {prompt_id}. Wartend: {len(pending)}"
        return "ComfyUI: frei, kein laufender Videojob."

    def _queue_entry_prompt_id(self, entry) -> str:
        if isinstance(entry, dict):
            return str(entry.get("prompt_id") or entry.get("id") or "")
        if isinstance(entry, (list, tuple)) and len(entry) > 1:
            return str(entry[1] or "")
        return ""

    def _active_prompt_id_from_queue(self, data: dict) -> str:
        if not isinstance(data, dict):
            return ""
        for key in ("queue_running", "queue_pending"):
            entries = data.get(key) or []
            if entries:
                prompt_id = self._queue_entry_prompt_id(entries[0])
                if prompt_id:
                    return prompt_id
        return ""

    def _comfyui_progress_data(self) -> dict:
        try:
            r = requests.get(f"{COMFYUI_URL}/progress", timeout=5)
            if not r.ok:
                return {"_error": f"HTTP {r.status_code}"}
            return r.json()
        except Exception as e:
            return {"_error": str(e)}

    def _progress_percent(self, data: dict, prompt_id: str = ""):
        if not isinstance(data, dict) or data.get("_error"):
            return None
        data_prompt = str(data.get("prompt_id") or data.get("id") or "")
        if prompt_id and data_prompt and data_prompt != prompt_id:
            return None
        for key in ("percent", "percentage", "progress"):
            value = data.get(key)
            if isinstance(value, (int, float)):
                pct = value * 100 if 0 <= value <= 1 else value
                return max(0, min(100, int(round(pct))))
        value = data.get("value", data.get("current"))
        maximum = data.get("max", data.get("total"))
        try:
            value = float(value)
            maximum = float(maximum)
            if maximum > 0:
                return max(0, min(100, int(round((value / maximum) * 100))))
        except Exception:
            return None
        return None

    def _progress_bar(self, percent, width: int = 24) -> str:
        if percent is None:
            return "[" + ("#" * 6) + ("." * (width - 6)) + "] laeuft"
        percent = max(0, min(100, int(percent)))
        filled = max(0, min(width, int(round(width * (percent / 100)))))
        return "[" + ("#" * filled) + ("." * (width - filled)) + f"] {percent}%"

    def _format_seconds(self, seconds: float) -> str:
        seconds = max(0, int(seconds))
        hours, rest = divmod(seconds, 3600)
        minutes, secs = divmod(rest, 60)
        if hours:
            return f"{hours}h {minutes}m {secs}s"
        if minutes:
            return f"{minutes}m {secs}s"
        return f"{secs}s"

    def _render_timing_lines(self, project: Path | None, render: dict, percent):
        started = 0.0
        try:
            started = float(render.get("queued_at") or 0)
        except Exception:
            started = 0.0
        if not started and project:
            for name in ("video_render_status.json", "queued_payload.json", "video_settings.json"):
                candidate = project / name
                try:
                    if candidate.exists():
                        started = candidate.stat().st_mtime
                        break
                except Exception:
                    pass
        if not started:
            return "Laufzeit: unbekannt", "Restzeit: wird angezeigt, sobald der Auftrag neu gestartet wurde."
        elapsed = max(0, time.time() - started)
        elapsed_line = f"Laufzeit: {self._format_seconds(elapsed)}"
        eta_line = "Restzeit: wird geschaetzt, sobald ComfyUI Fortschritt liefert."
        if isinstance(percent, int) and 1 <= percent < 100:
            eta = elapsed * ((100 - percent) / max(1, percent))
            eta_line = f"Restzeit: ca. {self._format_seconds(eta)}"
        elif percent == 100:
            eta_line = "Restzeit: fertig"
        return elapsed_line, eta_line

    def _render_status_path(self, folder: Path) -> Path:
        return folder / "video_render_status.json"

    def _write_render_status(self, folder: Path, prompt_id: str, workflow_name: str, settings: dict) -> None:
        try:
            data = {
                "state": "queued",
                "prompt_id": prompt_id,
                "workflow": workflow_name,
                "queued_at": time.time(),
                "queued_at_text": time.strftime("%Y-%m-%d %H:%M:%S"),
                "base_width": settings.get("base_width"),
                "base_height": settings.get("base_height"),
                "target_width": settings.get("target_width"),
                "target_height": settings.get("target_height"),
                "frames": settings.get("frames"),
                "fps": settings.get("fps"),
                "seconds": settings.get("seconds"),
            }
            self._render_status_path(folder).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _load_render_status(self, project: Path | None) -> dict:
        if not project:
            return {}
        try:
            path = self._render_status_path(project)
            if path.exists():
                return json.loads(path.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            pass
        return {}

    def _history_for_prompt(self, prompt_id: str) -> dict:
        if not prompt_id:
            return {}
        try:
            r = requests.get(f"{COMFYUI_URL}/history/{prompt_id}", timeout=8)
            if not r.ok:
                return {}
            return r.json()
        except Exception:
            return {}

    def _history_state(self, history: dict, prompt_id: str) -> str:
        if not isinstance(history, dict) or not history:
            return ""
        item = history.get(prompt_id)
        if not isinstance(item, dict):
            item = next((value for value in history.values() if isinstance(value, dict)), {})
        status = item.get("status") if isinstance(item, dict) else {}
        if not isinstance(status, dict):
            return ""
        status_text = str(status.get("status_str") or "").lower()
        messages = str(status.get("messages") or "").lower()
        if "error" in status_text or "failed" in status_text or "execution_error" in messages:
            return "error"
        if status.get("completed") or status_text in {"success", "completed"}:
            return "success"
        return ""

    def _recent_output_videos(self, limit: int = 5):
        roots = []
        project_root = self._output_dir()
        if project_root.exists():
            roots.append(project_root)
        comfy_output = Path(BASE_DIR) / "external" / "ComfyUI" / "output"
        if comfy_output.exists():
            roots.append(comfy_output)
        files = []
        for root in roots:
            try:
                files.extend(p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in VIDEO_SUFFIXES and p.stat().st_size > 1024)
            except Exception:
                pass
        files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return files[:limit]

    def _final_video_for_project(self, project: Path | None):
        if not project:
            return None
        for name in ("final_4k_audio.mp4", "final_video.mp4", "final_2k_audio.mp4"):
            path = project / name
            try:
                if path.exists() and path.stat().st_size > 1024:
                    return path
            except Exception:
                pass
        return None

    def _find_video_output_for_project(self, project: Path | None):
        if not self.output_finder or not project:
            return None
        render = self._load_render_status(project)
        started = 0.0
        try:
            started = float(render.get("queued_at") or 0)
        except Exception:
            started = 0.0
        if not started:
            for name in ("video_render_status.json", "queued_payload.json", "video_settings.json"):
                try:
                    candidate = project / name
                    if candidate.exists():
                        started = candidate.stat().st_mtime
                        break
                except Exception:
                    pass
        roots = [project, Path(BASE_DIR) / "external" / "ComfyUI" / "output"]
        matches = []
        for root in roots:
            if not root.exists():
                continue
            try:
                for path in root.rglob("*"):
                    if not path.is_file() or path.suffix.lower() not in VIDEO_SUFFIXES:
                        continue
                    if path.name.lower().startswith("final_"):
                        continue
                    try:
                        stat = path.stat()
                    except Exception:
                        continue
                    if stat.st_size <= 1024:
                        continue
                    if started and stat.st_mtime < started - 90:
                        continue
                    matches.append(path)
            except Exception:
                pass
        if not matches:
            return None
        return sorted(matches, key=lambda p: p.stat().st_mtime, reverse=True)[0]

    def _copy_video_to_project(self, project: Path | None, source: Path):
        if not project or not source:
            return source
        try:
            source = source.resolve()
            project = project.resolve()
            if self._is_relative_to(source, project):
                return source
            target = project / f"comfyui_output_{source.name}"
            if target.exists() and target.stat().st_size == source.stat().st_size:
                return target
            if target.exists():
                target = project / f"comfyui_output_{int(time.time())}_{source.name}"
            shutil.copy2(source, target)
            (project / "source_video.txt").write_text(str(source), encoding="utf-8")
            return target
        except Exception:
            return source

    def _update_render_status(self, project: Path | None, **updates) -> None:
        if not project:
            return
        try:
            data = self._load_render_status(project)
            data.update(updates)
            data["updated_at"] = time.time()
            data["updated_at_text"] = time.strftime("%Y-%m-%d %H:%M:%S")
            self._render_status_path(project).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _auto_finalize_if_ready(self, project: Path | None, source_video: Path) -> str:
        if not self.auto_finalize:
            return "Auto-Finalizer: aus"
        if not project:
            return "Auto-Finalizer: kein Projektordner"
        final = self._final_video_for_project(project)
        if final:
            return f"Auto-Finalizer: bereits fertig: {final}"
        script = project / "video_postprocess.py"
        if not script.exists():
            return "Auto-Finalizer: Postprocess-Skript fehlt"
        render = self._load_render_status(project)
        if render.get("state") == "finalizing":
            return "Auto-Finalizer: laeuft bereits"
        try:
            cmd = [sys.executable, str(script), str(source_video)]
            log = project / "auto_finalize_command.txt"
            log.write_text(" ".join(f'"{x}"' if " " in str(x) else str(x) for x in cmd), encoding="utf-8")
            subprocess.Popen(
                cmd,
                cwd=str(project),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            self._update_render_status(project, state="finalizing", source_video=str(source_video), finalize_started_at=time.time())
            return "Auto-Finalizer: gestartet. Jarvis erstellt jetzt automatisch 2K/4K + Audio."
        except Exception as e:
            return f"Auto-Finalizer: Start fehlgeschlagen: {e}"

    def _latest_comfyui_error(self) -> str:
        # History is per prompt-id, so without a prompt id we only report active queue state here.
        return ""

    def create_video_project(self, prompt: str) -> str:
        prompt = (prompt or "").strip()
        if not prompt:
            return "Video-Prompt fehlt. Beispiel: Jarvis, erstelle KI Video orange Roboter spricht in futuristischer Stadt"

        lock = self._acquire_video_job(prompt)
        if not isinstance(lock, Path):
            return lock
        try:
            return self._create_video_project_locked(prompt)
        finally:
            self._release_video_job(lock)

    def _create_video_project_locked(self, prompt: str) -> str:
        settings = self._video_settings(prompt)
        workflow_path, workflow_reason = self._select_workflow(prompt, settings)
        settings["workflow_name"] = workflow_path.name if workflow_path else ""
        settings["workflow_reason"] = workflow_reason
        vram_prepare = self._free_vram_for_video(settings)
        ok, status_message = self._ensure_comfyui(wait_seconds=20)
        real_ready, real_report = self._real_video_readiness(settings)
        workflow_check = self._workflow_preflight_report(workflow_path, settings) if self.workflow_preflight else "Workflow-Preflight: aus"

        out_dir = self._output_dir()
        out_dir.mkdir(parents=True, exist_ok=True)
        folder = out_dir / f"video_{time.strftime('%Y%m%d_%H%M%S')}"
        folder.mkdir(parents=True, exist_ok=True)

        enhanced = (
            prompt
            + ", cinematic, smooth coherent motion, high quality, orange black futuristic Jarvis style, "
            "dramatic lighting, sharp detail, stable character identity, clean composition"
        )
        negative = "low quality, blurry, flicker, watermark, text errors, deformed, distorted, unstable face"

        speech_text = self._speech_text(prompt)
        sound_text = self._sound_design(prompt)
        settings.update(
            {
                "prompt": enhanced,
                "negative_prompt": negative,
                "speech_text": speech_text,
                "sound_design": sound_text,
                "mode": "ComfyUI",
                "comfyui_url": COMFYUI_URL,
                "ffmpeg": self._ffmpeg_path() or "",
            }
        )

        (folder / "prompt.txt").write_text(enhanced, encoding="utf-8")
        (folder / "negative_prompt.txt").write_text(negative, encoding="utf-8")
        (folder / "speech_de.txt").write_text(speech_text, encoding="utf-8")
        (folder / "sound_design.txt").write_text(sound_text, encoding="utf-8")
        (folder / "video_settings.json").write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")
        (folder / "real_video_status.txt").write_text(real_report, encoding="utf-8")
        (folder / "workflow_status.txt").write_text(workflow_reason, encoding="utf-8")
        (folder / "workflow_preflight.txt").write_text(workflow_check, encoding="utf-8")
        studio_result = self._write_video_studio_files(folder, prompt, settings)

        audio_result = self._create_audio_assets(folder, settings)
        self._copy_templates(folder)
        self._write_postprocess_tools(folder, settings)

        if ok and (real_ready or not settings.get("real_motion_required")):
            queue_result = self._queue_if_possible(folder, enhanced, negative, settings)
            webbrowser.open(COMFYUI_URL, new=2)
        elif ok:
            queue_result = real_report
        else:
            queue_result = status_message + "\n" + real_report

        fallback_result = ""
        if "kein echter queuebarer Video-Workflow" in queue_result or not ok or (settings.get("real_motion_required") and not real_ready):
            fallback_note = ""
            if settings.get("real_motion_required") and not real_ready:
                fallback_note = "ECHT-VIDEO NOCH NICHT BEREIT: Das folgende Video ist nur eine Vorschau mit Kamera-Bewegung.\n"
            fallback_result = fallback_note + self._create_fallback_motion_video(folder, enhanced, negative, settings)

        render_status = self.ready_status(str(folder))

        (folder / "README_START.txt").write_text(
            f"""KI-VIDEO PROJEKT 4K + AUDIO

Prompt:
{enhanced}

Negative:
{negative}

Ausgabeziel:
- Basis-Render: {settings['base_width']}x{settings['base_height']}
- Zielvideo: {settings['target_width']}x{settings['target_height']} (4K)
- Dauer: {settings['seconds']} Sekunden
- FPS: {settings['fps']}

Audio:
- Sprache: {'aktiv' if settings['speech_enabled'] else 'aus'}
- Stimme: {settings['voice']}
- Sound: {'aktiv' if settings['audio_enabled'] else 'aus'}
- Speech-Datei: speech_de.txt
- Sound-Datei: sound_design.txt
- Ergebnis: {audio_result}

Automatik:
- Gewaehlter Workflow: {settings.get('workflow_name') or 'kein Workflow gefunden'}
- Grund: {settings.get('workflow_reason') or 'keine Auswahl'}
- VRAM-Schutz: {settings.get('vram_guard_note') or 'aus'}
- VRAM-Manager: {vram_prepare}
- Workflow-Preflight: {workflow_check}
- Video-Studio: {studio_result}

Echt-Video Status:
{real_report}

{queue_result}
{fallback_result}

Nach dem ComfyUI-Render:
1. Lege das fertige Video in diesen Ordner, oder starte make_4k_with_audio.bat und gib den Videopfad an.
2. Jarvis/ffmpeg erstellt daraus final_4k_audio.mp4.

Wenn kein echter Workflow gequeued wurde:
1. start_comfyui.bat starten.
2. In ComfyUI einen echten Video-Workflow mit den noetigen Nodes/Modellen laden.
3. Prompt aus prompt.txt einfuegen.
4. Queue Prompt druecken.
5. Danach make_4k_with_audio.bat starten.
""",
            encoding="utf-8",
        )

        return (
            f"KI-Video-Projekt erstellt: {folder}\n"
            f"4K-Ziel: {settings['target_width']}x{settings['target_height']}\n"
            f"Audio: {audio_result}\n"
            f"Workflow: {settings.get('workflow_name') or 'kein Workflow'} ({settings.get('workflow_reason')})\n"
            f"VRAM-Schutz: {settings.get('vram_guard_note') or 'aus'}\n"
            f"VRAM-Manager: {vram_prepare}\n"
            f"Workflow-Preflight: {workflow_check}\n"
            f"Video-Studio: {studio_result}\n"
            f"Echt-Video: {real_report}\n"
            f"Render-Anzeige:\n{render_status}\n"
            f"{queue_result}\n{fallback_result}"
        )

    def finalize_video(self, path_text: str = "") -> str:
        project = self._project_from_text(path_text)
        if not project:
            return "Kein KI-Video-Projekt gefunden. Erstelle zuerst ein KI Video."
        project = project.resolve()
        script = project / "video_postprocess.py"
        if not script.exists():
            return f"Postprocess-Skript fehlt in: {project}"
        settings = {}
        try:
            settings = json.loads((project / "video_settings.json").read_text(encoding="utf-8", errors="replace"))
        except Exception:
            settings = {}
        target_w = int(settings.get("target_width", VIDEO_TARGET_WIDTH))
        target_h = int(settings.get("target_height", VIDEO_TARGET_HEIGHT))
        quality_name = "4K" if max(target_w, target_h) >= 3840 else "2K" if max(target_w, target_h) >= 2048 else f"{target_w}x{target_h}"
        args = [sys.executable, str(script)]
        video = self._clean_path(path_text)
        if video and video.exists() and video.suffix.lower() in VIDEO_SUFFIXES:
            args.append(str(video))
        try:
            result = subprocess.run(args, cwd=str(project), capture_output=True, text=True, timeout=1800)
        except Exception as e:
            return f"{quality_name}-Video-Fertigstellung fehlgeschlagen: {e}"
        output = (result.stdout or "") + ("\n" + result.stderr if result.stderr else "")
        if result.returncode != 0:
            return f"{quality_name}-Video-Fertigstellung fehlgeschlagen.\n{output.strip()}"
        final = project / "final_4k_audio.mp4"
        if final.exists():
            self._open_file(final)
            self._open_folder(project)
        final_check = self._final_video_check(final) if final.exists() else "Finaltest: final_4k_audio.mp4 fehlt."
        return f"{quality_name}-Video mit Audio fertig.\nDatei: {final}\n{final_check}\n{output.strip()}"

    def install_hint(self) -> str:
        return (
            "KI-Video installieren:\n"
            "install_video_ai.bat\n\n"
            "Danach starten:\n"
            "start_comfyui.bat\n\n"
            "Befehl:\n"
            "Jarvis, erstelle KI Video orange Jarvis Roboter spricht in futuristischer Stadt 4K mit Sound\n\n"
            "Nach dem Render:\n"
            "Jarvis, KI Video fertigstellen"
        )

    def _video_settings(self, prompt: str):
        low = self._plain_lower(prompt)
        seconds = self._number_from_text(low, r"(\d+)\s*(sekunden|sekunde|second|seconds|sec|s)\b", VIDEO_DEFAULT_SECONDS)
        fps = self._number_from_text(low, r"(\d+)\s*(fps|bilder pro sekunde)\b", VIDEO_DEFAULT_FPS)
        seconds = max(1, min(seconds, 30))
        fps = max(8, min(fps, 30))

        base_width = VIDEO_DEFAULT_WIDTH
        base_height = VIDEO_DEFAULT_HEIGHT
        target_width = VIDEO_TARGET_WIDTH
        target_height = VIDEO_TARGET_HEIGHT

        if any(word in low for word in ["hochkant", "portrait", "tiktok", "shorts", "reel"]):
            base_width, base_height = 576, 1024
            target_width, target_height = 2160, 3840
        elif any(word in low for word in ["quadratisch", "square"]):
            base_width = base_height = 1024
            target_width = target_height = 4096
        elif "720" in low:
            base_width, base_height = 1280, 720
            target_width, target_height = 3840, 2160

        wants_2k = self.default_2k or any(word in low for word in ["2k", "4k", "2048", "4096", "hochqualitaet", "hochqualität"])
        if not wants_2k:
            target_width, target_height = base_width, base_height

        audio_enabled = VIDEO_ENABLE_AUDIO and not any(word in low for word in ["ohne sound", "ohne ton", "kein sound", "kein ton"])
        speech_enabled = VIDEO_ENABLE_SPEECH and not any(word in low for word in ["ohne sprache", "keine sprache", "ohne reden"])

        settings = {
            "seconds": seconds,
            "fps": fps,
            "frames": seconds * fps,
            "base_width": base_width,
            "base_height": base_height,
            "target_width": target_width,
            "target_height": target_height,
            "audio_enabled": audio_enabled,
            "speech_enabled": speech_enabled,
            "voice": self._voice_for_prompt(prompt),
            "real_motion_required": self._real_motion_requested(prompt),
            "preset": self._video_preset(low),
            "preview_first": os.getenv("JARVIS_VIDEO_PREVIEW_FIRST", "1") == "1",
        }
        self._apply_vram_guard(settings, low)
        return settings

    def studio(self) -> str:
        return (
            "KI-VIDEO STUDIO\n"
            "Bereit fuer: TikTok/Reel/Shorts, YouTube, normales Video, sprechender Mensch, Tanz, Bild-zu-Video, Kamera-Control, Anime, Upscale.\n"
            "Automatik:\n"
            "- Storyboard und Shot-Liste werden pro Projekt gespeichert.\n"
            "- Charakter-Hinweise werden gespeichert, damit die Figur stabil bleibt.\n"
            "- Untertiteldatei wird aus dem Sprachtext erstellt.\n"
            "- Erst Basis/Preview passend zu VRAM, danach 2K/4K-Finalisierung mit Audio.\n"
            "- Nach Finalisierung prueft Jarvis Laenge, Video/Audio und oeffnet Datei + Ordner.\n\n"
            "Befehle:\n"
            "- Jarvis, mach TikTok Video ...\n"
            "- Jarvis, mach sprechenden Menschen ...\n"
            "- Jarvis, mach Tanzvideo ...\n"
            "- Jarvis, mach Bild zu Video mit Referenz ...\n"
            "- Jarvis, KI Video fertigstellen"
        )

    def _video_preset(self, low_prompt: str) -> str:
        if any(word in low_prompt for word in ["tiktok", "shorts", "reel", "hochkant", "portrait"]):
            return "TikTok/Reel 9:16"
        if any(word in low_prompt for word in ["youtube", "16:9", "breitbild", "landscape"]):
            return "YouTube 16:9"
        if any(word in low_prompt for word in ["quadratisch", "square", "instagram post"]):
            return "Square 1:1"
        if any(word in low_prompt for word in ["anime", "manga"]):
            return "Anime"
        if any(word in low_prompt for word in ["produkt", "werbung", "product"]):
            return "Produkt/Ad"
        return "Auto"

    def _write_video_studio_files(self, folder: Path, prompt: str, settings: dict) -> str:
        speech_text = settings.get("speech_text") or self._speech_text(prompt)
        shots = self._storyboard_shots(prompt, settings)
        storyboard = [
            "# KI-Video Studio",
            "",
            f"Preset: {settings.get('preset', 'Auto')}",
            f"Workflow: {settings.get('workflow_name') or 'Auto'}",
            f"Ziel: {settings.get('target_width')}x{settings.get('target_height')}",
            f"Basis/Preview: {settings.get('base_width')}x{settings.get('base_height')}",
            f"Dauer: {settings.get('seconds')}s bei {settings.get('fps')}fps",
            "",
            "## Charakter-Konstanz",
            self._character_identity(prompt),
            "",
            "## Shot-Liste",
        ]
        for shot in shots:
            storyboard.append(f"{shot['nr']}. {shot['time']} - {shot['camera']} - {shot['action']}")
        storyboard.extend([
            "",
            "## Sprache",
            speech_text,
            "",
            "## Ablauf",
            "1. Preview/Basis mit VRAM-Schutz rendern.",
            "2. Ergebnis in diesen Projektordner legen oder ComfyUI-Queue nutzen.",
            "3. KI Video fertigstellen: 2K/4K-Upscale, Audio, Untertitel-Hinweis, Finaltest.",
        ])
        (folder / "storyboard.md").write_text("\n".join(storyboard), encoding="utf-8")
        (folder / "shot_list.json").write_text(json.dumps(shots, ensure_ascii=False, indent=2), encoding="utf-8")
        (folder / "character_identity.txt").write_text(self._character_identity(prompt), encoding="utf-8")
        (folder / "subtitles.srt").write_text(self._srt_from_text(speech_text, int(settings.get("seconds", 6))), encoding="utf-8")
        return "Studio-Dateien: storyboard.md, shot_list.json, character_identity.txt, subtitles.srt"

    def _storyboard_shots(self, prompt: str, settings: dict):
        seconds = max(1, int(settings.get("seconds", 6)))
        third = max(1, seconds // 3)
        preset = settings.get("preset", "Auto")
        base = (prompt or "").strip()
        return [
            {
                "nr": 1,
                "time": f"0-{third}s",
                "camera": "Establishing shot, stable framing",
                "action": f"Szene einfuehren: {base[:160]}",
                "preset": preset,
            },
            {
                "nr": 2,
                "time": f"{third}-{min(seconds, third * 2)}s",
                "camera": "Medium shot, leichte Kamerabewegung",
                "action": "Hauptbewegung/Handlung klar zeigen, Gesicht und Koerper stabil halten.",
                "preset": preset,
            },
            {
                "nr": 3,
                "time": f"{min(seconds, third * 2)}-{seconds}s",
                "camera": "Close-up oder dynamischer Abschluss",
                "action": "Finaler Moment mit sauberem Licht, lesbarer Bewegung und ohne Flackern.",
                "preset": preset,
            },
        ]

    def _character_identity(self, prompt: str) -> str:
        low = self._plain_lower(prompt)
        if any(word in low for word in ["frau", "maedchen", "girl", "woman", "anime"]):
            return "Gleiche weibliche Figur beibehalten: Gesicht, Frisur, Kleidung, Farben und Koerperform stabil halten."
        if any(word in low for word in ["mann", "junge", "boy", "man"]):
            return "Gleiche maennliche Figur beibehalten: Gesicht, Kleidung, Farben, Koerperform und Proportionen stabil halten."
        if any(word in low for word in ["roboter", "robot", "jarvis"]):
            return "Gleichen Jarvis/Roboter-Charakter beibehalten: orange-schwarz, leuchtende Details, futuristische Linien."
        return "Hauptmotiv ueber alle Frames stabil halten: Form, Farbe, Outfit/Material und Beleuchtung nicht wechseln."

    def _srt_from_text(self, text: str, seconds: int) -> str:
        clean = " ".join((text or "").split()) or " "
        return f"1\n00:00:00,000 --> 00:00:{max(1, seconds):02d},000\n{clean}\n"

    def _apply_vram_guard(self, settings: dict, low_prompt: str) -> None:
        if not self.vram_guard:
            settings["vram_guard_note"] = "aus"
            return
        if self.vram_gb > 16 and "ultra" not in low_prompt:
            settings["vram_guard_note"] = f"ausreichend VRAM erkannt ({self.vram_gb} GB)"
            return

        original = (
            settings["base_width"],
            settings["base_height"],
            settings["seconds"],
            settings["fps"],
        )
        portrait = settings["base_height"] > settings["base_width"]
        square = settings["base_height"] == settings["base_width"]
        if portrait:
            settings["base_width"], settings["base_height"] = min(settings["base_width"], 576), min(settings["base_height"], 1024)
        elif square:
            settings["base_width"] = settings["base_height"] = min(settings["base_width"], 768)
        else:
            settings["base_width"], settings["base_height"] = min(settings["base_width"], 1024), min(settings["base_height"], 576)
        if settings.get("real_motion_required"):
            settings["seconds"] = min(settings["seconds"], 6)
            settings["fps"] = min(settings["fps"], 16)
        else:
            settings["seconds"] = min(settings["seconds"], 8)
            settings["fps"] = min(settings["fps"], 16)
        settings["frames"] = max(1, settings["seconds"] * settings["fps"])
        settings["vram_guard_note"] = (
            f"aktiv fuer {self.vram_gb} GB VRAM: Basis {original[0]}x{original[1]}/{original[2]}s/{original[3]}fps "
            f"-> {settings['base_width']}x{settings['base_height']}/{settings['seconds']}s/{settings['fps']}fps, danach Ziel-Upscale"
        )

    def _plain_lower(self, text: str) -> str:
        value = unicodedata.normalize("NFKD", text or "")
        value = "".join(ch for ch in value if not unicodedata.combining(ch))
        return value.lower()

    def _voice_for_prompt(self, prompt: str) -> str:
        if not VIDEO_AUDIO_AUTO_GENDER:
            return VIDEO_AUDIO_VOICE
        low = self._plain_lower(prompt)
        female_words = [
            "frau",
            "weiblich",
            "maedchen",
            "madchen",
            "girl",
            "woman",
            "female",
            "dame",
            "katja",
            "frauenstimme",
            "weibliche stimme",
        ]
        male_words = [
            "mann",
            "maennlich",
            "mannlich",
            "junge",
            "boy",
            "man",
            "male",
            "michael",
            "maennerstimme",
            "mannerstimme",
            "maennliche stimme",
            "mannliche stimme",
        ]
        if any(word in low for word in female_words):
            return VIDEO_AUDIO_FEMALE_VOICE
        if any(word in low for word in male_words):
            return VIDEO_AUDIO_MALE_VOICE
        return VIDEO_AUDIO_VOICE

    def _real_motion_requested(self, prompt: str) -> bool:
        low = self._plain_lower(prompt)
        real_words = [
            "tiktok",
            "shorts",
            "reel",
            "echtes video",
            "echte bewegung",
            "realistisch",
            "lip sync",
            "lipsync",
            "lippen",
            "mundbewegung",
            "mund bewegt",
            "spricht",
            "redet",
            "laeuft",
            "lauft",
            "geht",
            "tanzt",
            "figur",
            "person",
            "wan",
            "animatediff",
            "animate",
        ]
        return any(word in low for word in real_words)

    def _real_video_readiness(self, settings: dict):
        base = Path(BASE_DIR) / "external" / "ComfyUI"
        models = base / "models"
        nodes = base / "custom_nodes"
        missing = []
        found = []

        if (nodes / "ComfyUI-WanVideoWrapper").exists():
            found.append("WanVideoWrapper installiert")
        else:
            missing.append("ComfyUI-WanVideoWrapper fehlt")

        if (nodes / "ComfyUI-VideoHelperSuite").exists():
            found.append("VideoHelperSuite installiert")
        else:
            missing.append("ComfyUI-VideoHelperSuite fehlt")

        video_models = self._find_model_files(
            [models / "diffusion_models", models / "unet"],
            ["wan", "video", "t2v", "i2v", "animate", "hunyuan", "ltx", "cogvideo", "skyreels"],
        )
        text_encoders = self._find_model_files(
            [models / "text_encoders", models / "clip"],
            ["qwen", "umt5", "t5", "clip", "text"],
        )
        vae_models = self._find_model_files([models / "vae"], ["wan", "video", "vae"])
        audio_models = self._find_model_files(
            [models / "audio_encoders", models / "transformers", models / "diffusion_models", models / "unet"],
            ["wav2vec", "fantasy", "talk", "multitalk", "kokoro", "audio"],
        )
        workflows = self._queueable_workflow_files()

        if video_models:
            found.append(f"Video-Modell: {video_models[0].name}")
        else:
            missing.append("Video-Hauptmodell fehlt in ComfyUI/models/diffusion_models oder unet")

        if text_encoders:
            found.append(f"Text-Encoder: {text_encoders[0].name}")
        else:
            missing.append("Text-Encoder fehlt in ComfyUI/models/text_encoders")

        if vae_models:
            found.append(f"VAE: {vae_models[0].name}")
        else:
            missing.append("Video-VAE fehlt in ComfyUI/models/vae")

        if settings.get("real_motion_required"):
            if audio_models:
                found.append(f"Talking/LipSync-Modell: {audio_models[0].name}")
            elif settings.get("speech_enabled"):
                missing.append("Talking/LipSync-Audio-Modell fehlt fuer echte Mundbewegung")

        if workflows:
            found.append(f"Queuebarer Workflow: {workflows[0].name}")
        else:
            missing.append("Queuebarer Video-Workflow fehlt in comfyui_video_workflows")

        if not settings.get("real_motion_required"):
            return True, "Normaler Video-Modus. Fuer echte Figur-/Mundbewegung sage: TikTok, Figur bewegt sich, spricht oder Lippenbewegung."

        ready = not missing
        if ready:
            return True, "ECHT-VIDEO BEREIT: " + "; ".join(found)

        return (
            False,
            "ECHT-VIDEO FEHLT NOCH: "
            + "; ".join(missing)
            + "\nGefunden: "
            + ("; ".join(found) if found else "keine echten Video-Komponenten")
        )

    def _find_model_files(self, folders, keywords):
        suffixes = {".safetensors", ".ckpt", ".pt", ".pth", ".bin", ".gguf"}
        result = []
        for folder in folders:
            if not folder.exists():
                continue
            for path in folder.rglob("*"):
                if not path.is_file() or path.suffix.lower() not in suffixes:
                    continue
                low = path.name.lower()
                if any(key in low for key in keywords):
                    result.append(path)
        return sorted(result, key=lambda p: p.stat().st_size if p.exists() else 0, reverse=True)

    def _queueable_workflow_files(self):
        workflow_dir = Path(BASE_DIR) / "comfyui_video_workflows"
        if not workflow_dir.exists():
            return []
        found = []
        for path in workflow_dir.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
            except Exception:
                continue
            if isinstance(data, dict) and data.get("type") == "template":
                continue
            if isinstance(data, dict) and ("prompt" in data or "nodes" in data or any(str(k).isdigit() for k in data.keys())):
                found.append(path)
        return found

    def _workflow_dir(self) -> Path:
        return Path(BASE_DIR) / "comfyui_video_workflows"

    def _select_workflow(self, prompt: str, settings: dict):
        workflows = {path.name.lower(): path for path in self._queueable_workflow_files()}
        if not self.auto_workflow:
            fallback = next(iter(workflows.values()), None)
            return fallback, "Auto-Auswahl aus; erster queuebarer Workflow" if fallback else "kein Workflow gefunden"

        low = self._plain_lower(prompt)
        rules = [
            (
                "Upscale/Qualitaet",
                ["upscale", "hochskal", "schaerfer", "scharfer", "qualitaet verbessern", "qualität verbessern", "4k upscale", "flashvsr"],
                ["jarvis_wan_flashvsr_upscale_ultra.json"],
            ),
            (
                "Tanz/Pose",
                ["tanz", "tanzt", "dance", "dancer", "steadydancer", "pose"],
                ["jarvis_wan_steadydancer_pose_ultra.json", "jarvis_wan_fun_control_ultra.json", "jarvis_wan_t2v_best.json"],
            ),
            (
                "Kamera/Control",
                ["kamera", "camera", "control", "kamerafahrt", "camera control", "bewegung steuern"],
                ["jarvis_wan_fun_control_camera_ultra.json", "jarvis_wan_fun_control_ultra.json", "jarvis_wan_t2v_best.json"],
            ),
            (
                "Ovi Audio-Video",
                ["ovi", "audio video", "audio-video", "sound im video", "musik video", "gespraech mit audio", "gespräch mit audio"],
                ["jarvis_wan_ovi_audio_ultra.json", "jarvis_wan_infinitetalk_single_ultra.json", "jarvis_wan_talking_avatar_best.json"],
            ),
            (
                "Sprechender Mensch/LipSync",
                ["sprechender mensch", "sprechenden menschen", "spricht", "redet", "lippen", "lipsync", "lip sync", "mundbewegung", "dialog", "avatar"],
                ["jarvis_wan_infinitetalk_multi_ultra.json", "jarvis_wan_infinitetalk_single_ultra.json", "jarvis_wan_talking_avatar_best.json"],
            ),
            (
                "Bild zu Video/Animation",
                ["bild zu video", "image to video", "i2v", "foto zu video", "photo to video", "wananimate", "animate", "figur animieren", "referenzbild"],
                ["jarvis_wananimate_ultra.json", "jarvis_wanmove_i2v_ultra.json", "jarvis_wan_i2v_low_ultra.json", "jarvis_wan_t2v_best.json"],
            ),
            (
                "TikTok/Anime/Short",
                ["tiktok", "shorts", "reel", "anime", "cinematic", "normales video", "video"],
                ["jarvis_wan_t2v_best.json"],
            ),
        ]

        for label, keywords, names in rules:
            if any(key in low for key in keywords):
                selected = self._first_workflow(workflows, names)
                if selected:
                    missing = [name for name in names if name.lower() not in workflows]
                    note = f"{label}: {selected.name}"
                    if missing and selected.name.lower() != names[0].lower():
                        note += f" (Ultra-Workflow fehlt noch: {names[0]})"
                    return selected, note
                fallback = next(iter(workflows.values()), None)
                if fallback:
                    return fallback, f"{label}: Spezial-Workflow fehlt noch, nutze {fallback.name}"
                return None, f"{label}: kein queuebarer Workflow installiert"

        fallback_name = "jarvis_wan_t2v_best.json"
        fallback = workflows.get(fallback_name) or next(iter(workflows.values()), None)
        if fallback:
            return fallback, f"Standard-Video: {fallback.name}"
        return None, "kein queuebarer Workflow installiert"

    def _first_workflow(self, workflows: dict, names):
        for name in names:
            path = workflows.get(name.lower())
            if path:
                return path
        return None

    def _model_status_summary(self) -> str:
        workflows = {p.name for p in self._queueable_workflow_files()}
        workflow_checks = [
            ("T2V", "jarvis_wan_t2v_best.json"),
            ("Talking", "jarvis_wan_talking_avatar_best.json"),
            ("Ovi", "jarvis_wan_ovi_audio_ultra.json"),
            ("InfiniteTalk", "jarvis_wan_infinitetalk_multi_ultra.json"),
            ("SteadyDancer", "jarvis_wan_steadydancer_pose_ultra.json"),
            ("Control Camera", "jarvis_wan_fun_control_camera_ultra.json"),
            ("Upscale", "jarvis_wan_flashvsr_upscale_ultra.json"),
        ]
        ready = [label for label, name in workflow_checks if name in workflows]
        missing = [label for label, name in workflow_checks if name not in workflows]

        models_root = Path(BASE_DIR) / "external" / "ComfyUI" / "models"
        model_checks = [
            ("Ovi Video", "diffusion_models/WanVideo/Ovi/Wan2_2_Ovi_Video_fp8_e4m3fn_scaled_KJ.safetensors"),
            ("Ovi Audio", "diffusion_models/WanVideo/Ovi/Wan2_2_Ovi_Audio_fp8_e4m3fn_scaled_KJ.safetensors"),
            ("InfiniteTalk Single", "diffusion_models/WanVideo/InfiniteTalk/Wan2_1-InfiniteTalk-Single_fp8_e4m3fn_scaled_KJ.safetensors"),
            ("InfiniteTalk Multi", "diffusion_models/WanVideo/InfiniteTalk/Wan2_1-InfiniteTalk-Multi_fp8_e4m3fn_scaled_KJ.safetensors"),
            ("SteadyDancer", "diffusion_models/WanVideo/SteadyDancer/Wan21_SteadyDancer_fp8_e4m3fn_scaled_KJ.safetensors"),
            ("WanMove", "diffusion_models/WanVideo/WanMove/Wan21-WanMove_fp8_scaled_e4m3fn_KJ.safetensors"),
            ("WanAnimate", "diffusion_models/WanVideo/2_2/Wan2_2-Animate-14B_fp8_e4m3fn_scaled_KJ.safetensors"),
            ("Fun Control Camera", "diffusion_models/WanVideo/2_2/Fun/Wan2_2-Fun-Control-Camera-A14B-HIGH_fp8_e4m3fn_scaled_KJ.safetensors"),
            ("Wan 2.2 I2V LOW", "diffusion_models/WanVideo/2_2/Wan2_2-I2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors"),
            ("Lightning I2V", "loras/WanVideo/Wan22-Lightning/Wan2.2-Lightning_I2V-A14B-4steps-lora_HIGH_fp16.safetensors"),
            ("Lightning T2V", "loras/WanVideo/Wan22-Lightning/Wan2.2-Lightning_T2V-A14B-4steps-lora_HIGH_fp16.safetensors"),
            ("FlashVSR Main", "diffusion_models/WanVideo/FlashVSR/Wan2_1-T2V-1_3B_FlashVSR_fp32.safetensors"),
            ("FlashVSR LQ", "diffusion_models/WanVideo/FlashVSR/Wan2_1_FlashVSR_LQ_proj_model_bf16.safetensors"),
            ("FlashVSR TC", "diffusion_models/WanVideo/FlashVSR/Wan2_1_FlashVSR_TCDecoder_fp32.safetensors"),
        ]
        model_ready = []
        model_missing = []
        for label, rel in model_checks:
            target = models_root / Path(rel)
            if target.exists():
                model_ready.append(label)
            else:
                model_missing.append(label)

        install_state = "Download: frei"
        install_lock = Path(BASE_DIR) / "data" / "install_real_video_models.lock"
        if install_lock.exists():
            try:
                details = install_lock.read_text(encoding="utf-8", errors="replace").strip().replace("\n", ", ")
            except Exception:
                details = "aktiv"
            install_state = f"Download laeuft: {details}"
        return (
            "Modelle/Workflows: "
            + f"Workflows bereit={', '.join(ready) if ready else 'keine'}; "
            + f"Workflow fehlt={', '.join(missing) if missing else 'nichts'}; "
            + f"Ultra-Modelle bereit={len(model_ready)}/{len(model_checks)}; "
            + f"Modell fehlt={', '.join(model_missing[:8]) if model_missing else 'nichts'}; "
            + install_state
        )

    def _storage_status_summary(self) -> str:
        hf_home = Path(os.environ.get("HF_HOME", str((Path(BASE_DIR) / "data" / "huggingface_cache").resolve())))
        e_cache = str(hf_home).lower().startswith("e:")
        ollama_models = os.environ.get("OLLAMA_MODELS", "")
        c_hf = Path.home() / ".cache" / "huggingface"
        parts = [
            f"HF_HOME={hf_home}",
            f"HF auf E={'ja' if e_cache else 'nein'}",
        ]
        if ollama_models:
            parts.append(f"OLLAMA_MODELS={ollama_models}")
        if c_hf.exists():
            parts.append("Hinweis: C-HuggingFace-Cache existiert noch")
        return "Speicher: " + "; ".join(parts)

    def _vram_status_summary(self) -> str:
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.used,memory.total,utilization.gpu", "--format=csv,noheader,nounits"],
                capture_output=True,
                text=True,
                timeout=8,
            )
            text = (result.stdout or result.stderr or "").strip()
            if result.returncode != 0 or not text:
                return "VRAM: nicht pruefbar"
            first = text.splitlines()[0]
            parts = [p.strip() for p in first.split(",")]
            if len(parts) >= 4:
                name, used, total, util = parts[:4]
                try:
                    free = max(0, int(float(total)) - int(float(used)))
                    return f"VRAM: {name}, benutzt {used}/{total} MB, frei {free} MB, GPU {util}%"
                except Exception:
                    pass
            return "VRAM: " + first
        except Exception as e:
            return f"VRAM: nicht pruefbar ({e})"

    def _free_vram_for_video(self, settings: dict) -> str:
        if not self.unload_ollama_for_video:
            return "aus"
        if not shutil.which("ollama"):
            return "Ollama nicht gefunden, nichts entladen"
        stopped = []
        try:
            env = os.environ.copy()
            env.setdefault("OLLAMA_MODELS", r"E:\.ollama\models")
            ps = subprocess.run(["ollama", "ps"], capture_output=True, text=True, timeout=12, env=env)
            lines = (ps.stdout or ps.stderr or "").splitlines()
            active = []
            for line in lines[1:]:
                parts = line.split()
                if parts:
                    name = parts[0].strip()
                    if name and any(key in name.lower() for key in ["qwen", "coder", "llama", "mistral", "gemma"]):
                        active.append(name)
            for name in dict.fromkeys(active):
                try:
                    subprocess.run(["ollama", "stop", name], capture_output=True, text=True, timeout=30, env=env)
                    stopped.append(name)
                except Exception:
                    pass
            if stopped:
                return "Ollama fuer Video entladen: " + ", ".join(stopped) + "; " + self._vram_status_summary()
            return "Kein aktives Ollama-Modell blockiert VRAM; " + self._vram_status_summary()
        except Exception as e:
            return f"VRAM-Manager konnte Ollama nicht pruefen: {e}; {self._vram_status_summary()}"

    def _workflow_preflight_report(self, workflow: Path | None, settings: dict) -> str:
        if not workflow:
            return "Workflow-Preflight: kein Workflow ausgewaehlt"
        if not workflow.exists():
            return f"Workflow-Preflight: Datei fehlt: {workflow}"
        try:
            data = json.loads(workflow.read_text(encoding="utf-8", errors="replace"))
            payload = self._workflow_to_api_prompt(data)
        except Exception as e:
            return f"Workflow-Preflight: JSON/Workflow nicht lesbar: {e}"
        if not isinstance(payload, dict) or not payload:
            return f"Workflow-Preflight: {workflow.name} ist nicht queuebar"

        classes = []
        for node in payload.values():
            if isinstance(node, dict):
                class_type = str(node.get("class_type") or "")
                if class_type:
                    classes.append(class_type)
        has_video_output = any(
            key in c.lower()
            for c in classes
            for key in ["videocombine", "savevideo", "videooutput", "vhs"]
        )
        missing_nodes = self._missing_comfyui_nodes(classes)
        warnings = []
        if not has_video_output:
            warnings.append("kein klarer Video-Output-Node erkannt")
        if missing_nodes:
            warnings.append("fehlende Nodes: " + ", ".join(missing_nodes[:10]))

        if warnings:
            return f"Workflow-Preflight: WARNUNG {workflow.name}: " + "; ".join(warnings)
        return f"Workflow-Preflight: OK {workflow.name}; Nodes={len(classes)}; Video-Output=OK"

    def _missing_comfyui_nodes(self, class_types) -> list:
        try:
            r = requests.get(f"{COMFYUI_URL}/object_info", timeout=8)
            if not r.ok:
                return []
            available = set((r.json() or {}).keys())
            return sorted({c for c in class_types if c and c not in available})
        except Exception:
            return []

    def _render_watchdog_status(self, project: Path | None, render: dict, queue_data: dict, history_state: str) -> str:
        if not self.render_watchdog or not project or not render:
            return ""
        queue = self._comfyui_queue_status(queue_data)
        if "laeuft" in queue.lower() or "wartet" in queue.lower():
            return ""
        prompt_id = render.get("prompt_id") or ""
        elapsed_line, _ = self._render_timing_lines(project, render, None)
        if queue_data.get("_error"):
            return (
                "Render-Waechter: ComfyUI ist nicht erreichbar.\n"
                f"Fortschritt: {self._progress_bar(None)}\n"
                f"{elapsed_line}\n"
                f"Prompt-ID: {prompt_id or 'unbekannt'}\n"
                f"Projekt: {project}\n"
                "Starte ComfyUI neu und sage danach: Jarvis, KI Video Fortschritt"
            )
        if history_state == "success":
            return (
                "Render-Waechter: ComfyUI hat den Auftrag beendet, aber Jarvis findet keine Video-Datei.\n"
                f"Fortschritt: {self._progress_bar(100)}\n"
                f"{elapsed_line}\n"
                f"Prompt-ID: {prompt_id or 'unbekannt'}\n"
                f"Projekt: {project}\n"
                "Wahrscheinlich speichert der Workflow keinen MP4/WebM-Output oder in einen anderen ComfyUI-Ordner."
            )
        if history_state == "error":
            return (
                "Render-Waechter: ComfyUI meldet Fehler beim Videoauftrag.\n"
                f"Fortschritt: {self._progress_bar(0)}\n"
                f"{elapsed_line}\n"
                f"Prompt-ID: {prompt_id or 'unbekannt'}\n"
                f"Projekt: {project}\n"
                "Jarvis startet keinen zweiten fehlerhaften Render, bis der Workflow/Node-Fehler behoben ist."
            )
        retry = self._retry_stalled_render(project, render)
        if retry:
            return retry
        return (
            "Render-Waechter: Kein aktiver Render und noch kein Video-Output.\n"
            f"Fortschritt: {self._progress_bar(0)}\n"
            f"{elapsed_line}\n"
            f"Prompt-ID: {prompt_id or 'unbekannt'}\n"
            f"Projekt: {project}\n"
            "Das bedeutet: der ComfyUI-Auftrag wurde nicht gestartet, ist verschwunden oder hat keinen Output geschrieben."
        )

    def _retry_stalled_render(self, project: Path, render: dict) -> str:
        if not self.auto_retry_render:
            return ""
        retries = int(render.get("retry_count") or 0)
        if retries >= self.max_render_retries:
            return ""
        payload_file = project / "queued_payload.json"
        if not payload_file.exists():
            return ""
        try:
            payload = json.loads(payload_file.read_text(encoding="utf-8", errors="replace"))
            if not isinstance(payload, dict) or not isinstance(payload.get("prompt"), dict):
                return ""
            r = requests.post(f"{COMFYUI_URL}/prompt", json=payload, timeout=30)
            if not r.ok:
                return f"Render-Waechter: Auto-Neustart fehlgeschlagen: HTTP {r.status_code} {r.text[:300]}"
            data = r.json() if r.text else {}
            prompt_id = str(data.get("prompt_id") or render.get("prompt_id") or "")
            render.update(
                {
                    "state": "requeued",
                    "prompt_id": prompt_id,
                    "retry_count": retries + 1,
                    "queued_at": time.time(),
                    "queued_at_text": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "watchdog": "Auto-Retry nach leerer Queue ohne Video-Output",
                }
            )
            self._render_status_path(project).write_text(json.dumps(render, ensure_ascii=False, indent=2), encoding="utf-8")
            return (
                "Render-Waechter: Queue war leer ohne Video. Ich habe den Render einmal neu gestartet.\n"
                f"Fortschritt: {self._progress_bar(None)}\n"
                f"Prompt-ID: {prompt_id or 'unbekannt'}\n"
                f"Projekt: {project}"
            )
        except Exception as e:
            return f"Render-Waechter: Auto-Neustart fehlgeschlagen: {e}"

    def _number_from_text(self, text: str, pattern: str, default: int) -> int:
        match = re.search(pattern, text)
        if not match:
            return default
        try:
            return int(match.group(1))
        except Exception:
            return default

    def _speech_text(self, prompt: str) -> str:
        quoted = re.findall(r'"([^"]{2,260})"|\'([^\']{2,260})\'|„([^“]{2,260})“', prompt or "")
        for group in quoted:
            value = next((part for part in group if part), "").strip()
            if value:
                return value
        low = (prompt or "").lower()
        marker_match = re.search(r"(sagt|spricht|dialog|gespraech|gespräch|voice|sprecher)\s*[:=,-]?\s*(.+)", prompt or "", flags=re.I)
        if marker_match and len(marker_match.group(2).strip()) > 2:
            return marker_match.group(2).strip()[:700]
        cleaned = re.sub(r"\b(2k|mit sound|mit ton|mit sprache|ki video|erstelle|generiere)\b", "", prompt or "", flags=re.I)
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" .,:;-")
        if not cleaned:
            cleaned = "ein futuristisches Jarvis Video"
        if "ohne sprache" in low or "keine sprache" in low:
            return ""
        return f"Jarvis praesentiert: {cleaned}."

    def _sound_design(self, prompt: str) -> str:
        low = (prompt or "").lower()
        if any(word in low for word in ["stadt", "city", "strasse", "straße"]):
            return "cinematic city ambience, distant traffic, subtle sci-fi pulses, deep bass hit"
        if any(word in low for word in ["kampf", "action", "explosion"]):
            return "action impacts, deep risers, metallic hits, cinematic bass, fast pulses"
        if any(word in low for word in ["weltraum", "space", "raumschiff"]):
            return "deep space ambience, engine hum, subtle radio texture, cinematic low drone"
        return "futuristic ambient hum, soft digital pulses, cinematic bass, clean Jarvis interface sounds"

    def _create_audio_assets(self, folder: Path, settings: dict) -> str:
        if not settings.get("audio_enabled"):
            return "Audio deaktiviert."
        results = []
        ambient = folder / "ambient_sound.wav"
        try:
            self._create_ambient_wav(ambient, settings["seconds"])
            results.append(f"Sound: {ambient.name}")
        except Exception as e:
            results.append(f"Sound Fehler: {e}")

        if settings.get("speech_enabled") and settings.get("speech_text"):
            speech = folder / "speech_voice.wav"
            if self._create_speech_wav(settings["speech_text"], speech, settings["voice"]):
                results.append(f"Sprache: {speech.name}")
            else:
                results.append("Sprache: speech_de.txt erstellt, WAV konnte nicht automatisch erzeugt werden")
        else:
            results.append("Sprache: aus")
        return "; ".join(results)

    def _create_ambient_wav(self, path: Path, seconds: int) -> None:
        sample_rate = 44100
        total = max(1, int(seconds * sample_rate))
        with wave.open(str(path), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(sample_rate)
            frames = bytearray()
            for n in range(total):
                t = n / sample_rate
                pulse = 1.0 if (n // max(1, sample_rate // 2)) % 2 == 0 else 0.35
                sample = (
                    math.sin(2 * math.pi * 72 * t) * 0.12
                    + math.sin(2 * math.pi * 144 * t) * 0.05
                    + math.sin(2 * math.pi * 420 * t) * 0.015 * pulse
                )
                frames += struct.pack("<h", int(max(-1.0, min(1.0, sample)) * 32767))
            wav.writeframes(frames)

    def _create_speech_wav(self, text: str, out_path: Path, voice_name: str) -> bool:
        text = (text or "").strip()
        if not text:
            return False
        script = r'''
$ErrorActionPreference = 'Stop'
$out = $env:JARVIS_VIDEO_TTS_OUT
$text = $env:JARVIS_VIDEO_TTS_TEXT
$voiceName = $env:JARVIS_VIDEO_TTS_VOICE
$fallbackRegex = $env:JARVIS_VIDEO_TTS_FALLBACK_REGEX
Add-Type -AssemblyName System.Runtime.WindowsRuntime
[Windows.Media.SpeechSynthesis.SpeechSynthesizer, Windows.Media.SpeechSynthesis, ContentType=WindowsRuntime] | Out-Null
[Windows.Media.SpeechSynthesis.SpeechSynthesisStream, Windows.Media.SpeechSynthesis, ContentType=WindowsRuntime] | Out-Null
$synth = [Windows.Media.SpeechSynthesis.SpeechSynthesizer]::new()
$voice = [Windows.Media.SpeechSynthesis.SpeechSynthesizer]::AllVoices | Where-Object { $_.DisplayName -eq $voiceName } | Select-Object -First 1
if([string]::IsNullOrWhiteSpace($fallbackRegex)){ $fallbackRegex = 'Michael|Stefan|David|male|Mann' }
if($null -eq $voice){ $voice = [Windows.Media.SpeechSynthesis.SpeechSynthesizer]::AllVoices | Where-Object { $_.DisplayName -match $fallbackRegex } | Select-Object -First 1 }
if($null -ne $voice){ $synth.Voice = $voice }
$op = $synth.SynthesizeTextToStreamAsync($text)
$method = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.IsGenericMethodDefinition -and $_.GetParameters().Count -eq 1 } | Select-Object -First 1
$task = $method.MakeGenericMethod([Windows.Media.SpeechSynthesis.SpeechSynthesisStream]).Invoke($null, @($op))
$stream = $task.GetAwaiter().GetResult()
$inStream = [System.IO.WindowsRuntimeStreamExtensions]::AsStreamForRead($stream)
$file = [System.IO.File]::Create($out)
try {
  $inStream.CopyTo($file)
} finally {
  $file.Close()
  $inStream.Close()
  $stream.Dispose()
  $synth.Dispose()
}
'''
        env = os.environ.copy()
        env["JARVIS_VIDEO_TTS_TEXT"] = text[:1500]
        env["JARVIS_VIDEO_TTS_OUT"] = str(out_path)
        env["JARVIS_VIDEO_TTS_VOICE"] = voice_name or "Microsoft Michael"
        voice_low = self._plain_lower(voice_name or "")
        if any(word in voice_low for word in ["katja", "hedda", "female", "frau", "weiblich"]):
            env["JARVIS_VIDEO_TTS_FALLBACK_REGEX"] = "Katja|Hedda|female|Frau|weiblich|Zira|Jenny"
        else:
            env["JARVIS_VIDEO_TTS_FALLBACK_REGEX"] = "Michael|Stefan|David|male|Mann"
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
                env=env,
                capture_output=True,
                text=True,
                timeout=90,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            return result.returncode == 0 and out_path.exists() and out_path.stat().st_size > 1000
        except Exception:
            return False

    def _create_fallback_motion_video(self, folder: Path, prompt: str, negative: str, settings: dict) -> str:
        folder = folder.resolve()
        folder.mkdir(parents=True, exist_ok=True)
        ffmpeg = self._ffmpeg_path()
        if not ffmpeg:
            return "Fallback-Video: ffmpeg fehlt, 4K+Audio kann nicht automatisch erstellt werden."
        if not self._ensure_image_api(wait_seconds=90):
            return "Fallback-Video: Bild-KI nicht erreichbar, kein automatisches Keyframe-Video erstellt."

        keyframe = (folder / "keyframe.png").resolve()
        motion_video = (folder / "motion_base.mp4").resolve()
        final_video = (folder / "final_4k_audio.mp4").resolve()
        if not self._create_keyframe_image(prompt, negative, settings, keyframe):
            return "Fallback-Video: Keyframe-Bild konnte nicht erstellt werden."

        frames = max(1, int(settings["seconds"] * settings["fps"]))
        vf = (
            f"scale={settings['target_width']}:{settings['target_height']}:force_original_aspect_ratio=increase,"
            f"crop={settings['target_width']}:{settings['target_height']},"
            f"zoompan=z='min(zoom+0.0015,1.08)':"
            f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
            f"d={frames}:s={settings['target_width']}x{settings['target_height']}:fps={settings['fps']},"
            "format=yuv420p"
        )
        cmd = [
            ffmpeg,
            "-y",
            "-loop",
            "1",
            "-i",
            str(keyframe),
            "-t",
            str(settings["seconds"]),
            "-vf",
            vf,
            "-c:v",
            "libx264",
            "-preset",
            "slow",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            str(motion_video),
        ]
        try:
            result = subprocess.run(cmd, cwd=str(folder), capture_output=True, text=True, timeout=1800)
            if result.returncode != 0:
                return f"Fallback-Video: Bewegungsvideo fehlgeschlagen: {self._short_error(result.stderr)}"
            post = subprocess.run(
                [sys.executable, str((folder / "video_postprocess.py").resolve()), str(motion_video)],
                cwd=str(folder),
                capture_output=True,
                text=True,
                timeout=1800,
            )
            if post.returncode != 0:
                return f"Fallback-Video: Audio/4K-Finalisierung fehlgeschlagen: {self._short_error((post.stdout or '') + (post.stderr or ''))}"
            if final_video.exists():
                self._open_file(final_video)
                self._open_folder(folder)
                return f"Fallback-Video automatisch fertig: {final_video}\n{self._final_video_check(final_video)}"
            return "Fallback-Video: Prozess lief, aber final_4k_audio.mp4 wurde nicht gefunden."
        except Exception as e:
            return f"Fallback-Video: fehlgeschlagen: {e}"

    def _ensure_image_api(self, wait_seconds: int = 90) -> bool:
        if self._image_api_ok():
            return True
        bat = Path(BASE_DIR) / "start_image_generator.bat"
        if bat.exists():
            try:
                subprocess.Popen(
                    ["cmd.exe", "/c", "start", "Jarvis Bild KI", "/min", str(bat)],
                    cwd=str(BASE_DIR),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except Exception:
                pass
        deadline = time.time() + max(1, wait_seconds)
        while time.time() < deadline:
            if self._image_api_ok():
                return True
            time.sleep(3)
        return False

    def _image_api_ok(self) -> bool:
        try:
            r = requests.get(f"{IMAGE_API_URL}/sdapi/v1/options", timeout=5)
            return bool(r.ok)
        except Exception:
            return False

    def _create_keyframe_image(self, prompt: str, negative: str, settings: dict, out_path: Path) -> bool:
        out_path = out_path.resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "prompt": prompt + ", single cinematic video keyframe, no text, no watermark",
            "negative_prompt": negative,
            "steps": max(24, min(int(IMAGE_STEPS), 36)),
            "cfg_scale": IMAGE_CFG_SCALE,
            "width": settings["base_width"],
            "height": settings["base_height"],
            "sampler_name": IMAGE_SAMPLER,
            "batch_size": 1,
            "n_iter": 1,
            "send_images": True,
            "save_images": False,
        }
        try:
            r = requests.post(f"{IMAGE_API_URL}/sdapi/v1/txt2img", json=payload, timeout=900)
            r.raise_for_status()
            images = r.json().get("images", [])
            if not images:
                return False
            img = images[0]
            if "," in img:
                img = img.split(",", 1)[1]
            out_path.write_bytes(base64.b64decode(img))
            return out_path.exists() and out_path.stat().st_size > 1000
        except Exception:
            return False

    def _write_postprocess_tools(self, folder: Path, settings: dict) -> None:
        script = folder / "video_postprocess.py"
        script.write_text(
            f'''import json
import shutil
import subprocess
import sys
from pathlib import Path

VIDEO_SUFFIXES = {{".mp4", ".mov", ".mkv", ".webm", ".avi"}}
ROOT = Path(__file__).resolve().parent
SETTINGS = json.loads((ROOT / "video_settings.json").read_text(encoding="utf-8"))

def find_video():
    if len(sys.argv) > 1:
        p = Path(sys.argv[1]).expanduser()
        if p.exists():
            return p
    for p in sorted(ROOT.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
        if p.suffix.lower() in VIDEO_SUFFIXES and not p.name.startswith("final_"):
            return p
    comfy = Path(r"{str((Path(BASE_DIR) / 'external' / 'ComfyUI' / 'output').resolve())}")
    if comfy.exists():
        vids = [p for p in comfy.rglob("*") if p.is_file() and p.suffix.lower() in VIDEO_SUFFIXES]
        if vids:
            return sorted(vids, key=lambda x: x.stat().st_mtime, reverse=True)[0]
    return None

def main():
    ffmpeg = SETTINGS.get("ffmpeg") or shutil.which("ffmpeg")
    if not ffmpeg:
        print("FFMPEG_FEHLT: Installiere ffmpeg, dann make_2k_with_audio.bat erneut starten.")
        return 2
    video = find_video()
    if not video:
        print("VIDEO_FEHLT: Lege das ComfyUI-Video in diesen Ordner oder uebergib den Pfad als Argument.")
        return 3
    try:
        if ROOT not in video.resolve().parents and video.resolve() != ROOT:
            copied = ROOT / ("comfyui_output_" + video.name)
            if copied.exists():
                copied = ROOT / ("comfyui_output_" + str(int(__import__("time").time())) + "_" + video.name)
            shutil.copy2(video, copied)
            (ROOT / "source_video.txt").write_text(str(video), encoding="utf-8")
            video = copied
            print("Quelle kopiert:", video)
    except Exception as e:
        print("Quelle konnte nicht kopiert werden:", e)
    out = ROOT / "final_4k_audio.mp4"
    target_w = int(SETTINGS.get("target_width", 3840))
    target_h = int(SETTINGS.get("target_height", 2160))
    fps = int(SETTINGS.get("fps", 16))
    speech = ROOT / "speech_voice.wav"
    if not speech.exists():
        speech = ROOT / "speech_michael.wav"
    ambient = ROOT / "ambient_sound.wav"
    inputs = ["-i", str(video)]
    filter_parts = [f"[0:v]scale={{target_w}}:{{target_h}}:flags=lanczos,fps={{fps}}[v]"]
    maps = ["-map", "[v]"]
    if speech.exists() and ambient.exists():
        inputs += ["-i", str(speech), "-i", str(ambient)]
        filter_parts.append("[1:a]volume=1.0[a1];[2:a]volume=0.20[a2];[a1][a2]amix=inputs=2:duration=longest[a]")
        maps += ["-map", "[a]"]
    elif speech.exists():
        inputs += ["-i", str(speech)]
        maps += ["-map", "1:a"]
    elif ambient.exists():
        inputs += ["-i", str(ambient)]
        maps += ["-map", "1:a"]
    cmd = [
        ffmpeg, "-y", *inputs,
        "-filter_complex", ";".join(filter_parts),
        *maps,
        "-c:v", "libx264", "-preset", "slow", "-crf", "18",
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
        "-shortest", str(out),
    ]
    print("Starte 4K+Audio:", " ".join(cmd))
    result = subprocess.run(cmd)
    if result.returncode != 0:
        return result.returncode
    print("FERTIG:", out)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
''',
            encoding="utf-8",
        )
        bat = folder / "make_4k_with_audio.bat"
        bat.write_text(
            f'''@echo off
cd /d "%~dp0"
echo Jarvis erstellt 4K-Video mit Audio...
"{sys.executable}" "%~dp0video_postprocess.py" %*
pause
''',
            encoding="utf-8",
        )
        legacy_bat = folder / "make_2k_with_audio.bat"
        legacy_bat.write_text(
            '''@echo off
call "%~dp0make_4k_with_audio.bat" %*
''',
            encoding="utf-8",
        )

    def _ensure_comfyui(self, wait_seconds: int = 90):
        if self._comfyui_ok():
            return True, ""
        if self.auto_start:
            bat = Path(BASE_DIR) / "start_comfyui.bat"
            if bat.exists():
                try:
                    subprocess.Popen(
                        ["cmd.exe", "/c", "start", "Jarvis ComfyUI", "/min", str(bat)],
                        cwd=str(BASE_DIR),
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                except Exception:
                    pass
        deadline = time.time() + max(1, wait_seconds)
        while time.time() < deadline:
            if self._comfyui_ok():
                return True, ""
            time.sleep(3)
        return False, "ComfyUI nicht erreichbar. Starte zuerst start_comfyui.bat oder install_video_ai.bat."

    def _comfyui_ok(self) -> bool:
        try:
            r = requests.get(f"{COMFYUI_URL}/system_stats", timeout=5)
            return bool(r.ok)
        except Exception:
            return False

    def _copy_templates(self, folder: Path) -> None:
        src_dir = Path(BASE_DIR) / "comfyui_video_workflows"
        dst_dir = folder / "workflows"
        dst_dir.mkdir(parents=True, exist_ok=True)
        if not src_dir.exists():
            return
        for src in src_dir.glob("*.json"):
            try:
                shutil.copy2(src, dst_dir / src.name)
            except Exception:
                pass

    def _queue_if_possible(self, folder: Path, prompt: str, negative: str, settings: dict) -> str:
        workflows = self._queue_workflow_candidates(folder, settings)
        if not workflows:
            return (
                "ComfyUI ist offen, aber es wurde noch kein echter queuebarer Video-Workflow gefunden.\n"
                "Jarvis hat 4K+Audio-Paket vorbereitet. Starte INSTALL_KI_VIDEO_TIKTOK_ALLES.bat, damit echte Wan/FantasyTalking-Workflows installiert werden."
            )
        errors = []
        for workflow in workflows:
            result = self._queue_single_workflow(folder, workflow, prompt, negative, settings)
            if result.startswith("ComfyUI-Workflow gequeued"):
                return result
            errors.append(result)
        return "ComfyUI Queue fehlgeschlagen:\n" + "\n".join(errors[:4])

    def _queue_single_workflow(self, folder: Path, workflow: Path, prompt: str, negative: str, settings: dict) -> str:
        try:
            data = json.loads(workflow.read_text(encoding="utf-8", errors="replace"))
            payload = self._workflow_to_api_prompt(data)
            if not isinstance(payload, dict):
                return f"Workflow nicht queuebar: {workflow.name}"
            self._inject_prompts(payload, prompt, negative)
            self._inject_video_settings(payload, settings)
            queue_payload = {"prompt": payload}
            (folder / "queued_payload.json").write_text(json.dumps(queue_payload, ensure_ascii=False, indent=2), encoding="utf-8")
            r = requests.post(f"{COMFYUI_URL}/prompt", json=queue_payload, timeout=30)
            if r.ok:
                prompt_id = ""
                try:
                    prompt_id = str((r.json() or {}).get("prompt_id") or "")
                except Exception:
                    pass
                self._write_render_status(folder, prompt_id, workflow.name, settings)
                return f"ComfyUI-Workflow gequeued: {workflow.name}\nAntwort: {r.text[:500]}"
            return f"ComfyUI Queue fehlgeschlagen: HTTP {r.status_code} {r.text[:500]}"
        except Exception as e:
            return f"ComfyUI Queue fehlgeschlagen: {e}"

    def _queue_workflow_candidates(self, folder: Path, settings=None):
        workflow_dirs = [Path(BASE_DIR) / "comfyui_video_workflows", folder / "workflows"]
        names = []
        if settings and settings.get("workflow_name"):
            names.append(settings["workflow_name"])
        names.extend([
            "jarvis_wan_t2v_best.json",
            "jarvis_wananimate_ultra.json",
            "jarvis_wan_talking_avatar_best.json",
        ])
        candidates = []
        seen = set()
        for name in names:
            if not name:
                continue
            for workflow_dir in workflow_dirs:
                path = workflow_dir / name
                key = str(path).lower()
                if path.exists() and key not in seen:
                    candidates.append(path)
                    seen.add(key)
        return candidates

    def _find_queueable_workflow(self, folder: Path, settings=None):
        workflow_dirs = [Path(BASE_DIR) / "comfyui_video_workflows", folder / "workflows"]
        preferred = []
        if settings and settings.get("workflow_name"):
            preferred.append(settings["workflow_name"])
        preferred += [
            "jarvis_wan_talking_avatar_best.json" if settings and settings.get("speech_enabled") else "",
            "jarvis_wan_t2v_best.json",
        ]
        candidates = []
        seen = set()
        for name in preferred:
            if not name:
                continue
            for workflow_dir in workflow_dirs:
                path = workflow_dir / name
                if path.exists() and str(path).lower() not in seen:
                    candidates.append(path)
                    seen.add(str(path).lower())
        for workflow_dir in workflow_dirs:
            if workflow_dir.exists():
                for path in workflow_dir.glob("*.json"):
                    if str(path).lower() not in seen:
                        candidates.append(path)
                        seen.add(str(path).lower())
        for path in candidates:
            try:
                data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
            except Exception:
                continue
            if isinstance(data, dict) and ("prompt" in data or "nodes" in data or any(str(k).isdigit() for k in data.keys())):
                if data.get("type") == "template":
                    continue
                return path
        return None

    def _workflow_to_api_prompt(self, data):
        if isinstance(data, dict) and isinstance(data.get("prompt"), dict):
            return self._sanitize_api_prompt(data["prompt"])
        if isinstance(data, dict) and any(str(k).isdigit() for k in data.keys()):
            return self._sanitize_api_prompt(data)
        if isinstance(data, dict) and isinstance(data.get("nodes"), list):
            return self._sanitize_api_prompt(self._convert_ui_workflow_to_api(data))
        return None

    def _sanitize_api_prompt(self, prompt):
        if not isinstance(prompt, dict):
            return prompt
        non_exec = {
            "note",
            "markdownnote",
            "noteplus",
            "reroute",
            "primitive",
        }
        removed = {
            str(node_id)
            for node_id, node in prompt.items()
            if isinstance(node, dict) and str(node.get("class_type", "")).lower() in non_exec
        }
        if not removed:
            return prompt
        cleaned = {}
        for node_id, node in prompt.items():
            if str(node_id) in removed or not isinstance(node, dict):
                continue
            inputs = node.get("inputs")
            if isinstance(inputs, dict):
                node = dict(node)
                clean_inputs = {}
                for key, value in inputs.items():
                    if isinstance(value, list) and value and str(value[0]) in removed:
                        continue
                    clean_inputs[key] = value
                node["inputs"] = clean_inputs
            cleaned[str(node_id)] = node
        return cleaned

    def _convert_ui_workflow_to_api(self, workflow: dict):
        object_info = self._comfyui_object_info()
        if not object_info:
            return None
        node_by_id = {
            str(node.get("id")): node
            for node in workflow.get("nodes", [])
            if isinstance(node, dict) and node.get("id") is not None
        }
        links = {}
        for link in workflow.get("links", []):
            if isinstance(link, list) and len(link) >= 4:
                links[link[0]] = [str(link[1]), int(link[2])]

        set_sources = self._ui_set_sources(node_by_id, links)
        primitive_values = self._ui_primitive_values(node_by_id)

        prompt = {}
        for node in workflow.get("nodes", []):
            if not isinstance(node, dict):
                continue
            node_id = str(node.get("id"))
            class_type = node.get("type")
            if not node_id or not class_type:
                continue
            if str(class_type).lower() in {"note", "markdownnote", "noteplus", "reroute", "primitive", "primitivenode", "setnode", "getnode"}:
                continue
            api_inputs = {}
            for item in node.get("inputs", []):
                if not isinstance(item, dict):
                    continue
                name = item.get("name")
                link_id = item.get("link")
                if name and link_id in links:
                    resolved = self._resolve_ui_link(links[link_id], node_by_id, set_sources, primitive_values)
                    if resolved is not None:
                        api_inputs[name] = resolved

            widget_names = self._widget_input_names(object_info.get(class_type, {}), api_inputs)
            widget_values = node.get("widgets_values") or []
            for name, value in zip(widget_names, widget_values):
                if name not in api_inputs:
                    api_inputs[name] = value

            prompt[node_id] = {"class_type": class_type, "inputs": api_inputs}
        return prompt if prompt else None

    def _ui_set_sources(self, node_by_id: dict, links: dict):
        sources = {}
        for node_id, node in node_by_id.items():
            if str(node.get("type", "")).lower() != "setnode":
                continue
            name = self._ui_named_node_key(node, "Set_")
            if not name:
                continue
            for item in node.get("inputs", []) or []:
                if not isinstance(item, dict):
                    continue
                link_id = item.get("link")
                if link_id in links:
                    sources[name] = links[link_id]
                    break
        return sources

    def _ui_primitive_values(self, node_by_id: dict):
        values = {}
        for node_id, node in node_by_id.items():
            if str(node.get("type", "")).lower() != "primitivenode":
                continue
            widgets = node.get("widgets_values") or []
            if widgets:
                values[node_id] = widgets[0]
        return values

    def _ui_named_node_key(self, node: dict, prefix: str = ""):
        props = node.get("properties") if isinstance(node.get("properties"), dict) else {}
        name = props.get("previousName") or node.get("title") or ""
        name = str(name)
        if prefix and name.lower().startswith(prefix.lower()):
            name = name[len(prefix):]
        return name.strip()

    def _resolve_ui_link(self, ref, node_by_id: dict, set_sources: dict, primitive_values: dict):
        if not isinstance(ref, list) or not ref:
            return ref
        source_id = str(ref[0])
        source_node = node_by_id.get(source_id)
        if not source_node:
            return ref
        source_type = str(source_node.get("type", "")).lower()
        if source_type == "getnode":
            key = self._ui_named_node_key(source_node, "Get_")
            source = set_sources.get(key)
            if source:
                return self._resolve_ui_link(source, node_by_id, set_sources, primitive_values)
            return None
        if source_type == "primitivenode":
            return primitive_values.get(source_id)
        if source_type in {"note", "markdownnote", "noteplus", "reroute", "primitive", "setnode"}:
            return None
        return ref

    def _comfyui_object_info(self):
        try:
            r = requests.get(f"{COMFYUI_URL}/object_info", timeout=20)
            if r.ok:
                return r.json()
        except Exception:
            return None
        return None

    def _widget_input_names(self, info: dict, linked_inputs: dict):
        result = []
        input_info = info.get("input") if isinstance(info, dict) else None
        if not isinstance(input_info, dict):
            return result
        for section in ("required", "optional"):
            fields = input_info.get(section)
            if not isinstance(fields, dict):
                continue
            for name, spec in fields.items():
                if name in linked_inputs:
                    continue
                if self._is_widget_spec(spec):
                    result.append(name)
        return result

    def _is_widget_spec(self, spec) -> bool:
        if not isinstance(spec, (list, tuple)) or not spec:
            return False
        kind = spec[0]
        if isinstance(kind, str):
            return kind.upper() not in {
                "IMAGE",
                "LATENT",
                "MODEL",
                "CLIP",
                "VAE",
                "CONDITIONING",
                "AUDIO",
                "MASK",
                "WANVIDEOMODEL",
                "WANVAE",
                "WANTEXTENCODER",
                "WAV2VECMODEL",
                "FANTASYTALKINGMODEL",
            }
        return True

    def _inject_prompts(self, workflow: dict, prompt: str, negative: str) -> None:
        for node in workflow.values():
            if not isinstance(node, dict):
                continue
            inputs = node.get("inputs")
            if not isinstance(inputs, dict):
                continue
            for key, value in list(inputs.items()):
                low_key = str(key).lower()
                low_value = str(value).lower()
                if "negative" in low_key or "negative" in low_value:
                    if isinstance(value, str):
                        inputs[key] = negative
                elif "prompt" in low_key or "text" in low_key or "positive" in low_key:
                    if isinstance(value, str):
                        inputs[key] = prompt

    def _inject_video_settings(self, workflow: dict, settings: dict) -> None:
        for node in workflow.values():
            if not isinstance(node, dict):
                continue
            inputs = node.get("inputs")
            if not isinstance(inputs, dict):
                continue
            for key in list(inputs.keys()):
                low = str(key).lower()
                if low in {"width", "w"} or low.endswith("_width"):
                    if isinstance(inputs[key], int):
                        inputs[key] = settings["base_width"]
                elif low in {"height", "h"} or low.endswith("_height"):
                    if isinstance(inputs[key], int):
                        inputs[key] = settings["base_height"]
                elif low in {"fps", "frame_rate"}:
                    if isinstance(inputs[key], int):
                        inputs[key] = settings["fps"]
                elif low in {"frames", "num_frames", "frame_count", "length"}:
                    if isinstance(inputs[key], int):
                        inputs[key] = settings["frames"]
            self._normalize_video_node_inputs(node, settings)

    def _normalize_video_node_inputs(self, node: dict, settings: dict) -> None:
        inputs = node.get("inputs")
        if not isinstance(inputs, dict):
            return
        class_type = str(node.get("class_type", ""))
        if class_type == "VHS_VideoCombine":
            inputs["frame_rate"] = int(settings.get("fps", 16))
            inputs["loop_count"] = 0
            inputs["format"] = "video/h264-mp4"
            inputs["filename_prefix"] = "jarvis_video"
            inputs["pingpong"] = False
            inputs["save_output"] = True
            inputs.pop("meta_batch", None)
        elif class_type == "ImageResizeKJv2":
            inputs["width"] = int(settings.get("base_width", 576))
            inputs["height"] = int(settings.get("base_height", 1024))
            inputs["keep_proportion"] = "resize"
            inputs["crop_position"] = "center"
            inputs["divisible_by"] = 16
            inputs["device"] = "gpu"
            inputs["upscale_method"] = "lanczos"
        elif class_type in {"WanVideoImageToVideoEncode", "WanVideoFunCameraEmbeds"}:
            if "start_latent_strength" in inputs:
                inputs["start_latent_strength"] = 1.0
            if "end_latent_strength" in inputs:
                inputs["end_latent_strength"] = 1.0
            if "noise_aug_strength" in inputs:
                inputs["noise_aug_strength"] = 0.03
            if "strength" in inputs:
                inputs["strength"] = 1.0
            if "start_percent" in inputs:
                inputs["start_percent"] = 0.0
            if "end_percent" in inputs:
                inputs["end_percent"] = 1.0
        elif class_type == "WanVideoSampler":
            for optional_key in [
                "feta_args",
                "context_options",
                "cache_args",
                "flowedit_args",
                "slg_args",
                "loop_args",
                "experimental_args",
                "sigmas",
                "freeinit_args",
            ]:
                if optional_key in inputs and not isinstance(inputs.get(optional_key), list):
                    inputs.pop(optional_key, None)
            if "steps" in inputs:
                inputs["steps"] = max(4, min(int(settings.get("frames", 96)) // 16, 8))
            if "shift" in inputs:
                inputs["shift"] = 5.0
            if "scheduler" in inputs:
                inputs["scheduler"] = "dpm++_sde"
            if "cfg" in inputs:
                inputs["cfg"] = 6.0
            if "seed" in inputs:
                inputs["seed"] = int(time.time()) % 2147483647
            if "force_offload" in inputs:
                inputs["force_offload"] = True
            if "riflex_freq_index" in inputs:
                inputs["riflex_freq_index"] = 0
            if "rope_function" in inputs:
                inputs["rope_function"] = "comfy"
            if "denoise_strength" in inputs:
                inputs["denoise_strength"] = 1.0
        elif class_type in {"WanVideoLoraSelect", "WanVideoLoraSelectMulti"}:
            if inputs.get("blocks") is False or inputs.get("blocks") is None:
                inputs["blocks"] = {"selected_blocks": {}}
            inputs["merge_loras"] = False
            if "low_mem_load" in inputs:
                inputs["low_mem_load"] = False

    def _project_from_text(self, path_text: str):
        path = self._clean_path(path_text)
        if path and path.exists():
            if path.is_file():
                return path.parent
            return path
        root = self._output_dir()
        if not root.exists():
            return None
        projects = [p for p in root.iterdir() if p.is_dir() and p.name.startswith("video_")]
        return sorted(projects, key=lambda p: p.stat().st_mtime, reverse=True)[0] if projects else None

    def _output_dir(self) -> Path:
        path = Path(VIDEO_OUTPUT_DIR).expanduser()
        if not path.is_absolute():
            path = Path(BASE_DIR) / path
        return path.resolve()

    def _short_error(self, text: str) -> str:
        lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
        useful = []
        for line in lines:
            low = line.lower()
            if any(key in low for key in ["error", "fehler", "failed", "no such file", "cannot", "invalid"]):
                useful.append(line)
        if not useful:
            useful = lines[-4:]
        return " | ".join(useful[-4:])[:700] if useful else "Unbekannter Fehler"

    def _clean_path(self, text: str):
        value = (text or "").strip().strip('"').strip("'")
        if not value:
            return None
        try:
            path = Path(value).expanduser()
            if not path.is_absolute():
                path = Path(BASE_DIR) / path
            return path
        except Exception:
            return None

    def _is_relative_to(self, path: Path, root: Path) -> bool:
        try:
            path.resolve().relative_to(root.resolve())
            return True
        except Exception:
            return False

    def _ffmpeg_path(self) -> str:
        env_path = os.getenv("FFMPEG_PATH", "").strip().strip('"')
        if env_path and Path(env_path).exists():
            return env_path
        found = shutil.which("ffmpeg")
        if found:
            return found
        winget_root = Path.home() / "AppData" / "Local" / "Microsoft" / "WinGet" / "Packages"
        if winget_root.exists():
            for candidate in winget_root.rglob("ffmpeg.exe"):
                return str(candidate)
            for candidate in Path(BASE_DIR).rglob("ffmpeg.exe"):
                return str(candidate)
        return ""

    def _ffprobe_path(self) -> str:
        ffmpeg = self._ffmpeg_path()
        if ffmpeg:
            candidate = Path(ffmpeg).with_name("ffprobe.exe")
            if candidate.exists():
                return str(candidate)
        found = shutil.which("ffprobe")
        return found or ""

    def _final_video_check(self, video: Path) -> str:
        if not video.exists():
            return "Finaltest: Datei fehlt."
        size_mb = round(video.stat().st_size / (1024 * 1024), 1)
        ffprobe = self._ffprobe_path()
        if not ffprobe:
            return f"Finaltest: Datei vorhanden ({size_mb} MB), ffprobe fehlt fuer Dauer/Audio."
        try:
            result = subprocess.run(
                [
                    ffprobe,
                    "-v",
                    "error",
                    "-print_format",
                    "json",
                    "-show_format",
                    "-show_streams",
                    str(video),
                ],
                capture_output=True,
                text=True,
                timeout=45,
            )
            if result.returncode != 0:
                return f"Finaltest: ffprobe Fehler: {self._short_error(result.stderr)}"
            data = json.loads(result.stdout or "{}")
            streams = data.get("streams", [])
            has_video = any(s.get("codec_type") == "video" for s in streams)
            has_audio = any(s.get("codec_type") == "audio" for s in streams)
            duration = float(data.get("format", {}).get("duration") or 0)
            return (
                f"Finaltest: ok; Dauer {duration:.1f}s; "
                f"Video={'ja' if has_video else 'nein'}; Audio={'ja' if has_audio else 'nein'}; Groesse {size_mb} MB"
            )
        except Exception as e:
            return f"Finaltest: Datei vorhanden ({size_mb} MB), Pruefung fehlgeschlagen: {e}"

    def _open_file(self, path: Path) -> None:
        try:
            webbrowser.open(path.resolve().as_uri(), new=2)
        except Exception:
            pass

    def _open_folder(self, path: Path) -> None:
        try:
            if hasattr(os, "startfile"):
                os.startfile(str(path.resolve()))
            else:
                webbrowser.open(path.resolve().as_uri(), new=2)
        except Exception:
            pass
