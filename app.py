
import atexit, json, threading, sys, os, time, queue, os, mimetypes, webbrowser, re, shutil, uuid, socket, subprocess
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

PORT = 8765
ROOT = Path(__file__).resolve().parent
WEB_DIR = ROOT / "jarvis_3d_webgl"
CHAT_HISTORY_FILE = ROOT / "data" / "chat_history.jsonl"
CHAT_SESSIONS_FILE = ROOT / "data" / "chat_sessions.json"
DROP_STATE_FILE = ROOT / "data" / "last_drop_paths.json"
INSTANCE_LOCK_FILE = ROOT / "data" / "jarvis_app.lock"
CODING_DASHBOARD_FILE = ROOT / "data" / "coding_dashboard.json"
CHAT_RETENTION_SECONDS = 7 * 24 * 60 * 60
CHAT_HISTORY_FOREVER = True
WORK_TIMEOUT_SECONDS = int(os.environ.get("JARVIS_WORK_TIMEOUT", "900") or "900")
WORK_STUCK_WARN_SECONDS = int(os.environ.get("JARVIS_WORK_STUCK_WARN", "180") or "180")
JARVIS_AUTO_MODE = os.environ.get("JARVIS_AUTO_MODE", "1") == "1"
JARVIS_AUTO_START_SERVICES = os.environ.get("JARVIS_AUTO_START_SERVICES", "1") == "1"
JARVIS_AUTO_OPEN_DASHBOARDS = os.environ.get("JARVIS_AUTO_OPEN_DASHBOARDS", "1") == "1"
STARTUP_USER_NAME = os.environ.get("JARVIS_USER_NAME", "Barkin").strip() or "Barkin"
CLEANUP_DIRS = [
    ROOT / "logs",
    ROOT / "data" / "chat_logs",
    ROOT / "data" / "work_logs",
    ROOT / "data" / "temp",
    ROOT / "data" / "screenshots",
    ROOT / "sandbox_runs",
    ROOT / "__pycache__",
]

VENV_DIR = ROOT / ".venv"
VENV_PYTHON = VENV_DIR / "Scripts" / "python.exe"
try:
    RUNNING_IN_PROJECT_VENV = Path(sys.prefix).resolve() == VENV_DIR.resolve()
except Exception:
    RUNNING_IN_PROJECT_VENV = False

if (
    not getattr(sys, "frozen", False)
    and Path(sys.argv[0]).name.lower() == "app.py"
    and VENV_PYTHON.exists()
    and not RUNNING_IN_PROJECT_VENV
    and Path(sys.executable).resolve() != VENV_PYTHON.resolve()
    and os.environ.get("JARVIS_NO_VENV_REEXEC") != "1"
):
    os.execv(str(VENV_PYTHON), [str(VENV_PYTHON), *sys.argv])

os.chdir(ROOT)

# Starkes Coding-Modell als Hauptmodell erzwingen, ohne automatischen Fallback.
FORCED_OLLAMA_MODEL = "qwen3-coder-next:latest"
for key in [
    "OLLAMA_MODEL",
    "OLLAMA_TEXT_MODEL",
    "OLLAMA_CODE_MODEL",
    "OLLAMA_MAX_CODE_MODEL",
    "OLLAMA_AGENT_CODE_MODEL",
    "OLLAMA_STRONG_CODE_MODEL",
    "OLLAMA_BEAST_CODE_MODEL",
    "JARVIS_MODEL",
    "MODEL_NAME",
    "LLM_MODEL",
]:
    os.environ[key] = FORCED_OLLAMA_MODEL
os.environ.setdefault("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
os.environ.setdefault("JARVIS_DIRECT_COMMAND_MODE", "1")


try:
    from brain import JarvisBrain
except Exception:
    JarvisBrain = None

try:
    from voice import listen_once, speak_text
except Exception:
    listen_once = None
    speak_text = None

brain = JarvisBrain() if JarvisBrain else None
events = queue.Queue()
wake_running = False
speech_lock = threading.Lock()
work_lock = threading.Lock()
work_history = []
last_work_window_open = 0
work_window_opened = False
auto_open_times = {}
drop_lock = threading.Lock()
last_drop_paths = []
chat_history_lock = threading.Lock()
chat_session_lock = threading.Lock()
active_chat_id = None
task_lock = threading.Lock()
task_state_lock = threading.Lock()
task_state = {"running": False, "command": "", "label": "", "started": 0.0}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}
DOC_EXTS = {".pdf", ".docx"}
CODE_FILE_EXTS = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".html", ".css", ".json", ".md", ".txt",
    ".cpp", ".h", ".hpp", ".c", ".cs", ".java", ".go", ".rs", ".php", ".sql",
    ".bat", ".ps1", ".yml", ".yaml", ".toml", ".ini", ".env",
}
WAKE_WORDS = (
    "jarvis", "javis", "jarwis", "jarwies", "jarbis", "jar ist", "jar was",
    "ja was", "jervis", "djarvis", "garvis", "arvis", "tscharvis", "tschervis",
    "charvis", "schervis", "service", "servus", "charles",
)
VOICE_ACTION_WORDS = (
    "codier", "codiere", "codieren", "codiern", "coderien", "coderiern", "programmier",
    "programmiere", "code", "coding", "skript", "script", "python", "javascript",
    "webseite", "website", "erstelle", "mach", "baue", "projekt", "app", "spiel",
    "oeffne", "öffne", "starte", "klick", "klicke", "schreib", "suche", "status",
    "modell", "terminal", "befehl", "bildschirm", "screenshot", "analysiere",
    "bearbeite", "verbesser", "reparier", "fix", "indexiere", "weiter", "daran",
    "ordner", "datei", "foto", "bild", "codex", "codey", "fuege", "füge",
    "einfügen", "einfuegen", "einbauen",
)

def spoken_has_wake(text: str) -> bool:
    low = (text or "").lower()
    return any(word in low for word in WAKE_WORDS)

def spoken_has_action(text: str) -> bool:
    low = (text or "").lower()
    return any(word in low for word in VOICE_ACTION_WORDS)

def push_event(kind, text):
    try:
        item = {"kind": kind, "text": str(text), "time": time.time()}
        events.put(item)
        with work_lock:
            work_history.append(item)
            if len(work_history) > 500:
                del work_history[:-500]
    except Exception:
        pass

def push_phase(phase, label, detail=""):
    push_event("phase", f"{phase}|{label}|{detail}")

def begin_task(command: str) -> bool:
    if not task_lock.acquire(False):
        return False
    phase, label = command_phase(command)
    with task_state_lock:
        task_state.update({
            "running": True,
            "command": clean_chat_text(command, 260),
            "label": label,
            "started": time.time(),
        })
    return True

def end_task():
    with task_state_lock:
        task_state.update({"running": False, "command": "", "label": "", "started": 0.0})
    try:
        task_lock.release()
    except RuntimeError:
        pass

def task_busy_message() -> str:
    with task_state_lock:
        command = task_state.get("command", "")
        label = task_state.get("label", "JARVIS ARBEITET")
        started = float(task_state.get("started") or 0)
    elapsed = int(time.time() - started) if started else 0
    detail = f" an: {command}" if command else ""
    return f"{label}: Ich arbeite noch{detail}. Laufzeit: {elapsed}s. Ich starte keinen zweiten Auftrag parallel."

def jarvis_already_running() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", PORT), timeout=0.5):
            return True
    except OSError:
        return False

def process_is_running(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}"],
                text=True,
                capture_output=True,
                timeout=3,
                encoding="utf-8",
                errors="ignore",
            )
            return str(pid) in (result.stdout or "")
        except Exception:
            return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False

