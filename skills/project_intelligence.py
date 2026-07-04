import hashlib
import json
import os
import re
import time
from pathlib import Path

from config import BASE_DIR


def re_tokens(text: str):
    return re.findall(r"[a-zA-Z0-9_äöüÄÖÜß-]+", text or "")


class ProjectIntelligence:
    def __init__(self, jarvis_root: Path = None):
        self.jarvis_root = Path(jarvis_root or BASE_DIR).resolve()
        self.data_file = self.jarvis_root / "data" / "project_intelligence.json"
        self.data_file.parent.mkdir(parents=True, exist_ok=True)

    def context_for(self, root: Path, task: str, allow_write: bool) -> str:
        root = Path(root).resolve()
        profile = self.profile(root)
        memory = self._get_memory(root)
        file_summary = self._file_summary(root)
        focus_files = self._focus_files(root, task)
        self._save_profile(root, profile)
        lines = [
            "PROJEKT-INTELLIGENZ:",
            f"- Typ: {profile.get('type', 'unbekannt')}",
            f"- Sprachen: {', '.join(profile.get('languages', [])) or 'unbekannt'}",
            f"- Frameworks: {', '.join(profile.get('frameworks', [])) or 'keine erkannt'}",
            f"- Wichtige Dateien: {', '.join(profile.get('key_files', [])[:12]) or 'keine erkannt'}",
            f"- Projektdateien: {file_summary.get('count', 0)} relevante Text-/Code-Dateien erkannt",
            f"- Dateiarten: {', '.join(file_summary.get('extensions', [])[:10]) or 'keine erkannt'}",
            f"- Wahrscheinlich relevant: {', '.join(focus_files[:10]) or 'erst Dateisuche nutzen'}",
            f"- Sinnvolle Tests: {', '.join(profile.get('test_commands', [])[:5]) or 'nur Syntax-/Dateipruefung'}",
        ]
        if memory.get("summary"):
            lines.append(f"- Gelernt: {memory['summary']}")
        if memory.get("last_task"):
            lines.append(f"- Letzter Auftrag: {memory['last_task']}")
        if memory.get("last_result"):
            lines.append(f"- Letztes Ergebnis: {memory['last_result']}")
        if memory.get("recent_errors"):
            lines.append("- Bekannte Fehlerdatenbank:")
            for item in memory["recent_errors"][:5]:
                lines.append(f"  * {item}")
        if allow_write:
            lines.extend([
                "",
                "ARBEITSABLAUF:",
                "1. Projektprofil und vorhandene Struktur beachten.",
                "2. Erst relevante Dateien lesen, dann klein und gezielt aendern.",
                "3. Nach der Aenderung passende Tests/Checks nennen.",
                "4. Wenn ein Test fehlschlaegt, Fehler kurz analysieren und wenn moeglich fixen.",
                "5. Im Ergebnis konkrete Dateien, Diff-Zusammenfassung, Tests und naechste Schritte nennen.",
            ])
        else:
            lines.extend([
                "",
                "ANALYSEABLAUF:",
                "1. Projektprofil beachten.",
                "2. Konkrete Befunde nennen, keine allgemeinen Wiederholungen.",
                "3. Priorisiere die besten naechsten 3 Schritte.",
            ])
        return "\n".join(lines)

    def focus_files(self, root: Path, task: str, limit: int = 12):
        return self._focus_files(Path(root).resolve(), task)[:limit]

    def codex_plan(self, root: Path, task: str, allow_write: bool) -> str:
        root = Path(root).resolve()
        profile = self.profile(root)
        focus_files = self.focus_files(root, task, limit=10)
        tests = profile.get("test_commands", [])[:4]
        mode = "Aendern" if allow_write else "Analyse"
        lines = [
            "CODEX-AUFGABENPLAN:",
            f"1. Modus: {mode}. Auftrag aus Chat-Kontext verstehen, keine alten Vorschlaege wiederholen.",
            f"2. Fokus-Dateien zuerst pruefen: {', '.join(focus_files) if focus_files else 'per Suche ermitteln'}.",
            "3. Nur noetige Dateien anfassen; keine Logs, Backups, Models, external oder generierte Projekte durchsuchen.",
        ]
        if allow_write:
            lines.extend([
                "4. Aenderung klein halten, danach Diff und geaenderte Dateien melden.",
                f"5. Tests/Checks ausfuehren: {', '.join(tests) if tests else 'Syntax-/Dateipruefung passend zum Projekt'}.",
                "6. Wenn ein Check fehlschlaegt: Fehler klar nennen und nicht so tun, als waere alles fertig.",
            ])
        else:
            lines.extend([
                "4. Konkrete Vorschlaege priorisieren, damit der Nutzer danach mit Nummern weiterarbeiten kann.",
                "5. Keine Dateien aendern.",
            ])
        return "\n".join(lines)

    def profile(self, root: Path) -> dict:
        root = Path(root).resolve()
        names = self._top_level_names(root)
        lower = {n.lower(): n for n in names}
        key_files = []
        languages = []
        frameworks = []
        project_type = "allgemeines projekt"

        def has(name: str) -> bool:
            return name.lower() in lower

        def add_lang(name: str):
            if name not in languages:
                languages.append(name)

        def add_fw(name: str):
            if name not in frameworks:
                frameworks.append(name)

        for name in [
            "package.json", "pyproject.toml", "requirements.txt", "app.py",
            "brain.py", "index.html", "vite.config.js", "next.config.js",
            "project.godot", "Cargo.toml", "go.mod", "README.md",
        ]:
            if has(name):
                key_files.append(lower[name.lower()])

        if has("package.json"):
            add_lang("JavaScript/TypeScript")
            project_type = "Node/Web-Projekt"
            package = self._read_json(root / lower["package.json"])
            deps = {}
            if isinstance(package, dict):
                deps.update(package.get("dependencies") or {})
                deps.update(package.get("devDependencies") or {})
                scripts = package.get("scripts") or {}
                if "react" in deps:
                    add_fw("React")
                if "next" in deps:
                    add_fw("Next.js")
                if "vite" in deps:
                    add_fw("Vite")
                if "phaser" in deps:
                    add_fw("Phaser")
                    project_type = "Browser-Spiel"
                if scripts:
                    key_files.append("package.json:scripts")
        if has("index.html"):
            add_lang("HTML/CSS/JavaScript")
            if project_type == "allgemeines projekt":
                project_type = "Webseite/Web-App"
        if has("project.godot"):
            add_lang("GDScript")
            add_fw("Godot")
            project_type = "Godot-Spiel"
        if has("ProjectSettings") or (has("Assets") and any(root.glob("Assets/**/*.cs"))):
            add_lang("C#")
            add_fw("Unity")
            project_type = "Unity-Spiel"
        if has("pyproject.toml") or has("requirements.txt") or has("app.py"):
            add_lang("Python")
            if has("app.py") and has("brain.py"):
                project_type = "Jarvis/Python-Assistent"
        if has("Cargo.toml"):
            add_lang("Rust")
            project_type = "Rust-Projekt"
        if has("go.mod"):
            add_lang("Go")
            project_type = "Go-Projekt"

        test_commands = self.suggest_tests(root)
        return {
            "type": project_type,
            "languages": languages,
            "frameworks": frameworks,
            "key_files": list(dict.fromkeys(key_files)),
            "test_commands": test_commands,
            "updated_at": int(time.time()),
        }

    def suggest_tests(self, root: Path):
        root = Path(root).resolve()
        commands = []
        package = root / "package.json"
        if package.exists():
            data = self._read_json(package)
            scripts = data.get("scripts") if isinstance(data, dict) else {}
            if isinstance(scripts, dict):
                if "test" in scripts:
                    commands.append("npm test")
                if "build" in scripts:
                    commands.append("npm run build")
                if "lint" in scripts:
                    commands.append("npm run lint")
        if (root / "pyproject.toml").exists() or (root / "pytest.ini").exists() or (root / "tests").exists():
            commands.append("python -m pytest -q")
        if (root / "app.py").exists() or any(root.glob("*.py")):
            commands.append("python -m py_compile <geaenderte Python-Dateien>")
        if (root / "index.html").exists():
            commands.append("HTML/CSS/JS-Dateipruefung")
        return commands[:6]

    def remember_result(self, root: Path, task: str, result_text: str, success: bool) -> None:
        root = Path(root).resolve()
        data = self._load()
        key = self._key(root)
        entry = data.get(key) or {"path": str(root), "history": []}
        entry["path"] = str(root)
        entry["profile"] = self.profile(root)
        entry["last_task"] = self._clip(task, 500)
        entry["last_result"] = self._clip(result_text, 700)
        entry["last_success"] = bool(success)
        entry["updated_at"] = int(time.time())
        history = entry.get("history") or []
        history.insert(0, {
            "time": int(time.time()),
            "task": self._clip(task, 300),
            "result": self._clip(result_text, 400),
            "success": bool(success),
        })
        entry["history"] = history[:20]
        if not success:
            errors = entry.get("errors") or []
            errors.insert(0, {
                "time": int(time.time()),
                "task": self._clip(task, 300),
                "error": self._clip(result_text, 700),
            })
            entry["errors"] = errors[:30]
        data[key] = entry
        self._save(data)

    def error_report(self, root: Path) -> str:
        root = Path(root).resolve()
        entry = self._load().get(self._key(root), {})
        errors = entry.get("errors") or []
        if not errors:
            return "Fehlerdatenbank: keine bekannten Fehler fuer diesen Projektordner."
        lines = ["Fehlerdatenbank:"]
        for item in errors[:10]:
            ts = time.strftime("%Y-%m-%d %H:%M", time.localtime(int(item.get("time") or 0)))
            lines.append(f"- {ts} | Auftrag: {item.get('task', '')} | Fehler: {item.get('error', '')}")
        return "\n".join(lines)

    def project_report(self, root: Path, task: str = "") -> str:
        root = Path(root).resolve()
        profile = self.profile(root)
        memory = self._get_memory(root)
        focus = self.focus_files(root, task or "jarvis projekt faehigkeiten coding video bild", limit=12)
        lines = [
            "PROJEKT-GEDAECHTNIS",
            f"Ordner: {root}",
            f"Typ: {profile.get('type', 'unbekannt')}",
            f"Sprachen: {', '.join(profile.get('languages') or []) or 'unbekannt'}",
            f"Frameworks: {', '.join(profile.get('frameworks') or []) or 'keine erkannt'}",
            f"Wichtige Dateien: {', '.join(profile.get('key_files') or []) or 'keine erkannt'}",
            f"Fokus-Dateien: {', '.join(focus) if focus else 'keine erkannt'}",
            f"Tests: {', '.join(profile.get('test_commands') or []) or 'keine erkannt'}",
        ]
        if memory.get("last_task"):
            lines.append(f"Letzter Auftrag: {memory['last_task']}")
        if memory.get("last_result"):
            lines.append(f"Letztes Ergebnis: {memory['last_result']}")
        recent_errors = memory.get("recent_errors") or []
        if recent_errors:
            lines.append("Letzte Fehler:")
            lines.extend(f"- {item}" for item in recent_errors[:5])
        else:
            lines.append("Letzte Fehler: keine gespeichert")
        return "\n".join(lines)

    def followup_context(self, root: Path, limit: int = 6) -> str:
        root = Path(root).resolve()
        entry = self._load().get(self._key(root), {})
        history = entry.get("history") or []
        lines = []
        if entry.get("last_task"):
            lines.append(f"Letzter Auftrag: {entry.get('last_task', '')}")
        if entry.get("last_result"):
            lines.append(f"Letztes Ergebnis: {entry.get('last_result', '')}")
        if history:
            lines.append("Letzte Projekt-Historie:")
            for index, item in enumerate(history[:limit], start=1):
                lines.append(
                    f"{index}. Auftrag: {self._clip(item.get('task', ''), 220)} | "
                    f"Ergebnis: {self._clip(item.get('result', ''), 260)}"
                )
        return "\n".join(lines)

    def _save_profile(self, root: Path, profile: dict) -> None:
        data = self._load()
        key = self._key(root)
        entry = data.get(key) or {"path": str(root), "history": []}
        entry["path"] = str(root)
        entry["profile"] = profile
        entry["updated_at"] = int(time.time())
        data[key] = entry
        self._save(data)

    def _get_memory(self, root: Path) -> dict:
        entry = self._load().get(self._key(root), {})
        history = entry.get("history") or []
        summary = ""
        if history:
            last = history[0]
            summary = f"{last.get('task', '')} -> {last.get('result', '')}"
        return {
            "summary": self._clip(summary, 500),
            "last_task": entry.get("last_task", ""),
            "last_result": entry.get("last_result", ""),
            "recent_errors": [
                self._clip(f"{e.get('task', '')} -> {e.get('error', '')}", 500)
                for e in (entry.get("errors") or [])[:5]
            ],
        }

    def _top_level_names(self, root: Path):
        blocked = {
            ".git", ".venv", "venv", "__pycache__", "node_modules", "models",
            "external", "data", "logs", "codex_backups", "project_backups",
            "Jarvis_Projects", "jarvis_projects",
        }
        try:
            return [p.name for p in root.iterdir() if p.name not in blocked]
        except Exception:
            return []

    def _project_files(self, root: Path, limit: int = 500):
        blocked = {
            ".git", ".venv", "venv", "__pycache__", "node_modules", "models",
            "external", "data", "logs", "codex_backups", "project_backups",
            "sandbox_runs", ".aider.tags.cache.v4", "Jarvis_Projects", "jarvis_projects",
        }
        suffixes = {
            ".py", ".js", ".ts", ".tsx", ".jsx", ".html", ".css", ".json",
            ".md", ".txt", ".yml", ".yaml", ".toml", ".ini", ".bat", ".ps1",
            ".cs", ".cpp", ".c", ".h", ".hpp", ".java", ".go", ".rs", ".php",
        }
        special_names = {
            ".env", ".env.example", ".aider.conf.yml", ".aider.model.settings.yml",
            ".aiderignore", ".rooignore", "Jarvis_Roo_Code.code-workspace",
            "System einschalten.bat",
        }
        files = []
        try:
            for current, dirs, names in os.walk(root):
                dirs[:] = [d for d in dirs if d not in blocked and d.lower() not in blocked]
                current_path = Path(current)
                for name in names:
                    if name.startswith(".aider") and name not in special_names:
                        continue
                    path = current_path / name
                    if path.suffix.lower() not in suffixes and name not in special_names:
                        continue
                    try:
                        if path.stat().st_size > 2_000_000:
                            continue
                        rel = path.relative_to(root).as_posix()
                    except Exception:
                        continue
                    files.append(rel)
                    if len(files) >= limit:
                        return files
        except Exception:
            return files
        return files

    def _file_summary(self, root: Path) -> dict:
        files = self._project_files(root)
        counts = {}
        for rel in files:
            ext = Path(rel).suffix.lower() or "<none>"
            counts[ext] = counts.get(ext, 0) + 1
        extensions = [
            f"{ext}:{count}"
            for ext, count in sorted(counts.items(), key=lambda item: item[1], reverse=True)
        ]
        return {"count": len(files), "extensions": extensions}

    def _focus_files(self, root: Path, task: str):
        files = self._project_files(root)
        text = " ".join(str(task or "").lower().replace("\\", "/").split())
        text_norm = (
            text.replace("ä", "ae")
            .replace("ö", "oe")
            .replace("ü", "ue")
            .replace("ß", "ss")
            .replace("Ã¤", "ae")
            .replace("Ã¶", "oe")
            .replace("Ã¼", "ue")
            .replace("ÃŸ", "ss")
        )
        wants_3d = any(word in text for word in ["3d", "hologram", "hologramm", "webgl", "jarvis_3d", "hologramm-ui"])
        important_names = [
            "app.py", "brain.py", "config.py", "voice.py", "package.json",
            "index.html", "style.css", "script.js", "main.py", "server.js",
            "client.js",
        ]
        exact_scores = self._topic_focus_scores(text_norm)
        scored = []
        for rel in files:
            low = rel.lower()
            if low.startswith("jarvis_3d_webgl/") and not wants_3d:
                continue
            score = 0
            name = Path(low).name
            score += exact_scores.get(low, 0)
            if name in [n.lower() for n in important_names]:
                score += 4
            for token in re_tokens(text_norm):
                if len(token) >= 4 and token in low:
                    score += 5
            if any(word in text_norm for word in ["bild", "image", "foto"]) and ("image" in low or "bild" in low):
                score += 8
            if any(word in text_norm for word in ["video", "comfy"]) and ("video" in low or "comfy" in low):
                score += 8
            if any(word in text_norm for word in ["stimme", "sprache", "sprech", "mikro", "voice"]) and ("voice" in low or "audio" in low):
                score += 8
            if any(word in text_norm for word in ["web", "homepage", "spiel", "game", "browser"]) and Path(low).suffix in {".html", ".css", ".js"}:
                score += 4
            if score:
                scored.append((score, rel))
        scored.sort(key=lambda item: (-item[0], item[1]))
        return [rel for _, rel in scored[:15]]

    def _topic_focus_scores(self, text: str):
        rules = [
            (
                ["bild", "image", "foto", "sdxl", "stable diffusion", "upscale", "img2img", "referenzbild"],
                {
                    "skills/image_ai.py": 45,
                    "start_image_generator.bat": 22,
                    "install_image_generator.bat": 12,
                    "brain.py": 16,
                    "config.py": 14,
                    ".env": 10,
                },
            ),
            (
                ["video", "comfy", "comfyui", "workflow", "ki video"],
                {
                    "skills/video_ai.py": 45,
                    "skills/comfyui_skill.py": 24,
                    "start_comfyui.bat": 20,
                    "install_video_ai.bat": 14,
                    "brain.py": 16,
                    "config.py": 14,
                    ".env": 10,
                },
            ),
            (
                ["aider", "codex", "codey", "diff", "rollback", "fokus", "focus", "coding live", "live coding"],
                {
                    "skills/aider_agent.py": 50,
                    "skills/project_intelligence.py": 36,
                    ".aider.conf.yml": 24,
                    ".aider.model.settings.yml": 22,
                    "brain.py": 16,
                    "app.py": 14,
                    ".env": 10,
                    "System einschalten.bat".lower(): 10,
                },
            ),
            (
                ["roo", "vs code", "vscode", "workspace"],
                {
                    ".roo/roo-code-settings.json": 45,
                    "Jarvis_Roo_Code.code-workspace".lower(): 35,
                    ".vscode/settings.json": 25,
                    "JARVIS_ROO_CODE_START.bat".lower(): 18,
                },
            ),
            (
                ["chat", "chats", "verlauf", "umbenenn", "loesch", "losch", "speicher", "ordner rein"],
                {
                    "app.py": 45,
                    "brain.py": 18,
                    "skills/project_memory.py": 14,
                    "skills/memory.py": 12,
                },
            ),
            (
                ["was kann", "was koenn", "was noch", "faehigkeit", "faehigkeiten", "feature", "features", "funktion", "funktionen", "mach nummer", "nummer"],
                {
                    "app.py": 36,
                    "brain.py": 34,
                    "skills/aider_agent.py": 24,
                    "skills/project_intelligence.py": 24,
                    "skills/repo_agent.py": 18,
                    "skills/coder.py": 16,
                    "config.py": 12,
                },
            ),
            (
                ["stimme", "sprache", "sprachausgabe", "sprech", "hoert", "hort", "mikro", "microphone", "vosk", "michael"],
                {
                    "voice.py": 50,
                    "app.py": 18,
                    "config.py": 16,
                    ".env": 10,
                },
            ),
            (
                ["internet", "google", "recherche", "browser", "websuche", "web recherche"],
                {
                    "skills/internet_research.py": 45,
                    "skills/browser.py": 32,
                    "skills/browser_agent_v3.py": 18,
                    "brain.py": 18,
                    "config.py": 10,
                },
            ),
            (
                ["3d", "hologram", "hologramm", "webgl", "mund", "mimik", "partikel", "jarvis_3d"],
                {
                    "jarvis_3d_webgl/index.html": 50,
                    "app.py": 12,
                    "brain.py": 8,
                },
            ),
            (
                ["modell", "model", "ollama", "qwen", "480b", "context", "kontext", "ctx", "timeout"],
                {
                    "config.py": 35,
                    ".env": 32,
                    ".env.example": 22,
                    "skills/model_manager.py": 24,
                    "System einschalten.bat".lower(): 22,
                    ".aider.model.settings.yml": 18,
                },
            ),
            (
                ["start", "system einschalten", "autostart", "doppelt", "comfyui zweimal", "app.py zweimal"],
                {
                    "System einschalten.bat".lower(): 45,
                    "start_comfyui.bat": 28,
                    "app.py": 28,
                    "crash_watcher.py": 10,
                },
            ),
            (
                ["webseite", "website", "homepage", "spiel", "game", "browsergame", "html", "css", "javascript"],
                {
                    "skills/coder.py": 42,
                    "brain.py": 18,
                    "skills/aider_agent.py": 14,
                    "app.py": 12,
                },
            ),
        ]
        scores = {}
        for terms, paths in rules:
            if any(term in text for term in terms):
                for rel, points in paths.items():
                    scores[rel.lower()] = max(scores.get(rel.lower(), 0), points)
        return scores

    def _read_json(self, path: Path):
        try:
            return json.loads(path.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            return {}

    def _load(self) -> dict:
        try:
            if self.data_file.exists():
                data = json.loads(self.data_file.read_text(encoding="utf-8", errors="replace"))
                if isinstance(data, dict):
                    return data
        except Exception:
            pass
        return {}

    def _save(self, data: dict) -> None:
        try:
            tmp = self.data_file.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(tmp, self.data_file)
        except Exception:
            pass

    def _key(self, root: Path) -> str:
        text = str(Path(root).resolve()).lower()
        return hashlib.sha1(text.encode("utf-8", errors="ignore")).hexdigest()

    def _clip(self, text: str, limit: int) -> str:
        text = " ".join(str(text or "").split())
        if len(text) <= limit:
            return text
        return text[:limit].rsplit(" ", 1)[0].rstrip() + "..."