def acquire_instance_lock() -> bool:
    try:
        INSTANCE_LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
        if INSTANCE_LOCK_FILE.exists():
            try:
                old_pid = int(INSTANCE_LOCK_FILE.read_text(encoding="utf-8", errors="ignore").strip() or "0")
            except Exception:
                old_pid = 0
            if process_is_running(old_pid):
                return False
            try:
                INSTANCE_LOCK_FILE.unlink()
            except Exception:
                return False
        fd = os.open(str(INSTANCE_LOCK_FILE), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(str(os.getpid()))
        atexit.register(release_instance_lock)
        return True
    except FileExistsError:
        return False
    except Exception:
        return True

def release_instance_lock() -> None:
    try:
        if INSTANCE_LOCK_FILE.exists():
            current = INSTANCE_LOCK_FILE.read_text(encoding="utf-8", errors="ignore").strip()
            if current == str(os.getpid()):
                INSTANCE_LOCK_FILE.unlink()
    except Exception:
        pass

def ollama_has_active_model() -> bool:
    try:
        result = subprocess.run(
            ["ollama", "ps"],
            text=True,
            capture_output=True,
            timeout=5,
            encoding="utf-8",
            errors="replace",
        )
        lines = [line.strip() for line in (result.stdout or "").splitlines() if line.strip()]
        return len(lines) > 1
    except Exception:
        return True

def prune_chat_history(now=None):
    if CHAT_HISTORY_FOREVER:
        return
    now = float(now or time.time())
    cutoff = now - CHAT_RETENTION_SECONDS
    with chat_history_lock:
        try:
            if not CHAT_HISTORY_FILE.exists():
                return
            kept = []
            for line in CHAT_HISTORY_FILE.read_text(encoding="utf-8", errors="ignore").splitlines():
                try:
                    item = json.loads(line)
                except Exception:
                    continue
                if float(item.get("time", 0)) >= cutoff:
                    kept.append(item)
            CHAT_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
            tmp = CHAT_HISTORY_FILE.with_suffix(".tmp")
            tmp.write_text(
                "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in kept),
                encoding="utf-8",
            )
            tmp.replace(CHAT_HISTORY_FILE)
        except Exception as e:
            push_event("system", f"Chat-Verlauf konnte nicht bereinigt werden: {e}")

def cleanup_old_runtime_files(now=None):
    now = float(now or time.time())
    cutoff = now - CHAT_RETENTION_SECONDS
    try:
        root_resolved = ROOT.resolve()
    except Exception:
        root_resolved = ROOT
    deleted = 0
    for cleanup_root in CLEANUP_DIRS:
        try:
            cleanup_root = cleanup_root.resolve()
            if not cleanup_root.exists():
                continue
            if cleanup_root != root_resolved and root_resolved not in cleanup_root.parents:
                continue
            for path in sorted(cleanup_root.rglob("*"), key=lambda p: len(p.parts), reverse=True):
                try:
                    if path == cleanup_root:
                        continue
                    stat = path.stat()
                    if stat.st_mtime >= cutoff:
                        continue
                    if path.is_file() or path.is_symlink():
                        path.unlink()
                        deleted += 1
                    elif path.is_dir():
                        try:
                            next(path.iterdir())
                        except StopIteration:
                            path.rmdir()
                            deleted += 1
                except Exception:
                    pass
        except Exception as e:
            push_event("system", f"7-Tage-Bereinigung konnte {cleanup_root} nicht prüfen: {e}")
    if deleted:
        push_event("system", f"7-Tage-Bereinigung: {deleted} alte Log/Temp-Dateien entfernt.")

def cleanup_retained_data():
    prune_chat_history()
    cleanup_old_runtime_files()

def retention_cleanup_loop():
    while True:
        time.sleep(6 * 60 * 60)
        cleanup_retained_data()

def clean_chat_text(text: str, limit: int = 160) -> str:
    clean = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(clean) > limit:
        return clean[:limit - 3].rstrip() + "..."
    return clean

def new_chat_id() -> str:
    return time.strftime("chat-%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:8]

def load_chat_sessions():
    with chat_session_lock:
        try:
            if CHAT_SESSIONS_FILE.exists():
                data = json.loads(CHAT_SESSIONS_FILE.read_text(encoding="utf-8", errors="ignore") or "{}")
                if isinstance(data, dict):
                    return data
        except Exception:
            pass
    return {"active_chat_id": None, "chats": {}}

def save_chat_sessions(data):
    with chat_session_lock:
        try:
            CHAT_SESSIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
            CHAT_SESSIONS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:
            push_event("system", f"Chat-Sitzungen konnten nicht gespeichert werden: {e}")

def create_chat(title: str = "Neuer Chat") -> dict:
    global active_chat_id
    now = time.time()
    chat_id = new_chat_id()
    data = load_chat_sessions()
    data.setdefault("chats", {})[chat_id] = {
        "id": chat_id,
        "title": clean_chat_text(title, 72) or "Neuer Chat",
        "created": now,
        "updated": now,
    }
    data["active_chat_id"] = chat_id
    active_chat_id = chat_id
    save_chat_sessions(data)
    with drop_lock:
        last_drop_paths[:] = []
    save_drop_paths([])
    push_event("drop", "")
    push_phase("idle", "CHAT OHNE ORDNER", "Kein Arbeitsordner aktiv")
    return data["chats"][chat_id]

def set_active_chat(chat_id: str) -> str:
    global active_chat_id
    chat_id = str(chat_id or "").strip()
    data = load_chat_sessions()
    if chat_id == "legacy":
        data["active_chat_id"] = chat_id
        active_chat_id = chat_id
        save_chat_sessions(data)
        restore_chat_workspace(chat_id)
        return chat_id
    if chat_id and chat_id in data.get("chats", {}):
        data["active_chat_id"] = chat_id
        active_chat_id = chat_id
        save_chat_sessions(data)
        restore_chat_workspace(chat_id)
        return chat_id
    chat = create_chat()
    return chat["id"]

def get_active_chat_id(create_if_missing: bool = True) -> str:
    global active_chat_id
    data = load_chat_sessions()
    if active_chat_id and (active_chat_id == "legacy" or active_chat_id in data.get("chats", {})):
        return active_chat_id
    saved = data.get("active_chat_id")
    if saved and (saved == "legacy" or saved in data.get("chats", {})):
        active_chat_id = saved
        return saved
    if not create_if_missing:
        return ""
    chat = create_chat()
    return chat["id"]

def touch_chat(chat_id: str, text: str):
    if not chat_id or chat_id == "legacy":
        return
    data = load_chat_sessions()
    chats = data.setdefault("chats", {})
    chat = chats.get(chat_id)
    if not chat:
        return
    now = time.time()
    chat["updated"] = now
    title = clean_chat_text(text, 72)
    if title and chat.get("title", "Neuer Chat") in ("Neuer Chat", "Unbenannter Chat"):
        chat["title"] = title
    data["active_chat_id"] = chat_id
    save_chat_sessions(data)

def rename_chat(chat_id: str, title: str) -> dict:
    chat_id = str(chat_id or "").strip()
    if not chat_id:
        chat_id = get_active_chat_id(True)
    title = clean_chat_text(title, 72) or "Unbenannter Chat"
    data = load_chat_sessions()
    now = time.time()
    if chat_id == "legacy":
        data["legacy_title"] = title
        data["active_chat_id"] = chat_id
        save_chat_sessions(data)
        return {"id": chat_id, "title": title, "updated": now}
    chats = data.setdefault("chats", {})
    if chat_id not in chats:
        chats[chat_id] = {
            "id": chat_id,
            "created": now,
            "updated": now,
        }
    chats[chat_id]["title"] = title
    chats[chat_id]["updated"] = now
    data["active_chat_id"] = chat_id
    save_chat_sessions(data)
    return chats[chat_id]

def remove_chat_messages(chat_id: str):
    with chat_history_lock:
        try:
            if not CHAT_HISTORY_FILE.exists():
                return
            kept = []
            for line in CHAT_HISTORY_FILE.read_text(encoding="utf-8", errors="ignore").splitlines():
                try:
                    item = json.loads(line)
                except Exception:
                    continue
                item_chat_id = str(item.get("chat_id") or "legacy")
                if item_chat_id != chat_id:
                    kept.append(item)
            tmp = CHAT_HISTORY_FILE.with_suffix(".tmp")
            tmp.write_text(
                "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in kept),
                encoding="utf-8",
            )
            tmp.replace(CHAT_HISTORY_FILE)
        except Exception as e:
            push_event("system", f"Chat konnte nicht aus Verlauf entfernt werden: {e}")

def delete_chat(chat_id: str) -> dict:
    global active_chat_id
    chat_id = str(chat_id or "").strip()
    if not chat_id:
        chat_id = get_active_chat_id(False)
    if not chat_id:
        return {"deleted": "", "active_chat_id": ""}

    data = load_chat_sessions()
    chats = data.setdefault("chats", {})
    if chat_id == "legacy":
        data.pop("legacy_title", None)
        data.pop("legacy_workspace", None)
    else:
        chats.pop(chat_id, None)
    remove_chat_messages(chat_id)
    data["active_chat_id"] = ""
    active_chat_id = ""
    save_chat_sessions(data)

    remaining = build_chat_threads("")
    next_id = ""
    for chat in remaining:
        if chat["id"] != chat_id:
            next_id = chat["id"]
            break
    if not next_id:
        new_chat = create_chat()
        next_id = new_chat["id"]
        data = load_chat_sessions()
    data["active_chat_id"] = next_id
    active_chat_id = next_id
    save_chat_sessions(data)
    restore_chat_workspace(next_id)
    return {"deleted": chat_id, "active_chat_id": next_id}

def save_chat_message(role: str, text: str, source: str = "text", routed_text: str = "", chat_id: str = ""):
    text = str(text or "").strip()
    if not text:
        return
    now = time.time()
    prune_chat_history(now)
    if chat_id:
        chat_id = set_active_chat(chat_id)
    else:
        chat_id = get_active_chat_id(True)
    item = {
        "time": now,
        "role": str(role),
        "source": str(source),
        "text": text,
        "chat_id": chat_id,
    }
    if routed_text and routed_text != text:
        item["routed_text"] = str(routed_text)
    with chat_history_lock:
        try:
            CHAT_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
            with CHAT_HISTORY_FILE.open("a", encoding="utf-8") as f:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
        except Exception as e:
            push_event("system", f"Chat-Verlauf konnte nicht gespeichert werden: {e}")
    if str(role).lower() == "user":
        touch_chat(chat_id, text)

def read_chat_history():
    prune_chat_history()
    items = []
    with chat_history_lock:
        try:
            if not CHAT_HISTORY_FILE.exists():
                return []
            for idx, line in enumerate(CHAT_HISTORY_FILE.read_text(encoding="utf-8", errors="ignore").splitlines()):
                try:
                    item = json.loads(line)
                except Exception:
                    continue
                item["_id"] = idx
                items.append(item)
        except Exception:
            return []
    return items

def recent_chat_context(chat_id: str, limit: int = 8, max_chars: int = 2600) -> str:
    chat_id = str(chat_id or get_active_chat_id(False) or "legacy")
    items = [item for item in read_chat_history() if str(item.get("chat_id") or "legacy") == chat_id]
    if not items:
        return ""
    parts = []
    for item in items[-limit:]:
        role = "DU" if str(item.get("role", "")).lower() == "user" else "JARVIS"
        text = clean_chat_text(item.get("text", ""), 650)
        routed = clean_chat_text(item.get("routed_text", ""), 650)
        if routed and routed != text:
            text = f"{text}\nRoute: {routed}"
        if text:
            parts.append(f"{role}: {text}")
    context = "\n".join(parts).strip()
    if len(context) > max_chars:
        context = context[-max_chars:]
    return context

def build_chat_threads(search: str = ""):
    query = clean_chat_text(search, 80).lower()
    data = load_chat_sessions()
    active = get_active_chat_id(False) or data.get("active_chat_id")
    threads = {}
    for chat_id, meta in data.get("chats", {}).items():
        workspace_paths = valid_paths(meta.get("workspace_paths", []))
        threads[chat_id] = {
            "id": chat_id,
            "time": float(meta.get("updated") or meta.get("created") or 0),
            "title": clean_chat_text(meta.get("title") or "Neuer Chat", 72),
            "preview": "",
            "messages": [],
            "workspace": summarize_paths(workspace_paths) if workspace_paths else "",
            "active": chat_id == active,
        }

    for item in read_chat_history():
        role = str(item.get("role", "")).lower()
        text = str(item.get("text", "")).strip()
        if not text:
            continue
        chat_id = str(item.get("chat_id") or "legacy")
        message = {
            "role": role or "system",
            "source": str(item.get("source", "")),
            "text": text,
            "time": float(item.get("time", 0) or 0),
        }
        routed = str(item.get("routed_text", "")).strip()
        if routed:
            message["routed_text"] = routed

        if chat_id not in threads:
            workspace_paths = valid_paths(data.get("legacy_workspace", []) if chat_id == "legacy" else data.get("chats", {}).get(chat_id, {}).get("workspace_paths", []))
            threads[chat_id] = {
                "id": chat_id,
                "time": message["time"],
                "title": clean_chat_text(data.get("legacy_title") or "Alter Chat", 72) if chat_id == "legacy" else "Neuer Chat",
                "preview": "",
                "messages": [],
                "workspace": summarize_paths(workspace_paths) if workspace_paths else "",
                "active": chat_id == active,
            }
        thread = threads[chat_id]
        thread["messages"].append(message)
        thread["time"] = max(float(thread.get("time") or 0), message["time"])
        if role == "user" and thread.get("title") in ("Neuer Chat", "Unbenannter Chat"):
            thread["title"] = clean_chat_text(text, 72)
        if role == "assistant":
            thread["preview"] = clean_chat_text(text, 110)

    result = list(threads.values())
    for thread in result:
        messages = thread.get("messages", [])
        if messages and not thread.get("preview"):
            thread["preview"] = clean_chat_text(messages[-1].get("text", ""), 110)
        thread["search_blob"] = " ".join(
            [thread.get("title", ""), thread.get("preview", ""), thread.get("workspace", "")] + [m.get("text", "") for m in messages]
        ).lower()

    result.sort(key=lambda thread: float(thread.get("time", 0)), reverse=True)
    if query:
        result = [thread for thread in result if query in thread.get("search_blob", "")]
    for thread in result:
        thread.pop("search_blob", None)
    return result

def summarize_paths(paths):
    clean = [str(p) for p in paths if str(p).strip()]
    if not clean:
        return "Kein Pfad erkannt"
    first = Path(clean[0])
    kind = "Ordner" if first.is_dir() else "Datei"
    suffix = f" + {len(clean) - 1} weitere" if len(clean) > 1 else ""
    return f"{kind}: {first}{suffix}"

def valid_paths(paths):
    clean = []
    if isinstance(paths, (str, Path)):
        paths = [paths]
    for raw in paths or []:
        try:
            p = Path(str(raw).strip().strip('"')).expanduser()
            if p.exists():
                clean.append(str(p.resolve()))
        except Exception:
            pass
    return clean

def set_chat_workspace(chat_id: str, paths):
    chat_id = str(chat_id or get_active_chat_id(True)).strip()
    clean = valid_paths(paths)
    if not chat_id or not clean:
        return []
    data = load_chat_sessions()
    now = time.time()
    if chat_id == "legacy":
        data["legacy_workspace"] = clean
    else:
        chat = data.setdefault("chats", {}).setdefault(chat_id, {
            "id": chat_id,
            "title": "Neuer Chat",
            "created": now,
            "updated": now,
        })
        chat["workspace_paths"] = clean
        chat["updated"] = now
    data["active_chat_id"] = chat_id
    save_chat_sessions(data)
    return clean

def get_chat_workspace(chat_id: str):
    chat_id = str(chat_id or get_active_chat_id(False)).strip()
    data = load_chat_sessions()
    if chat_id == "legacy":
        return valid_paths(data.get("legacy_workspace", []))
    return valid_paths(data.get("chats", {}).get(chat_id, {}).get("workspace_paths", []))

def restore_chat_workspace(chat_id: str):
    clean = get_chat_workspace(chat_id)
    with drop_lock:
        previous = list(last_drop_paths)
        last_drop_paths[:] = clean
    if previous != clean:
        save_drop_paths(clean)
    if clean and previous != clean:
        summary = summarize_paths(clean)
        push_event("drop", summary)
        push_phase("coding" if Path(clean[0]).is_dir() else "reading", "CHAT ARBEITSORDNER AKTIV", summary)
    elif not clean and previous:
        push_event("drop", "")
        push_phase("idle", "CHAT OHNE ORDNER", "Kein Arbeitsordner aktiv")
    return clean

def save_drop_paths(paths):
    try:
        DROP_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        DROP_STATE_FILE.write_text(json.dumps({"paths": list(paths)}, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        push_event("system", f"Arbeitsordner konnte nicht gespeichert werden: {e}")

def load_drop_paths():
    try:
        if not DROP_STATE_FILE.exists():
            return
        data = json.loads(DROP_STATE_FILE.read_text(encoding="utf-8", errors="ignore") or "{}")
        paths = data.get("paths", [])
        clean = []
        for raw in paths:
            p = Path(str(raw).strip().strip('"')).expanduser()
            if p.exists():
                clean.append(str(p.resolve()))
        if not clean:
            return
        with drop_lock:
            last_drop_paths[:] = clean
        summary = summarize_paths(clean)
        push_event("drop", summary)
        push_phase("coding" if Path(clean[0]).is_dir() else "reading", "ARBEITSBEREICH AKTIV", summary)
    except Exception as e:
        push_event("system", f"Arbeitsordner konnte nicht geladen werden: {e}")

def register_dropped_paths(paths):
    clean = valid_paths(paths)
    if not clean:
        push_event("system", "Drop erkannt, aber kein lesbarer Pfad gefunden.")
        return []
    with drop_lock:
        last_drop_paths[:] = clean
    save_drop_paths(clean)
    set_chat_workspace(get_active_chat_id(True), clean)
    summary = summarize_paths(clean)
    push_event("drop", summary)
    push_phase("coding" if Path(clean[0]).is_dir() else "reading", "ARBEITSBEREICH AKTIV", summary)
    try:
        open_work_window()
    except Exception:
        pass
    push_event("work_reset", f"ARBEITSBEREICH AKTIV|{summary}")
    push_event("work_step", f"0|Drop aktiv: {summary}")
    first = Path(clean[0])
    if first.is_dir():
        speak_status_async("Ordner erhalten. Ich arbeite jetzt in diesem Ordner.")
    else:
        speak_status_async("Datei erhalten.")
    return clean

def current_drop_path():
    with drop_lock:
        if last_drop_paths:
            return Path(last_drop_paths[0])
    workspace = get_chat_workspace(get_active_chat_id(False))
    if workspace:
        with drop_lock:
            last_drop_paths[:] = workspace
        return Path(workspace[0])
    return None

def has_term(text: str, terms) -> bool:
    text_norm = normalize_intent_text(text)
    for term in terms:
        term = normalize_intent_text(term)
        if not term:
            continue
        if " " in term:
            if term in text_norm:
                return True
        elif re.search(rf"(?<!\w){re.escape(term)}(?!\w)", text_norm, flags=re.I):
            return True
    return False

def normalize_intent_text(text: str) -> str:
    text = str(text or "").lower()
    text = (
        text.replace("\u00e4", "ae")
        .replace("\u00f6", "oe")
        .replace("\u00fc", "ue")
        .replace("\u00df", "ss")
    )
    replacements = {
        "ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss",
        "Ã¤": "ae", "Ã¶": "oe", "Ã¼": "ue", "ÃŸ": "ss",
        "ortner": "ordner", "ordent": "ordner",
        "coderinb": "codieren", "coderien": "codieren", "coderiern": "codieren",
        "codiern": "codieren", "codiere": "codieren",
        "kannm": "kann", "kanm": "kann",
        "faehigkeietn": "faehigkeiten", "faehgikeiten": "faehigkeiten",
        "faehigketen": "faehigkeiten", "faeigkeiten": "faehigkeiten",
        "faehgkeiten": "faehigkeiten", "fertigkeiten": "faehigkeiten",
        "moeglichkeietn": "moeglichkeiten", "vorschlaege": "ideen",
        "homge": "homepage", "web seite": "webseite",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    text = re.sub(r"[^a-z0-9_#.+:/\\\-\s?]", " ", text)
    return re.sub(r"\s+", " ", text).strip()

def is_followup_request(text: str) -> bool:
    low = normalize_intent_text(text)
    if not low:
        return False
    words = low.split()
    if re.search(r"\b(nr|nummer|punkt|option|idee)\s*\d+\b", low):
        return True
    if re.search(r"^(mach|nimm|baue|erstelle|setz|setze|implementier)\s+\d+\b", low):
        return True
    followup_starts = (
        "mach das", "mach es", "mach den", "mach die", "mach nr", "mach nummer",
        "nimm das", "nimm nr", "nimm nummer", "das erste", "das zweite",
        "ja mach", "ok mach", "okay mach", "passt mach", "genau das",
        "so machen", "mach weiter", "weiter", "weiter machen",
    )
    if any(low.startswith(start) for start in followup_starts):
        return True
    return len(words) <= 5 and any(word in low for word in ["das", "es", "nr", "nummer", "idee", "weiter"])

def instruction_with_chat_context(instruction: str, chat_id: str) -> str:
    if not is_followup_request(instruction):
        return instruction
    context = recent_chat_context(chat_id)
    if not context:
        return instruction
    push_phase("thinking", "CODEX-MODUS: CHAT-KONTEXT", "Folgeauftrag wird mit bisherigem Chat verstanden")
    return (
        "Vorheriger Chat-Kontext:\n"
        f"{context}\n\n"
        "Aktueller Auftrag:\n"
        f"{instruction}\n\n"
        "Verstehe diesen Auftrag als Folgeauftrag. Wenn eine Nummer, Option oder Idee genannt wird, "
        "leite sie aus dem vorherigen Chat-Kontext ab."
    )

def apply_dropped_context(command: str, chat_id: str = "") -> str:
    target = current_drop_path()
    if target is None:
        return command
    instruction = (command or "").strip()
    if not instruction:
        return command
    instruction = re.sub(r"^\s*(hey\s+)?jarvis[:,]?\s*", "", instruction, flags=re.I).strip()
    low = normalize_intent_text(instruction)
    routed_instruction = instruction_with_chat_context(instruction, chat_id)
    quoted = f'"{target}"'
    edit_words = [
        "bearbeite", "ändere", "ändern", "änder", "aendere", "aendern", "aender", "verbesser", "fix", "reparier",
        "weiter", "weiterentwick", "codier", "codiern", "coderinb", "programmier", "implementier",
        "arbeite", "codex", "codey", "coding", "code ändern", "code aendern", "fuege", "füge", "einfügen",
        "einfuegen", "einbauen", "erstelle", "baue", "schreib", "schreibe",
        "ersetze", "lösche", "loesche", "entferne", "mach rein", "bau ein",
    ]
    analyze_words = [
        "analysiere", "analysier", "prüfe", "pruefe", "review", "check",
        "was ist", "erkläre", "erklaere", "zeig", "zeige", "lies", "schau",
    ]
    question_words = [
        "was kann", "was könnte", "was koennte", "kann man", "können wir",
        "ob man", "ob wir", "kann ich", "kannst du", "geht noch", "was geht",
        "koennen wir", "ideen", "idee", "vorschläge", "vorschlaege",
        "möglichkeiten", "moeglichkeiten", "fähigkeiten", "faehigkeiten",
        "features", "funktion", "funktionen", "was fehlt", "empfiehl",
        "welche", "wie kann", "was soll", "was wäre", "was waere", "plan",
        "planung", "vorschlag", "empfehlung",
    ]
    project_context_words = [
        "ordner", "projekt", "repo", "datei", "code", "app", "ki", "jarvis",
        "fähigkeit", "fähigkeiten", "faehigkeit", "faehigkeiten", "feature",
        "fähigkeietn", "faehigkeietn", "fähgikeiten", "fertigkeiten",
        "features", "funktion", "funktionen", "button", "seite", "webseite",
        "design", "ui", "fenster", "menü", "menu", "modell", "stimme",
        "mikrofon", "fehler", "bug", "screen", "bildschirm", "hologramm",
        "konsole", "arbeitsbereich", "daran", "hier", "diese datei",
        "dieser ordner",
    ]
    chat_starts = [
        "wer ", "was ", "wie ", "warum ", "wieso ", "wann ", "wo ",
        "erzähl", "erzaehl", "erkläre mir", "erklaere mir",
    ]
    continuation_words = [
        "mach weiter", "weiter machen", "weiterarbeiten", "arbeite weiter",
        "weiter codieren", "weiter coden", "mach daran weiter", "daran weiter",
        "projekt weiter", "code weiter", "im ordner weiter",
    ]
    project_question_words = [
        "was kann man noch", "was kann ich noch", "was können wir noch",
        "was koennen wir noch", "was geht noch", "was fehlt noch",
        "was wäre noch", "was waere noch", "noch fähigkeiten",
        "noch faehigkeiten", "fähigkeiten machen", "faehigkeiten machen",
        "fähigkeiten einbauen", "faehigkeiten einbauen", "neue fähigkeiten",
        "neue faehigkeiten", "mehr fähigkeiten", "mehr faehigkeiten",
        "was kann man machen", "was kann ich machen", "was soll ich machen",
        "welche features", "welche funktionen", "ideen für", "ideen fuer",
    ]
    general_chat_words = [
        "wie geht es dir", "wie gehts", "wer bist du", "was bist du",
        "erzaehl mir einen witz", "erzaehl einen witz", "guten morgen",
        "gute nacht", "hallo", "danke", "uhrzeit", "wetter",
    ]
    explicit_project_edit = has_term(low, edit_words)
    has_project_context = has_term(low, project_context_words)
    active_project_test_terms = [
        "cheat", "cheats", "aimbot", "aim assist", "wallhack", "esp",
        "debug", "debug overlay", "debug-overlay", "admin", "admin menue",
        "admin menu", "testmodus", "testtool", "test-tool", "test bot",
        "testbot", "anti-cheat", "anticheat", "dev modus", "dev-modus",
    ]
    security_marker = (target / ".jarvis_security_test_allowed") if target.is_dir() else (target.parent / ".jarvis_security_test_allowed")
    security_enable_terms = [
        "security test modus aktivieren", "sicherheitstest modus aktivieren",
        "security-test modus aktivieren", "pentest modus aktivieren",
        "red team modus aktivieren", "red-team modus aktivieren",
        "angriff testmodus aktivieren", "angriffs testmodus aktivieren",
    ]
    security_disable_terms = [
        "security test modus deaktivieren", "sicherheitstest modus deaktivieren",
        "security-test modus deaktivieren", "pentest modus deaktivieren",
        "red team modus deaktivieren", "red-team modus deaktivieren",
    ]
    security_attack_test_terms = [
        "angreifen", "angriff testen", "angriff simulieren",
        "attacke testen", "attack test", "red team", "red-team",
        "pentest", "penetration test", "security test", "sicherheit testen",
        "exploit test", "exploit-test", "exploit simulation",
        "fuzz test", "fuzzer", "packet test", "paket test",
        "replay test", "rate limit test", "ratelimit test",
        "load test", "stresstest", "bot angriff testen",
    ]
    active_root = target if target.is_dir() else target.parent
    active_root_name = normalize_intent_text(active_root.name)
    game_request_terms = [
        "spiel", "game", "online spiel", "online-game", "testserver",
        "server", "client", "anti-cheat", "anticheat", "cheat", "aimbot",
        "wallhack", "esp", "debug overlay",
    ]
    game_folder_terms = [
        "spiel", "game", "gameserver", "game-server", "onlinegame",
        "online-game", "unity", "godot", "unreal", "phaser",
    ]
    game_project_markers = [
        "project.godot", "package.json", "server.js", "client.js",
        "index.html", "Assets", "ProjectSettings", "Content", "Source",
        "src", "public",
    ]
    folder_looks_like_game = has_term(active_root_name, game_folder_terms)
    if not folder_looks_like_game and has_term(low, game_request_terms):
        try:
            folder_looks_like_game = any((active_root / marker).exists() for marker in game_project_markers)
        except Exception:
            folder_looks_like_game = False
    if has_term(low, security_enable_terms):
        try:
            security_marker.write_text(
                "Jarvis Security-Test-Modus fuer diesen Projektordner aktiviert.\n"
                "Nur fuer eigene/autorisierte Testserver und defensive Pruefungen verwenden.\n",
                encoding="utf-8",
            )
        except Exception:
            pass
        push_phase("coding", "SECURITY-TEST-MODUS AKTIV", str(target))
        return "Security-Test-Modus fuer diesen aktiven Projektordner ist aktiv. Jarvis darf jetzt defensive Angriffs-/Exploit-/Pentest-Tests als lokale Testauftraege fuer dieses Projekt planen und codieren."
    if has_term(low, security_disable_terms):
        try:
            if security_marker.exists():
                security_marker.unlink()
        except Exception:
            pass
        push_phase("idle", "SECURITY-TEST-MODUS AUS", str(target))
        return "Security-Test-Modus fuer diesen Projektordner ist deaktiviert."
    if has_term(low, active_project_test_terms):
        explicit_project_edit = True
        has_project_context = True
    security_test_enabled = security_marker.exists() or folder_looks_like_game
    if security_test_enabled and has_term(low, security_attack_test_terms):
        explicit_project_edit = True
        has_project_context = True
        routed_instruction = (
            "Security-Test-Modus gilt fuer diesen aktiven Spiel-/Projektordner. "
            "Verstehe den Auftrag als defensive Red-Team-/Pentest-/Exploit-Simulation "
            "nur gegen das eigene Spiel, den lokalen Testserver oder autorisierte Testumgebung. "
            "Keine fremden Ziele, keine Credentialdiebstahl-Funktionen, keine Malware, keine heimliche Persistenz. "
            f"Originalauftrag: {routed_instruction}"
        )
    is_followup = is_followup_request(instruction)
    is_continuation = has_term(low, continuation_words)
    is_general_chat = has_term(low, general_chat_words)
    is_project_question = (
        has_term(low, project_question_words)
        or (
            has_term(low, ["was kann", "was man", "kann man", "was koennte", "was noch", "welche"])
            and has_term(low, ["faehigkeit", "faehigkeiten", "feature", "features", "funktion", "funktionen", "einbauen", "machen"])
        )
        or (has_term(low, question_words) and (has_project_context or low.endswith("?")))
        or (has_term(low, analyze_words) and has_project_context)
    )
    is_new_website_request = (
        has_term(low, ["homepage", "webseite", "website", "landing page", "home page", "homge"])
        and has_term(low, ["erstelle", "erzeuge", "generiere", "baue", "mach"])
        and not has_term(low, ["jarvis_3d_webgl", "hologramm", "hologram", "3d", "jarvis ui", "jarvis design", "work.html"])
    )
    is_new_browser_game_request = (
        has_term(low, ["spiel", "spiele", "game", "browsergame", "browser game", "arcade", "runner"])
        and has_term(low, ["erstelle", "erzeuge", "generiere", "baue", "mach", "programmiere", "entwickle"])
        and has_term(low, ["browser", "browsergame", "browser game", "web", "html", "canvas", "javascript", "offline", "arcade", "runner"])
        and not has_term(low, ["jarvis_3d_webgl", "hologramm", "hologram", "3d", "jarvis ui", "jarvis design", "work.html"])
        and not has_term(low, ["gross", "grosse", "grosses", "groß", "große", "großes", "unity", "unreal", "godot", "multiplayer", "open world", "engine", "steam"])
    )
    is_question_like = low.endswith("?") or has_term(low, question_words) or any(low.startswith(x.strip()) for x in chat_starts)
    looks_like_chat = low.endswith("?") or any(low.startswith(x) for x in chat_starts)
    if target.is_dir():
        if is_new_website_request or is_new_browser_game_request:
            label = "JARVIS BAUT SPIEL" if is_new_browser_game_request else "JARVIS BAUT WEBSEITE"
            push_phase("web", label, "Neues Browserprojekt statt aktiven Ordner ueberschreiben")
            return command
        if is_continuation:
            push_phase("coding", "CODEX-MODUS: WEITERARBEITEN", str(target))
            return f"Jarvis, repo ändere {quoted} | Arbeite im vorhandenen Projekt weiter: {routed_instruction}"
        if has_term(low, ["index", "indexiere", "merk", "speicher"]):
            push_phase("reading", "CODEX-MODUS: ORDNER INDEX", str(target))
            return f"Jarvis, rag index {quoted}"
        if is_followup:
            push_phase("coding", "CODEX-MODUS: FOLGEAUFTRAG", str(target))
            return f"Jarvis, repo ändere {quoted} | {routed_instruction}"
        if is_project_question:
            push_phase("reading", "CODEX-MODUS: PROJEKTFRAGE", str(target))
            return f"Jarvis, repo frage {quoted} | {routed_instruction}"
        if explicit_project_edit:
            push_phase("coding", "CODEX-MODUS: PROJEKT ÄNDERN", str(target))
            return f"Jarvis, repo ändere {quoted} | {routed_instruction}"
        if is_question_like and not is_general_chat:
            push_phase("reading", "CODEX-MODUS: PROJEKTFRAGE", str(target))
            return f"Jarvis, repo frage {quoted} | Verstehe diese Frage im Kontext des aktiven Projektordners und antworte konkret: {routed_instruction}"
        if looks_like_chat and not has_project_context:
            return command
        if not has_project_context and not explicit_project_edit:
            return command
        push_phase("coding", "CODEX-MODUS: PROJEKT ÄNDERN", str(target))
        return f"Jarvis, repo ändere {quoted} | {routed_instruction}"
    suffix = target.suffix.lower()
    if suffix == ".pdf":
        return f"Jarvis, lies pdf {quoted}"
    if suffix == ".docx":
        return f"Jarvis, lies word {quoted}"
    if suffix in IMAGE_EXTS:
        if has_term(low, ["upscale", "hochskalier", "4k", "schaerfer", "schÃ¤rfer"]):
            return f"Jarvis, ki bild upscale {quoted}"
        if has_term(low, ["ki bild", "bild erstellen", "bild generieren", "image erstellen", "foto generieren", "mach daraus", "erstelle daraus", "referenz"]):
            return f"Jarvis, ki bild referenz {quoted} | {instruction}"
        return f"Jarvis, analysiere bild {quoted}"
    if suffix in CODE_FILE_EXTS:
        parent = f'"{target.parent}"'
        if is_continuation:
            push_phase("coding", "CODEX-MODUS: DATEI WEITER", str(target))
            return f"Jarvis, repo ändere {parent} | Arbeite an Datei {target.name} weiter: {routed_instruction}"
        if is_followup:
            push_phase("coding", "CODEX-MODUS: DATEI-FOLGEAUFTRAG", str(target))
            return f"Jarvis, repo ändere {parent} | Bearbeite nur die Datei {target.name}: {routed_instruction}"
        if is_project_question:
            push_phase("reading", "CODEX-MODUS: DATEIFRAGE", str(target))
            return f"Jarvis, repo frage {parent} | Frage bezieht sich auf Datei {target.name}: {routed_instruction}"
        if explicit_project_edit:
            push_phase("coding", "CODEX-MODUS: DATEI ÄNDERN", str(target))
            return f"Jarvis, repo ändere {parent} | Bearbeite nur die Datei {target.name}: {routed_instruction}"
        if is_question_like and not is_general_chat:
            push_phase("reading", "CODEX-MODUS: DATEIFRAGE", str(target))
            return f"Jarvis, repo frage {parent} | Frage bezieht sich auf Datei {target.name}: {routed_instruction}"
        if looks_like_chat and not has_project_context:
            return command
        if not has_project_context and not explicit_project_edit:
            return command
        push_phase("coding", "CODEX-MODUS: DATEI ÄNDERN", str(target))
        return f"Jarvis, repo ändere {parent} | Bearbeite nur die Datei {target.name}: {routed_instruction}"
    parent = f'"{target.parent}"'
    if is_project_question:
        push_phase("reading", "CODEX-MODUS: DATEIFRAGE", str(target))
        return f"Jarvis, repo frage {parent} | Frage bezieht sich auf Datei {target.name}: {routed_instruction}"
    if looks_like_chat and not has_project_context:
        return command
    if (has_term(low, question_words) and has_project_context and not has_term(low, edit_words)) or (has_term(low, analyze_words) and has_project_context and not has_term(low, edit_words)):
        return f"Jarvis, repo frage {parent} | Frage bezieht sich auf Datei {target.name}: {routed_instruction}"
    if not has_project_context and not has_term(low, edit_words):
        return command
    return f"Jarvis, repo ändere {parent} | Bearbeite die Datei {target.name}: {routed_instruction}"

def answer_has_error(answer: str) -> bool:
    low = (answer or "").lower()
    if any(x in low for x in [
        "serverfehler",
        "ollama-fehler",
        "repo-agent rollback",
        "repo-agent: kein valides json",
        "build/test-fehler",
        "test-gate: fehler",
        "python-syntax fehler",
        "browser-konsole/pageerror",
        "rollback:",
        "ampel: kritisch",
        "auto-reparatur\nstatus: pruefen",
        "auto-reparatur: laeuft bereits",
        "python-syntax fehler",
        "fehler: ",
        "jarvis-waechter: der auftrag sah nach echter code-aenderung aus",
        "ich habe nichts geaendert",
        "keine datei geaendert",
        "read timed out",
        "fehlgeschlagen",
        "nicht erstellt",
        "nicht erreichbar",
        "konnte nicht",
    ]):
        return True
    return bool(re.search(r"\b(error|exception)\b|fehler:", low))

def speak_status(text: str, final_phase=None):
    if speak_text is None:
        return
    with speech_lock:
        try:
            push_event("speaking", "1")
            push_phase("speaking", "JARVIS SPRICHT", text)
            speak_text(text)
        except Exception as e:
            push_event("system", f"Sprachfehler: {e}")
        finally:
            push_event("speaking", "0")
            if final_phase:
                push_phase(final_phase[0], final_phase[1], final_phase[2] if len(final_phase) > 2 else "")

def speak_status_async(text: str, final_phase=None):
    threading.Thread(target=lambda: speak_status(text, final_phase), daemon=True).start()

def startup_greeting():
    greeting = f"Hallo {STARTUP_USER_NAME}. Jarvis ist online. Was kann ich für dich tun?"
    push_event("system", greeting)
    push_phase("speaking", "JARVIS BEGRÜSST DICH", greeting)
    speak_status_async(greeting, ("listening", "JARVIS HÖRT ZU", "Bereit"))

def spoken_answer_text(answer: str, prefix: str = "") -> str:
    text = str(answer or "").strip()
    if not text:
        return prefix.strip()
    low = text.lower()
    if "py_compile" in low or "ollama_list" in low:
        return f"{prefix} Pruefung fertig. Details stehen am Bildschirm.".strip()
    if "jarvis komplett-check" in low or "status-ampel" in low:
        return f"{prefix} Status geprueft. Die Ampel steht am Bildschirm.".strip()
    if "jarvis zuverlaessigkeits-check" in low or "zuverlässigkeits-check" in low:
        if "ampel: kritisch" in low or "fehler:" in low:
            return f"{prefix} Zuverlaessigkeit geprueft. Es gibt Probleme, Details stehen am Bildschirm.".strip()
        return f"{prefix} Zuverlaessigkeit geprueft. Details stehen am Bildschirm.".strip()
    if "auto-reparatur" in low:
        if "status: pruefen" in low or "fehler:" in low:
            return f"{prefix} Auto-Reparatur fertig, aber es gibt Warnungen. Details stehen am Bildschirm.".strip()
        return f"{prefix} Auto-Reparatur fertig. Details stehen am Bildschirm.".strip()
    if "service-waechter" in low or "service-wächter" in low:
        return f"{prefix} Dienste geprueft. Details stehen am Bildschirm.".strip()
    if "modell-router" in low:
        return f"{prefix} Modell-Router ist geprueft. Details stehen am Bildschirm.".strip()
    if "coding-dashboard geoeffnet" in low or "coding-dashboard geöffnet" in low:
        return f"{prefix} Coding-Dashboard ist offen.".strip()
    if "video-dashboard geoeffnet" in low or "video-dashboard geöffnet" in low:
        return f"{prefix} Video-Dashboard ist offen. Fortschritt steht am Bildschirm.".strip()
    if "ki-video" in low or "comfyui-workflow gequeued" in low or "fortschritt:" in low:
        return f"{prefix} Video-Status aktualisiert. Ladebalken und Details stehen am Bildschirm.".strip()
    if "ki-bild studio" in low or "ki-bild galerie" in low:
        return f"{prefix} Bild-Studio ist bereit. Details stehen am Bildschirm.".strip()
    if "punkt 1 erkannt" in low:
        return f"{prefix} Punkt 1 ist bereit. Details stehen am Bildschirm.".strip()
    if "punkt 2 erkannt" in low:
        return f"{prefix} Punkt 2 ist bereit. Details stehen am Bildschirm.".strip()
    if "repo geaendert" in low or "repo geändert" in low:
        return f"{prefix} Code-Aenderung fertig. Diff und Tests stehen am Bildschirm.".strip()
    text = re.sub(r"```[\s\S]*?```", "Code steht am Bildschirm.", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"https?://\S+", "Link steht am Bildschirm.", text)
    text = re.sub(r"[*_#>\[\]{}|]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    max_chars = 220
    if len(text) > max_chars:
        text = text[:max_chars].rsplit(" ", 1)[0].rstrip(".,;:") + ". Details stehen am Bildschirm."
    return f"{prefix} {text}".strip()

def speak_answer(answer: str, done_text: str, final_phase=None):
    speak_status(spoken_answer_text(answer, done_text), final_phase)

def speak_answer_async(answer: str, done_text: str, final_phase=None):
    threading.Thread(target=lambda: speak_answer(answer, done_text, final_phase), daemon=True).start()

def command_phase(command: str):
    low = command.lower()
    if any(x in low for x in ["ki video", "video generieren", "video erstellen", "mach video", "mache video", "tiktok video", "tanzvideo", "bild zu video", "foto zu video", "render fortschritt", "video ladebalken"]):
        return "video", "JARVIS RENDERT VIDEO"
    if any(x in low for x in ["ki bild", "bild erstellen", "bild generieren", "ai bild", "image erstellen", "foto generieren", "bild upscale", "bild galerie"]):
        return "image", "JARVIS ERSTELLT BILD"
    if any(x in low for x in ["baue", "bau ", "mach ", "erstelle", "erstell", "implementier", "testfunktion", "funktion ein", "feature ein"]):
        return "coding", "JARVIS CODIERT"
    if any(x in low for x in ["repo frage", "projekt frage", "frage repo", "frage projekt"]):
        return "reading", "JARVIS ANALYSIERT PROJEKT"
    if any(x in low for x in ["repo Ã¤ndere", "repo aendere", "repo ändere", "Ã¤ndere repo", "ändere repo", "projekt Ã¤ndern", "projekt aendern"]):
        return "coding", "JARVIS CODIERT"
    if (
        any(x in low for x in ["spiel", "game", "browsergame", "browser game", "arcade", "runner"])
        and any(x in low for x in ["erstelle", "erstell", "mach", "baue", "bau", "programmiere", "programmier", "entwickle"])
        and any(x in low for x in ["browser", "browsergame", "browser game", "web", "html", "canvas", "javascript", "offline", "arcade", "runner"])
        and not any(x in low for x in ["gross", "grosse", "grosses", "groß", "große", "großes", "3d", "unity", "unreal", "godot", "multiplayer", "open world", "engine", "steam"])
    ):
        return "web", "JARVIS BAUT SPIEL"
    if any(x in low for x in ["webseite", "website", "homepage", "home page", "homge", "html", "css", "landing page"]):
        return "web", "JARVIS BAUT WEBSEITE"
    if any(x in low for x in ["repo ändere", "repo aendere", "projekt ändern", "projekt aendern", "bearbeite", "ändere", "aendere", "füge", "fuege", "einfügen", "einfuegen", "einbauen", "programmiere", "programmier", "codier", "codiere", "codieren", "codiern", "coderinb", "coderien", "coderiern", "codex", "codey", "code", "coding", "skript", "script", "python", "javascript", "typescript", "react", "node", "batch", "powershell", "app erstellen", "spiel", "app", "tool", "programm", "entwickle", "software", "bot"]):
        return "coding", "JARVIS CODIERT"
    if any(x in low for x in ["terminal", "cmd", "befehl ausfuehren", "befehl ausführen"]):
        return "terminal", "JARVIS ARBEITET"
    if any(x in low for x in ["lies pdf", "pdf", "word", "docx", "dokument"]):
        return "reading", "JARVIS LIEST"
    return "thinking", "JARVIS DENKT"

WORK_STEPS = {
    "thinking": [
        "Arbeitsfenster geoeffnet",
        "Auftrag wird gelesen",
        "Jarvis entscheidet den naechsten Schritt",
        "Modell wird gefragt",
        "Antwort wird vorbereitet",
    ],
    "coding": [
        "Arbeitsfenster geoeffnet",
        "Auftrag wird gelesen",
        "Internet/Doku-Loesungen werden gesucht",
        "Projektprofil und Fehlerdatenbank werden geladen",
        "Plan wird gebaut",
        "Aider/Codex-Modell wird vorbereitet",
        "Code wird gezielt geaendert",
        "Warte auf Ollama-Antwort",
        "Dateien und Diff werden geprueft",
        "Build/Test/Review wird gestartet",
        "Ergebnis wird im Projektgedaechtnis gespeichert",
    ],
    "web": [
        "Browser-Vorschau wird vorbereitet",
        "Webseiten-Auftrag wird gelesen",
        "Internet/Doku-Loesungen werden gesucht",
        "Layout und Animationen werden geplant",
        "HTML/CSS/JavaScript wird generiert",
        "Warte auf Ollama-Antwort",
        "Dateien werden geschrieben",
        "Browser-Vorschau und Basispruefung laufen",
    ],
    "terminal": [
        "Arbeitsfenster geoeffnet",
        "Auftrag wird gelesen",
        "Befehl wird vorbereitet",
        "Ausfuehrung wird gestartet",
        "Ausgabe wird gelesen",
    ],
    "reading": [
        "Arbeitsfenster geoeffnet",
        "Datei oder Dokument wird geprueft",
        "Inhalt wird gelesen",
        "Zusammenfassung wird vorbereitet",
        "Antwort wird erstellt",
    ],
    "video": [
        "Video-Dashboard wird geoeffnet",
        "ComfyUI und Video-Workflow werden geprueft",
        "Projektordner, Storyboard und Einstellungen werden vorbereitet",
        "Workflow wird in die Queue gestellt",
        "Renderstatus und Ladebalken werden aktualisiert",
        "Fertige Datei wird gesucht und finalisiert",
    ],
    "image": [
        "Bildgenerator wird geprueft",
        "Prompt, Stil und Qualitaet werden vorbereitet",
        "Referenzbild oder Upscale wird erkannt",
        "Bild wird generiert oder verbessert",
        "Ergebnis wird gespeichert und geoeffnet",
    ],
}

def minimize_coding_windows(delay=0.7):
    if os.name != "nt" or os.getenv("JARVIS_MINIMIZE_CODING_WINDOWS", "1") != "1":
        return

    def worker():
        try:
            import ctypes
            time.sleep(delay)
            user32 = ctypes.windll.user32
            SW_MINIMIZE = 6
            EnumWindows = user32.EnumWindows
            EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
            GetWindowTextW = user32.GetWindowTextW
            GetWindowTextLengthW = user32.GetWindowTextLengthW
            IsWindowVisible = user32.IsWindowVisible
            ShowWindow = user32.ShowWindow
            targets = [
                "jarvis arbeitet live",
                "jarvis coding live",
                "jarvis analyse live",
                "roo",
                "roo code",
                "visual studio code",
                "work.html",
            ]

            def callback(hwnd, lparam):
                if not IsWindowVisible(hwnd):
                    return True
                length = GetWindowTextLengthW(hwnd)
                if length <= 0:
                    return True
                buff = ctypes.create_unicode_buffer(length + 1)
                GetWindowTextW(hwnd, buff, length + 1)
                title = buff.value.lower()
                if "jarvis 3d" in title:
                    return True
                if any(t in title for t in targets):
                    try:
                        ShowWindow(hwnd, SW_MINIMIZE)
                    except Exception:
                        pass
                return True

            EnumWindows(EnumWindowsProc(callback), 0)
        except Exception:
            pass

    threading.Thread(target=worker, daemon=True).start()

def open_work_window(force=False, minimized=False):
    global last_work_window_open, work_window_opened
    if work_window_opened and not force:
        if minimized:
            minimize_coding_windows(0.1)
        return
    now = time.time()
    if now - last_work_window_open < 2:
        if minimized:
            minimize_coding_windows(0.1)
        return
    last_work_window_open = now
    try:
        webbrowser.open(f"http://127.0.0.1:{PORT}/work.html", new=2)
        work_window_opened = True
        if minimized:
            minimize_coding_windows()
    except Exception as e:
        push_event("system", f"Arbeitsfenster konnte nicht geoeffnet werden: {e}")

def auto_open_url(name: str, url: str, min_interval: int = 12):
    if not JARVIS_AUTO_MODE or not JARVIS_AUTO_OPEN_DASHBOARDS:
        return
    now = time.time()
    last = auto_open_times.get(name, 0)
    if now - last < min_interval:
        return
    auto_open_times[name] = now
    try:
        webbrowser.open(url, new=2)
        push_event("system", f"Auto-Anzeige geoeffnet: {name}")
    except Exception as e:
        push_event("system", f"Auto-Anzeige konnte nicht geoeffnet werden ({name}): {e}")

def auto_prepare_for_phase(phase: str, command: str):
    if not JARVIS_AUTO_MODE:
        return
    low = (command or "").lower()
    if phase == "coding":
        auto_open_url("Coding-Dashboard", f"http://127.0.0.1:{PORT}/coding_dashboard.html", min_interval=20)
    elif phase == "video" or any(x in low for x in ["ki video", "video", "tiktok", "render", "comfyui"]):
        auto_open_url("Video-Dashboard", f"http://127.0.0.1:{PORT}/video_dashboard.html", min_interval=15)
    elif phase == "image" or any(x in low for x in ["ki bild", "bild erstellen", "bild generieren", "image"]):
        push_event("system", "Auto-Modus: Bildgenerator wird bei Bedarf automatisch gestartet.")

def startup_auto_mode():
    if not JARVIS_AUTO_MODE:
        return
    push_event("system", "Auto-Modus aktiv: Jarvis repariert sichere Probleme automatisch.")
    push_phase("thinking", "AUTO-REPARATUR", "Jarvis prueft und repariert Runtime-Zustand")
    try:
        from skills.auto_repair import AutoRepair
        report = AutoRepair().run(reason="startup", start_services=JARVIS_AUTO_START_SERVICES)
        first_lines = "\n".join(report.splitlines()[:8])
        push_event("system", first_lines)
    except Exception as e:
        push_event("system", f"Auto-Reparatur Fehler: {e}")
    auto_open_url("Coding-Dashboard", f"http://127.0.0.1:{PORT}/coding_dashboard.html", min_interval=60)
    push_phase("idle", "JARVIS BEREIT", "Auto-Reparatur abgeschlossen")

def start_work_progress(phase: str, label: str, command: str):
    auto_prepare_for_phase(phase, command)
    open_work_window(minimized=(phase == "coding"))
    stop_event = threading.Event()
    start_time = time.time()
    steps = WORK_STEPS.get(phase, WORK_STEPS["thinking"])

    def worker():
        push_event("work_reset", f"{label}|{command}")
        index = 0
        warned_no_model = False
        while not stop_event.is_set():
            elapsed = int(time.time() - start_time)
            if elapsed >= WORK_TIMEOUT_SECONDS:
                push_event("work_step", f"{elapsed}|Zeitlimit erreicht. Auftrag laeuft zu lange oder wartet auf Ollama/Aider.")
                push_phase("thinking", "JARVIS WARTET ZU LANGE", "Auftrag kleiner machen oder Jarvis sauber neu starten")
                break
            if (
                not warned_no_model
                and elapsed >= WORK_STUCK_WARN_SECONDS
                and phase in ("coding", "web", "thinking")
                and not ollama_has_active_model()
            ):
                warned_no_model = True
                push_event("work_step", f"{elapsed}|Hinweis: Jarvis arbeitet noch, aber es kam laenger kein neuer Text. Das Modell kann trotzdem im Hintergrund laden oder rechnen.")
            step = steps[index] if index < len(steps) else f"Modell arbeitet weiter ({elapsed}s)"
            push_event("work_step", f"{elapsed}|{step}")
            index += 1
            stop_event.wait(3)

    threading.Thread(target=worker, daemon=True).start()
    return stop_event

def finish_work_progress(stop_event, answer: str):
    if stop_event is None:
        return
    stop_event.set()
    status = "FEHLER" if answer_has_error(answer) else "FERTIG"
    push_event("work_done", f"{status}|{answer}")

def execute_command(command: str, user_text: str = "", source: str = "text", chat_id: str = "", task_started: bool = False):
    chat_id = chat_id or get_active_chat_id(True)
    if not task_started and not begin_task(command):
        answer = task_busy_message()
        save_chat_message("user", user_text or command, source, command, chat_id)
        save_chat_message("assistant", answer, source, chat_id=chat_id)
        push_event("answer", answer)
        speak_answer_async(answer, "Ich bin noch beschäftigt.")
        return answer
    try:
        save_chat_message("user", user_text or command, source, command, chat_id)
        answer = run_brain(command)
        save_chat_message("assistant", answer, source, chat_id=chat_id)
        push_event("answer", answer)
        done_text = "Bin fertig, aber es gab einen Fehler." if answer_has_error(answer) else "Bin fertig."
        push_phase("idle", "JARVIS FERTIG", done_text)
        speak_answer_async(answer, done_text, ("idle", "JARVIS BEREIT", "Warte auf Befehl"))
        return answer
    finally:
        end_task()

def run_brain(command: str) -> str:
    progress = None
    try:
        command = (command or "").strip()
        if not command:
            return "Befehl fehlt."
        if not command.lower().startswith("jarvis"):
            command = "Jarvis, " + command
        if brain is None:
            return "Brain konnte nicht geladen werden. Prüfe brain.py."
        phase, label = command_phase(command)
        push_phase(phase, label, command)
        progress = start_work_progress(phase, label, command)
        if hasattr(brain, "handle"):
            answer = str(brain.handle(command))
            finish_work_progress(progress, answer)
            return answer
        if hasattr(brain, "run"):
            answer = str(brain.run(command))
            finish_work_progress(progress, answer)
            return answer
        if hasattr(brain, "ask"):
            answer = str(brain.ask(command))
            finish_work_progress(progress, answer)
            return answer
        return "Brain hat keine handle/run/ask Methode."
    except Exception as e:
        answer = f"Fehler: {e}"
        finish_work_progress(progress, answer)
        return answer

def wakeword_loop():
    global wake_running
    if wake_running:
        return
    wake_running = True

    if listen_once is None:
        push_event("system", "Sprachmodul nicht geladen. Prüfe voice.py / Vosk.")
        push_phase("idle", "SPRACHMODUL FEHLT", "voice.py oder Vosk nicht geladen")
        return

    push_event("system", "Auto-Zuhören aktiv. Sag einfach was Jarvis machen soll.")
    push_phase("listening", "JARVIS HÖRT ZU", "Sag einfach einen Befehl")

    while True:
        try:
            text = str(listen_once() or "").strip()
            if not text:
                continue

            low = text.lower()
            push_event("heard", text)
            push_phase("listening", "SPRACHE ERKANNT", text)
            heard_text = text
            wake_found = spoken_has_wake(text)
            action_found = spoken_has_action(text)
            if not wake_found and not action_found:
                if len(text.split()) < 2:
                    push_phase("listening", "WARTE AUF BEFEHL", "Sag einfach was Jarvis machen soll")
                    continue
                push_phase("thinking", "BEFEHL ERKANNT", text)

            # Vosk erkennt "Jarvis" oft falsch. Vor dem Brain sauber normieren.
            if not text.strip().lower().startswith("jarvis"):
                text = "Jarvis, " + text
            text = apply_dropped_context(text, get_active_chat_id(False))

            if not begin_task(text):
                answer = task_busy_message()
                save_chat_message("user", heard_text, "voice", text)
                save_chat_message("assistant", answer, "voice")
                push_event("answer", answer)
                speak_answer(answer, "Ich bin noch beschäftigt.")
                push_phase("listening", "JARVIS HÖRT ZU", "Bereit")
                continue

            phase, label = command_phase(text)
            try:
                push_phase(phase, label, text)
                save_chat_message("user", heard_text, "voice", text)
                answer = run_brain(text)
                save_chat_message("assistant", answer, "voice")
                push_event("answer", answer)
                done_text = "Bin fertig, aber es gab einen Fehler." if answer_has_error(answer) else "Bin fertig."
                push_phase("idle", "JARVIS FERTIG", done_text)
                speak_answer(answer, done_text)
                push_phase("listening", "JARVIS HÖRT ZU", "Bereit")
            finally:
                end_task()

        except Exception as e:
            push_event("system", f"Sprachfehler: {e}")
            push_phase("idle", "SPRACHFEHLER", str(e))
            time.sleep(1.5)

class JarvisHandler(BaseHTTPRequestHandler):
    def _send(self, code=200, ctype="text/html; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "content-type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()

    def do_OPTIONS(self):
        self._send(204)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if path in ["/", "/index.html"]:
            self._send(200, "text/html; charset=utf-8")
            self.wfile.write((WEB_DIR / "index.html").read_bytes())
            return

        if path == "/work.html":
            self._send(200, "text/html; charset=utf-8")
            self.wfile.write((WEB_DIR / "work.html").read_bytes())
            return

        if path == "/coding_dashboard.html":
            self._send(200, "text/html; charset=utf-8")
            self.wfile.write((WEB_DIR / "coding_dashboard.html").read_bytes())
            return

        if path == "/video_dashboard.html":
            self._send(200, "text/html; charset=utf-8")
            self.wfile.write((WEB_DIR / "video_dashboard.html").read_bytes())
            return

        if path.startswith("/assets/"):
            rel = path.lstrip("/").replace("/", os.sep)
            asset = (WEB_DIR / rel).resolve()
            if WEB_DIR.resolve() in asset.parents and asset.is_file():
                ctype = mimetypes.guess_type(str(asset))[0] or "application/octet-stream"
                self._send(200, ctype)
                self.wfile.write(asset.read_bytes())
                return

        if path == "/api/events":
            items = []
            try:
                while len(items) < 20:
                    items.append(events.get_nowait())
            except queue.Empty:
                pass
            self._send(200, "application/json; charset=utf-8")
            self.wfile.write(json.dumps({"events": items}, ensure_ascii=False).encode("utf-8"))
            return

        if path == "/api/work_events":
            since = 0.0
            if parsed.query:
                try:
                    query = parsed.query
                    for part in query.split("&"):
                        key, _, value = part.partition("=")
                        if key == "since":
                            since = float(value or "0")
                except Exception:
                    since = 0.0
            with work_lock:
                items = [item for item in work_history if float(item.get("time", 0)) > since][-120:]
            self._send(200, "application/json; charset=utf-8")
            self.wfile.write(json.dumps({"events": items}, ensure_ascii=False).encode("utf-8"))
            return

        if path == "/api/coding_dashboard":
            try:
                if CODING_DASHBOARD_FILE.exists():
                    data = json.loads(CODING_DASHBOARD_FILE.read_text(encoding="utf-8", errors="replace") or "{}")
                else:
                    data = {"state": "idle", "summary": "Noch kein Coding-Auftrag.", "changed_files": []}
            except Exception as e:
                data = {"state": "error", "summary": f"Dashboard nicht lesbar: {e}", "changed_files": []}
            self._send(200, "application/json; charset=utf-8")
            self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))
            return

        if path == "/api/video_progress":
            try:
                from skills.video_ai import VideoAISkill
                text = VideoAISkill().ready_status("")
                low = text.lower()
                percent = None
                match = re.search(r"(\d{1,3})\s*%", text)
                if match:
                    percent = max(0, min(100, int(match.group(1))))
                if "komplett fertig" in low or "fertig gerendert" in low:
                    state = "done"
                    percent = 100
                elif "fehlgeschlagen" in low or "fehler" in low:
                    state = "error"
                elif "rendert noch" in low or "laeuft" in low or "läuft" in low:
                    state = "running"
                elif "wartet" in low or "queue" in low:
                    state = "pending"
                else:
                    state = "idle"
                data = {
                    "state": state,
                    "percent": percent,
                    "text": text,
                    "updated_at": time.time(),
                }
            except Exception as e:
                data = {
                    "state": "error",
                    "percent": None,
                    "text": f"Video-Fortschritt nicht lesbar: {e}",
                    "updated_at": time.time(),
                }
            self._send(200, "application/json; charset=utf-8")
            self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))
            return

        if path == "/api/chats":
            query = parse_qs(parsed.query)
            search = query.get("q", [""])[0]
            chats = build_chat_threads(search)[:80]
            summary = [
                {
                    "id": chat["id"],
                    "time": chat["time"],
                    "title": chat["title"],
                    "preview": chat.get("preview", ""),
                    "workspace": chat.get("workspace", ""),
                    "count": len(chat.get("messages", [])),
                    "active": bool(chat.get("active")),
                }
                for chat in chats
            ]
            self._send(200, "application/json; charset=utf-8")
            self.wfile.write(json.dumps({"chats": summary, "active_chat_id": get_active_chat_id(False)}, ensure_ascii=False).encode("utf-8"))
            return

        if path == "/api/chat_detail":
            query = parse_qs(parsed.query)
            chat_id = query.get("id", [""])[0]
            chat = next((item for item in build_chat_threads("") if item["id"] == chat_id), None)
            self._send(200, "application/json; charset=utf-8")
            self.wfile.write(json.dumps({"chat": chat}, ensure_ascii=False).encode("utf-8"))
            return

        self._send(404, "text/plain; charset=utf-8")
        self.wfile.write(b"not found")

    def do_POST(self):
        path = self.path.split("?", 1)[0]

        if path == "/api/quit":
            self._send(200, "application/json; charset=utf-8")
            self.wfile.write(json.dumps({"ok": True}, ensure_ascii=False).encode("utf-8"))
            threading.Thread(target=lambda: (time.sleep(0.2), os._exit(0)), daemon=True).start()
            return

        if path == "/api/drop_paths":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
                paths = payload.get("paths", [])
                if isinstance(paths, str):
                    paths = [paths]
                clean = register_dropped_paths(paths)
                self._send(200, "application/json; charset=utf-8")
                self.wfile.write(json.dumps({"ok": bool(clean), "summary": summarize_paths(clean or paths), "workspace": summarize_paths(clean) if clean else ""}, ensure_ascii=False).encode("utf-8"))
            except Exception as e:
                self._send(500, "application/json; charset=utf-8")
                self.wfile.write(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False).encode("utf-8"))
            return

        if path == "/api/chats/new":
            try:
                chat = create_chat()
                self._send(200, "application/json; charset=utf-8")
                self.wfile.write(json.dumps({"ok": True, "chat": chat, "active_chat_id": chat["id"]}, ensure_ascii=False).encode("utf-8"))
            except Exception as e:
                self._send(500, "application/json; charset=utf-8")
                self.wfile.write(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False).encode("utf-8"))
            return

        if path == "/api/chats/select":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
                chat_id = set_active_chat(str(payload.get("id", "")))
                workspace_paths = get_chat_workspace(chat_id)
                self._send(200, "application/json; charset=utf-8")
                self.wfile.write(json.dumps({"ok": True, "active_chat_id": chat_id, "workspace": summarize_paths(workspace_paths) if workspace_paths else ""}, ensure_ascii=False).encode("utf-8"))
            except Exception as e:
                self._send(500, "application/json; charset=utf-8")
                self.wfile.write(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False).encode("utf-8"))
            return

        if path == "/api/chats/rename":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
                chat = rename_chat(str(payload.get("id", "")), str(payload.get("title", "")))
                set_active_chat(str(chat.get("id", "")))
                self._send(200, "application/json; charset=utf-8")
                self.wfile.write(json.dumps({"ok": True, "chat": chat, "active_chat_id": chat.get("id")}, ensure_ascii=False).encode("utf-8"))
            except Exception as e:
                self._send(500, "application/json; charset=utf-8")
                self.wfile.write(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False).encode("utf-8"))
            return

        if path == "/api/chats/delete":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
                result = delete_chat(str(payload.get("id", "")))
                self._send(200, "application/json; charset=utf-8")
                self.wfile.write(json.dumps({"ok": True, **result}, ensure_ascii=False).encode("utf-8"))
            except Exception as e:
                self._send(500, "application/json; charset=utf-8")
                self.wfile.write(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False).encode("utf-8"))
            return

        if path == "/api/chat":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
                raw_command = str(payload.get("command", ""))
                chat_id = str(payload.get("chat_id", "")).strip()
                if chat_id:
                    chat_id = set_active_chat(chat_id)
                else:
                    chat_id = get_active_chat_id(True)
                command = raw_command
                command = apply_dropped_context(command, chat_id)
                if not begin_task(command):
                    answer = task_busy_message()
                    save_chat_message("user", raw_command or command, "text", command, chat_id)
                    save_chat_message("assistant", answer, "text", chat_id=chat_id)
                    push_event("answer", answer)
                    speak_answer_async(answer, "Ich bin noch beschäftigt.")
                    self._send(200, "application/json; charset=utf-8")
                    self.wfile.write(json.dumps({"answer": answer, "chat_id": chat_id, "busy": True}, ensure_ascii=False).encode("utf-8"))
                    return
                push_event("heard", command)
                phase, label = command_phase(command)
                push_phase(phase, label, command)
                if phase != "web":
                    open_work_window(minimized=(phase == "coding"))
                threading.Thread(target=execute_command, args=(command, raw_command, "text", chat_id, True), daemon=True).start()
                if phase == "web":
                    answer = "Aufgabe gestartet. Browser-Vorschau wird geoeffnet."
                elif phase == "coding":
                    answer = "Aufgabe gestartet. Codierfenster wird minimiert."
                else:
                    answer = "Aufgabe gestartet. Arbeitsfenster wurde geoeffnet."

                self._send(200, "application/json; charset=utf-8")
                self.wfile.write(json.dumps({"answer": answer, "chat_id": chat_id}, ensure_ascii=False).encode("utf-8"))
            except Exception as e:
                error_answer = f"Serverfehler: {e}"
                push_event("answer", error_answer)
                save_chat_message("assistant", error_answer, "text", chat_id=locals().get("chat_id", ""))
                speak_answer_async(error_answer, "Es gab einen Serverfehler.")
                self._send(500, "application/json; charset=utf-8")
                self.wfile.write(json.dumps({"answer": error_answer}, ensure_ascii=False).encode("utf-8"))
            return

        self._send(404, "application/json")
        self.wfile.write(b'{"error":"not found"}')

    def log_message(self, *args):
        return

def start_server():
    ThreadingHTTPServer(("127.0.0.1", PORT), JarvisHandler).serve_forever()

def minimize_console_windows():
    try:
        import ctypes, time
        user32 = ctypes.windll.user32
        SW_MINIMIZE = 6
        EnumWindows = user32.EnumWindows
        EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        GetWindowTextW = user32.GetWindowTextW
        GetWindowTextLengthW = user32.GetWindowTextLengthW
        IsWindowVisible = user32.IsWindowVisible
        ShowWindow = user32.ShowWindow
        targets = [
            "cmd.exe",
            "powershell",
            "ollama",
            "comfyui",
            "stable diffusion",
            "system einschalten",
            "start_",
            "jarvis coding live",
            "jarvis analyse live",
            "jarvis arbeitet live",
        ]
        def callback(hwnd, lparam):
            if not IsWindowVisible(hwnd):
                return True
            length = GetWindowTextLengthW(hwnd)
            if length <= 0:
                return True
            buff = ctypes.create_unicode_buffer(length + 1)
            GetWindowTextW(hwnd, buff, length + 1)
            title = buff.value.lower()
            if any(t in title for t in targets) and "jarvis 3d" not in title:
                try:
                    ShowWindow(hwnd, SW_MINIMIZE)
                except Exception:
                    pass
            return True
        time.sleep(3)
        EnumWindows(EnumWindowsProc(callback), 0)
    except Exception:
        pass

def main():
    if not acquire_instance_lock():
        print("Jarvis laeuft bereits oder startet gerade. Ich starte keine zweite Instanz.")
        try:
            webbrowser.open(f"http://127.0.0.1:{PORT}/", new=2)
        except Exception:
            pass
        return

    cleanup_retained_data()
    if not WEB_DIR.exists():
        print("Fehler: Ordner jarvis_3d_webgl fehlt.")
        input("Enter...")
        return

    url = f"http://127.0.0.1:{PORT}/"
    if jarvis_already_running():
        print("Jarvis laeuft bereits. Oeffne vorhandenes Fenster.")
        try:
            webbrowser.open(url, new=2)
        except Exception:
            pass
        return

    threading.Thread(target=start_server, daemon=True).start()
    threading.Thread(target=wakeword_loop, daemon=True).start()
    threading.Thread(target=minimize_console_windows, daemon=True).start()
    threading.Thread(target=retention_cleanup_loop, daemon=True).start()
    threading.Timer(2.5, startup_greeting).start()
    threading.Timer(5.0, startup_auto_mode).start()

    try:
        from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox
        from PySide6.QtCore import QUrl, Qt
        from PySide6.QtWebEngineWidgets import QWebEngineView
    except Exception as e:
        try:
            from PySide6.QtWidgets import QApplication, QMessageBox
            app = QApplication(sys.argv)
            QMessageBox.critical(
                None,
                "JARVIS 3D Desktop Engine fehlt",
                "Für 3D direkt am Desktop fehlt QtWebEngine.\n\n"
                "Bitte im Jarvis-Ordner starten:\n"
                "INSTALL_DESKTOP_3D_ENGINE.bat\n\n"
                f"Fehler:\n{e}"
            )
        except Exception:
            print("JARVIS 3D Desktop Engine fehlt.")
            print("Starte: INSTALL_DESKTOP_3D_ENGINE.bat")
            print("Fehler:", e)
            input("Enter...")
        return

    class DropWebView(QWebEngineView):
        def __init__(self):
            super().__init__()
            self.setAcceptDrops(True)

        def dragEnterEvent(self, event):
            if event.mimeData().hasUrls():
                event.acceptProposedAction()
                try:
                    self.page().runJavaScript("window.jarvisShowDropHint && window.jarvisShowDropHint(true)")
                except Exception:
                    pass
            else:
                super().dragEnterEvent(event)

        def dragLeaveEvent(self, event):
            try:
                self.page().runJavaScript("window.jarvisShowDropHint && window.jarvisShowDropHint(false)")
            except Exception:
                pass
            super().dragLeaveEvent(event)

        def dropEvent(self, event):
            paths = []
            for url in event.mimeData().urls():
                local = url.toLocalFile()
                if local:
                    paths.append(local)
            if paths:
                register_dropped_paths(paths)
                try:
                    self.page().runJavaScript("window.jarvisShowDropHint && window.jarvisShowDropHint(false)")
                except Exception:
                    pass
                event.acceptProposedAction()
                return
            super().dropEvent(event)

    app = QApplication(sys.argv)
    win = QMainWindow()
    win.setWindowTitle("JARVIS 3D AUTO WAKEWORD")
    win.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
    win.resize(1320, 860)
    view = DropWebView()
    view.load(QUrl(url))
    win.setCentralWidget(view)
    win.showFullScreen()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
