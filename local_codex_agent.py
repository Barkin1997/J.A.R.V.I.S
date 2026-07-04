import difflib
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path


MODEL = os.getenv("OLLAMA_CODE_MODEL") or os.getenv("OLLAMA_MODEL") or "qwen3-coder-next:latest"


class LocalCodexAgent:
    """
    Lokaler Codex-Pro-Modus für Jarvis.

    Ziel:
    - mehr Kontext wie Codex
    - bessere Tool-Steuerung
    - lokale Tools: Dateibaum, Suche, Lesen, Patchen, Schreiben, Tests
    - Backups vor Änderungen
    - 3D-Schutz: jarvis_3d_webgl bleibt geschützt, außer der Nutzer verlangt ausdrücklich 3D/UI/Design.
    """

    IGNORE_DIRS = {
        ".git", ".venv", "venv", "env", "__pycache__", ".mypy_cache", ".pytest_cache",
        ".aider.tags.cache.v4",
        "node_modules", "external", "models", "ComfyUI", "stable-diffusion", "stable_diffusion",
        "data/codex_logs", "codex_backups", "sandbox_runs", "dist", "build",
    }

    CODE_EXTS = {
        ".py", ".bat", ".ps1", ".js", ".ts", ".tsx", ".jsx", ".html", ".css",
        ".json", ".md", ".txt", ".env", ".ini", ".toml", ".yml", ".yaml",
    }

    SAFE_COMMANDS = {
        "py_compile",
        "pytest",
        "python_version",
        "ollama_list",
        "ollama_test",
        "dir",
        "tree",
    }

    CORE_FILES = [
        "app.py",
        "brain.py",
        "voice.py",
        "config.py",
        "ollama_client.py",
        "plugin_manager.py",
        "local_codex_agent.py",
        "requirements.txt",
        ".env",
        "System einschalten.bat",
        "JARVIS_DEBUG_START.bat",
    ]

    def __init__(self, ollama=None, root=None):
        self.ollama = ollama
        self.root = Path(root or Path(__file__).resolve().parent).resolve()
        self.log_dir = self.root / "data" / "codex_logs"
        self.backup_dir = self.root / "codex_backups"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def help(self):
        return (
            "Lokaler Codex-Pro-Modus ist aktiv.\n\n"
            "Neue Befehle:\n"
            "- Jarvis, codex status\n"
            "- Jarvis, codex index\n"
            "- Jarvis, codex suche ollama\n"
            "- Jarvis, codex lese app.py\n"
            "- Jarvis, codex prüfe dich\n"
            "- Jarvis, codex finde warum du nicht antwortest\n"
            "- Jarvis, codex repariere app.py\n"
            "- Jarvis, codex ändere brain.py: ...\n"
            "- Jarvis, codex test\n\n"
            "Pro-Funktionen:\n"
            "- mehr Kontext durch Projektindex\n"
            "- Tool-Schleife ähnlich Codex\n"
            "- Dateien suchen/lesen/patchen\n"
            "- sichere Tests ausführen\n"
            "- automatische Backups\n"
            "- 3D bleibt geschützt, außer du sagst ausdrücklich 3D/UI/Design."
        )

    def run(self, task: str):
        task = (task or "").strip()
        if not task or task.lower() in {"modus", "mode", "hilfe", "help"}:
            return self.help()

        low = task.lower()

        if low.startswith(("status", "info")):
            return self.status()

        if low.startswith(("index", "dateibaum", "projektindex", "project index")):
            return self.project_index()

        if low.startswith(("suche ", "search ", "grep ")):
            query = re.sub(r"^(suche|search|grep)\s+", "", task, flags=re.I).strip()
            return self.search_text(query)

        if low.startswith(("lese ", "read ", "zeige ")):
            rel = re.sub(r"^(lese|read|zeige)\s+", "", task, flags=re.I).strip()
            return self.read_file(rel)

        if any(x in low for x in ["test", "prüfe start", "pruefe start", "check start"]):
            return self.run_tests()

        if any(x in low for x in ["reparier", "repariere", "fix", "ändere", "aendere", "verbesser", "baue", "füge", "fuege", "implementier"]):
            return self.agentic_modify(task)

        return self.agentic_analyze(task)

    def status(self):
        files = self._all_code_files()
        return (
            "Lokaler Codex-Pro-Modus bereit.\n"
            f"Modell: {MODEL}\n"
            f"Projekt: {self.root}\n"
            f"Indexierte Code-Dateien: {len(files)}\n"
            f"Backups: {self.backup_dir}\n"
            f"Logs: {self.log_dir}\n"
            "Tools: tree, search, read_file, write_file, replace_text, run_command, py_compile\n"
            "3D-Schutz: jarvis_3d_webgl wird nur geändert, wenn du ausdrücklich 3D/UI/Design sagst."
        )

    def project_index(self):
        files = self._all_code_files()
        rows = []
        for rel in files[:220]:
            p = self.root / rel
            try:
                size = p.stat().st_size
            except Exception:
                size = 0
            rows.append(f"{rel} ({size} bytes)")
        if len(files) > 220:
            rows.append(f"...gekürzt, insgesamt {len(files)} Code-Dateien")
        return "Projektindex:\n" + "\n".join(rows)

    def search_text(self, query: str):
        query = (query or "").strip()
        if not query:
            return "Bitte Suchwort angeben, z.B. Jarvis, codex suche ollama"
        results = self._tool_search_text(query)
        return results or f"Keine Treffer für: {query}"

    def read_file(self, rel: str):
        rel = rel.strip().strip('"').strip("'").replace("\\", "/")
        ok, reason = self._path_allowed(rel, allow_3d=self._allow_3d(rel))
        if not ok:
            return f"Kann Datei nicht lesen: {reason}"
        p = self.root / rel
        if not p.exists():
            return f"Datei nicht gefunden: {rel}"
        txt = p.read_text(encoding="utf-8", errors="ignore")
        if len(txt) > 18000:
            txt = txt[:18000] + "\n...<gekürzt>..."
        return f"--- {rel} ---\n{txt}"

    def agentic_analyze(self, task: str):
        context = self._build_context(task, max_total=90000)
        prompt = self._system_prompt(task, allow_write=False) + "\n\n" + context
        answer = self._ask_model(prompt, temperature=0.05, timeout=420)
        self._write_log("analyze", task, answer)
        return answer or "Codex-Pro-Analyse hatte keine Antwort."

    def agentic_modify(self, task: str):
        """
        Kleine Tool-Schleife:
        1. Modell bekommt Kontext und darf Toolcalls anfordern.
        2. Jarvis führt sichere Tools aus.
        3. Modell darf Änderungen als JSON liefern.
        """
        allow_3d = self._allow_3d(task)
        transcript = []
        context = self._build_context(task, max_total=95000)

        for step in range(1, 4):
            tool_info = self._tool_instructions(allow_write=True, allow_3d=allow_3d)
            prompt = (
                self._system_prompt(task, allow_write=True)
                + "\n\n"
                + tool_info
                + "\n\nBISHERIGE TOOL-ERGEBNISSE:\n"
                + "\n\n".join(transcript[-6:])
                + "\n\nAKTUELLER KONTEXT:\n"
                + context
                + "\n\nAUFGABE:\n"
                + task
                + "\n\n"
                "Entscheide jetzt:\n"
                "A) Wenn du mehr Informationen brauchst, antworte als JSON mit tool_calls.\n"
                "B) Wenn du ändern willst, antworte als JSON mit changes.\n"
                "C) Wenn keine Änderung nötig ist, antworte als JSON mit summary und changes: []."
            )
            raw = self._ask_model(prompt, temperature=0.03, timeout=700)
            self._write_log(f"modify_step_{step}_raw", task, raw)
            data = self._extract_json(raw)

            if not data:
                return (
                    "Codex-Pro konnte keine sichere JSON-Antwort liefern. Es wurde nichts geändert.\n"
                    "Die Antwort wurde geloggt. Sag genauer, was repariert werden soll."
                )

            if data.get("tool_calls"):
                tool_result = self._execute_tool_calls(data.get("tool_calls"), allow_3d=allow_3d)
                transcript.append(tool_result)
                continue

            return self._apply_changes(data, task, allow_3d=allow_3d)

        return "Codex-Pro hat nach mehreren Tool-Schritten keine sichere Änderung abgeschlossen. Es wurde nichts geändert."

    def _system_prompt(self, task, allow_write):
        return (
            "Du bist ein lokaler Codex-Pro-Agent in einem Windows Jarvis-Projekt.\n"
            f"Modell: {MODEL}\n"
            "Sprache: Deutsch.\n"
            "Arbeite wie Codex: erst verstehen, dann gezielt ändern, danach testen.\n"
            "Du hast mehr Kontext über Projektindex, Suche, Lesen, sichere Befehle und Backups.\n"
            "WICHTIG:\n"
            "- Kein unnötiges Umschreiben.\n"
            "- Kleine gezielte Patches.\n"
            "- Keine Dateien in .venv/external/models/data/logs ändern.\n"
            "- jarvis_3d_webgl nicht ändern, außer Aufgabe sagt ausdrücklich 3D/UI/Design.\n"
            "- Wenn du Dateien änderst, gib vollständigen neuen Dateiinhalt aus.\n"
            "- Antworten für Dateiänderungen NUR als gültiges JSON, kein Markdown.\n"
            f"- Schreibrechte in diesem Schritt: {allow_write}\n"
        )

    def _tool_instructions(self, allow_write, allow_3d):
        return (
            "VERFÜGBARE TOOLS als JSON:\n"
            "{\n"
            '  "tool_calls": [\n'
            '    {"tool": "tree", "args": {"limit": 200}},\n'
            '    {"tool": "search_text", "args": {"query": "OLLAMA_MODEL"}},\n'
            '    {"tool": "read_file", "args": {"path": "app.py"}},\n'
            '    {"tool": "run_command", "args": {"command": "py_compile", "path": "app.py"}},\n'
            '    {"tool": "run_command", "args": {"command": "ollama_list"}},\n'
            '    {"tool": "replace_text", "args": {"path": "app.py", "old": "alt", "new": "neu"}}\n'
            "  ]\n"
            "}\n\n"
            "ODER Änderungen als JSON:\n"
            "{\n"
            '  "summary": "kurz",\n'
            '  "changes": [ {"path": "brain.py", "content": "vollständiger neuer Inhalt"} ],\n'
            '  "commands": [ {"command": "py_compile", "path": "brain.py"} ]\n'
            "}\n\n"
            f"Schreiben erlaubt: {allow_write}\n"
            f"3D-Dateien erlaubt: {allow_3d}\n"
        )

    def _execute_tool_calls(self, calls, allow_3d=False):
        out = []
        if not isinstance(calls, list):
            return "TOOL ERROR: tool_calls ist keine Liste."

        for call in calls[:12]:
            tool = str(call.get("tool", "")).strip()
            args = call.get("args") or {}
            try:
                if tool == "tree":
                    out.append("TOOL tree:\n" + self.project_index())
                elif tool == "search_text":
                    out.append("TOOL search_text:\n" + self._tool_search_text(str(args.get("query", ""))))
                elif tool == "read_file":
                    out.append("TOOL read_file:\n" + self._tool_read_file(str(args.get("path", "")), allow_3d=allow_3d))
                elif tool == "replace_text":
                    if not allow_3d and str(args.get("path", "")).replace("\\", "/").startswith("jarvis_3d_webgl/"):
                        out.append("TOOL replace_text: BLOCKED 3D geschützt.")
                    else:
                        out.append("TOOL replace_text:\n" + self._tool_replace_text(str(args.get("path", "")), str(args.get("old", "")), str(args.get("new", "")), allow_3d=allow_3d))
                elif tool == "run_command":
                    out.append("TOOL run_command:\n" + self._tool_run_command(args))
                else:
                    out.append(f"TOOL ERROR: unbekanntes Tool {tool}")
            except Exception as e:
                out.append(f"TOOL ERROR {tool}: {e}")

        result = "\n\n".join(out)
        self._write_log("tool_results", "tool_calls", result)
        return result

    def _apply_changes(self, data, task, allow_3d=False):
        changes = data.get("changes") or []
        if not isinstance(changes, list):
            return "Codex-Pro JSON war ungültig: changes ist keine Liste. Es wurde nichts geändert."

        if not changes:
            return "Codex-Pro: Keine Dateiänderung nötig.\n\n" + str(data.get("summary", ""))

        stamp = time.strftime("%Y%m%d_%H%M%S")
        backup_root = self.backup_dir / stamp
        backup_root.mkdir(parents=True, exist_ok=True)

        written, skipped, diffs = [], [], []
        snapshots = {}
        for ch in changes:
            rel = str(ch.get("path", "")).strip().replace("\\", "/")
            content = ch.get("content", None)
            if not rel or content is None:
                skipped.append(f"{rel or '?'}: ungültiger Änderungseintrag")
                continue

            ok, reason = self._path_allowed(rel, allow_3d=allow_3d)
            if not ok:
                skipped.append(f"{rel}: {reason}")
                continue

            target = (self.root / rel).resolve()
            before = ""
            existed = target.exists()
            if target.exists():
                before = target.read_text(encoding="utf-8", errors="ignore")
                b = backup_root / rel
                b.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, b)

            snapshots[rel] = {"target": target, "exists": existed, "content": before}
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(str(content).replace("\r\n", "\n"), encoding="utf-8")
            written.append(rel)
            diffs.append(self._diff_text(rel, before, str(content)))

        test_result = self._validate_files(written)

        # optionale sichere Commands
        commands_result = []
        for cmd in (data.get("commands") or [])[:5]:
            if isinstance(cmd, dict):
                commands_result.append(self._tool_run_command(cmd))

        if self._has_failed_validation(test_result, commands_result):
            self._restore_snapshots(snapshots)
            done = {
                "summary": data.get("summary", ""),
                "rolled_back": written,
                "skipped": skipped,
                "backup": str(backup_root),
                "test": test_result,
                "commands": commands_result,
            }
            self._write_log("modify_rollback", task, json.dumps(done, ensure_ascii=False, indent=2))
            msg = [
                "Codex-Pro Rollback: Test/Pruefung fehlgeschlagen, Aenderungen wurden zurueckgesetzt.",
                "Backup: " + str(backup_root),
            ]
            if data.get("summary"):
                msg.append("Zusammenfassung: " + str(data.get("summary")))
            if written:
                msg.append("Zurueckgesetzt:\n" + "\n".join("- " + w for w in written))
            if skipped:
                msg.append("Uebersprungen:\n" + "\n".join("- " + s for s in skipped))
            msg.append("Test:\n" + test_result)
            if commands_result:
                msg.append("Befehle:\n" + "\n".join(commands_result))
            if diffs:
                msg.append("Diff vor Rollback:\n" + self._clip_text("\n".join(diffs), 6000))
            return "\n\n".join(msg)

        done = {
            "summary": data.get("summary", ""),
            "written": written,
            "skipped": skipped,
            "backup": str(backup_root),
            "test": test_result,
            "commands": commands_result,
            "diff": "\n".join(diffs),
        }
        self._write_log("modify_done", task, json.dumps(done, ensure_ascii=False, indent=2))

        msg = ["Codex-Pro fertig."]
        if data.get("summary"):
            msg.append("Zusammenfassung: " + str(data.get("summary")))
        if written:
            msg.append("Geändert:\n" + "\n".join("- " + w for w in written))
            msg.append("Backup: " + str(backup_root))
        if skipped:
            msg.append("Übersprungen:\n" + "\n".join("- " + s for s in skipped))
        if test_result:
            msg.append("Test:\n" + test_result)
        if commands_result:
            msg.append("Befehle:\n" + "\n".join(commands_result))
        if diffs:
            msg.append("Diff:\n" + self._clip_text("\n".join(diffs), 6000))
        return "\n\n".join(msg)

    def run_tests(self):
        files = [f for f in self.CORE_FILES if f.endswith(".py") and (self.root / f).exists()]
        lines = []
        for rel in files:
            lines.append(self._tool_run_command({"command": "py_compile", "path": rel}))
        lines.append(self._tool_run_command({"command": "ollama_list"}))
        out = "\n".join(lines)
        self._write_log("test", "codex test", out)
        return out

    def _tool_run_command(self, args):
        command = str(args.get("command", "")).strip()
        path = str(args.get("path", "")).strip().replace("\\", "/")

        if command == "py_compile":
            if not path:
                return "py_compile: path fehlt"
            ok, reason = self._path_allowed(path, allow_3d=True)
            if not ok:
                return f"py_compile {path}: {reason}"
            p = self.root / path
            if not p.exists():
                return f"py_compile {path}: Datei nicht gefunden"
            r = subprocess.run([os.sys.executable, "-m", "py_compile", str(p)], cwd=str(self.root), capture_output=True, text=True, timeout=40)
            return f"py_compile {path}: " + ("OK" if r.returncode == 0 else (r.stderr.strip() or r.stdout.strip()))

        if command == "python_version":
            r = subprocess.run([os.sys.executable, "--version"], capture_output=True, text=True, timeout=15)
            return "python_version: " + (r.stdout.strip() or r.stderr.strip())

        if command == "ollama_list":
            try:
                r = subprocess.run(["ollama", "list"], cwd=str(self.root), capture_output=True, text=True, timeout=20)
                return "ollama_list:\n" + ((r.stdout or r.stderr or "").strip()[:5000])
            except Exception as e:
                return "ollama_list Fehler: " + str(e)

        if command == "ollama_test":
            try:
                r = subprocess.run(["ollama", "run", MODEL, "Antworte nur mit: OK"], cwd=str(self.root), capture_output=True, text=True, timeout=120)
                return "ollama_test:\n" + ((r.stdout or r.stderr or "").strip()[:5000])
            except Exception as e:
                return "ollama_test Fehler: " + str(e)

        if command == "tree":
            return self.project_index()

        return "Befehl blockiert oder unbekannt: " + command

    def _tool_search_text(self, query):
        query = (query or "").strip()
        if not query:
            return "search_text: query fehlt"

        results = []
        qlow = query.lower()
        for rel in self._all_code_files():
            p = self.root / rel
            try:
                txt = p.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            hits = []
            for i, line in enumerate(txt.splitlines(), start=1):
                if qlow in line.lower():
                    hits.append(f"L{i}: {line[:220]}")
                    if len(hits) >= 5:
                        break
            if hits:
                results.append(f"--- {rel} ---\n" + "\n".join(hits))
            if len(results) >= 30:
                results.append("...gekürzt...")
                break
        return "\n\n".join(results) or f"Keine Treffer für {query}"

    def _tool_read_file(self, rel, allow_3d=False):
        rel = rel.strip().strip('"').strip("'").replace("\\", "/")
        ok, reason = self._path_allowed(rel, allow_3d=allow_3d)
        if not ok:
            return f"read_file {rel}: {reason}"
        p = self.root / rel
        if not p.exists():
            return f"read_file {rel}: Datei nicht gefunden"
        txt = p.read_text(encoding="utf-8", errors="ignore")
        if len(txt) > 28000:
            txt = txt[:28000] + "\n...<gekürzt>..."
        return f"--- {rel} ---\n{txt}"

    def _tool_replace_text(self, rel, old, new, allow_3d=False):
        rel = rel.strip().strip('"').strip("'").replace("\\", "/")
        ok, reason = self._path_allowed(rel, allow_3d=allow_3d)
        if not ok:
            return f"replace_text {rel}: {reason}"
        if not old:
            return f"replace_text {rel}: old fehlt"
        p = self.root / rel
        if not p.exists():
            return f"replace_text {rel}: Datei nicht gefunden"
        txt = p.read_text(encoding="utf-8", errors="ignore")
        if old not in txt:
            return f"replace_text {rel}: old nicht gefunden"
        stamp = time.strftime("%Y%m%d_%H%M%S")
        b = self.backup_dir / stamp / rel
        b.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, b)
        updated = txt.replace(old, new, 1)
        p.write_text(updated, encoding="utf-8")
        test_result = self._validate_files([rel])
        if self._has_failed_validation(test_result, []):
            p.write_text(txt, encoding="utf-8")
            return (
                f"replace_text {rel}: Rollback, Test fehlgeschlagen. Backup: {b}\n"
                f"Test:\n{test_result}\n"
                f"Diff vor Rollback:\n{self._clip_text(self._diff_text(rel, txt, updated), 4000)}"
            )
        return (
            f"replace_text {rel}: OK, Backup: {b}\n"
            f"Test:\n{test_result}\n"
            f"Diff:\n{self._clip_text(self._diff_text(rel, txt, updated), 4000)}"
        )

    def _build_context(self, task, max_total=90000):
        files = self._select_relevant_files(task)
        parts = ["PROJEKTINDEX:\n" + self.project_index()[:16000]]
        total = sum(len(x) for x in parts)

        search_terms = self._task_terms(task)
        if search_terms:
            for term in search_terms[:5]:
                s = self._tool_search_text(term)
                block = f"\n\nSUCHE: {term}\n{s[:9000]}"
                if total + len(block) < max_total:
                    parts.append(block)
                    total += len(block)

        for rel in files:
            block = "\n\n" + self._tool_read_file(rel, allow_3d=self._allow_3d(task))
            if total + len(block) > max_total:
                break
            parts.append(block)
            total += len(block)

        return "\n".join(parts)

    def _select_relevant_files(self, task):
        allow_3d = self._allow_3d(task)
        selected = []
        low = task.lower()

        for rel in self.CORE_FILES:
            if (self.root / rel).exists():
                selected.append(rel)

        explicit = re.findall(r"[\w./\\-]+\.(?:py|bat|ps1|js|html|css|json|md|txt|env|yml|yaml|ini|toml)", task, flags=re.I)
        for m in explicit:
            rel = m.strip("\"'").replace("\\", "/")
            if (self.root / rel).exists():
                selected.append(rel)

        if any(x in low for x in ["antwort", "nicht antwort", "chat", "api/chat", "events"]):
            for rel in ["app.py", "brain.py", "ollama_client.py"]:
                if (self.root / rel).exists():
                    selected.append(rel)

        if any(x in low for x in ["voice", "mikro", "sprache", "jarvis hört", "wakeword", "zuhören"]):
            for rel in ["voice.py", "app.py"]:
                if (self.root / rel).exists():
                    selected.append(rel)

        if any(x in low for x in ["modell", "ollama", "qwen", "coder"]):
            for rel in [".env", "ollama_client.py", "config.py", "System einschalten.bat"]:
                if (self.root / rel).exists():
                    selected.append(rel)

        if allow_3d:
            for rel in ["jarvis_3d_webgl/index.html", "jarvis_3d_webgl/work.html"]:
                if (self.root / rel).exists():
                    selected.append(rel)

        out = []
        for rel in selected:
            if rel not in out:
                out.append(rel)
        return out[:45]

    def _task_terms(self, task):
        base = []
        low = task.lower()
        for term in ["OLLAMA_MODEL", "JARVIS_MODEL", "api/chat", "push_event", "listen_once", "speak_text", "handle", "complete", "qwen3-coder-next"]:
            if term.lower() in low or term in {"OLLAMA_MODEL", "api/chat", "push_event", "listen_once", "complete"}:
                base.append(term)
        words = [w for w in re.findall(r"[A-Za-z0-9_:-]{4,}", task) if len(w) >= 4]
        return (base + words)[:8]

    def _all_code_files(self):
        rows = []
        for p in sorted(self.root.rglob("*")):
            try:
                rel = p.relative_to(self.root)
            except Exception:
                continue
            rels = str(rel).replace("\\", "/")
            if p.is_dir():
                continue
            if self._ignored_path(rels):
                continue
            if p.name == ".env" or p.suffix.lower() in self.CODE_EXTS:
                rows.append(rels)
        return rows

    def _ignored_path(self, rels):
        parts = rels.replace("\\", "/").split("/")
        joined = "/".join(parts)
        for ig in self.IGNORE_DIRS:
            if ig in parts or joined.startswith(ig + "/"):
                return True
        if any(part.startswith(".aider") for part in parts):
            return True
        return False

    def _path_allowed(self, rel, allow_3d=False):
        rel = str(rel).strip().replace("\\", "/").lstrip("/")
        if not rel:
            return False, "leerer Pfad"
        if ".." in Path(rel).parts:
            return False, "unsicherer Pfad"
        if self._ignored_path(rel):
            return False, "geschützter Ordner"
        if rel.startswith("jarvis_3d_webgl/") and not allow_3d:
            return False, "3D geschützt"
        suffix = Path(rel).suffix.lower()
        if Path(rel).name != ".env" and suffix not in self.CODE_EXTS:
            return False, "Dateityp nicht erlaubt"
        try:
            target = (self.root / rel).resolve()
            target.relative_to(self.root)
        except Exception:
            return False, "Pfad außerhalb Projekt"
        return True, "ok"

    def _allow_3d(self, task):
        low = str(task).lower()
        return any(x in low for x in ["3d", "ui", "design", "hologramm", "webgl", "jarvis_3d_webgl", "oberfläche", "oberflaeche"])

    def _ask_model(self, prompt, temperature=0.05, timeout=500):
        if self.ollama is not None:
            try:
                return self.ollama.complete(prompt, model=MODEL, temperature=temperature, ctx=32768, timeout=timeout)
            except TypeError:
                try:
                    return self.ollama.complete(prompt, model=MODEL)
                except Exception as e:
                    return "Ollama/Codex-Fehler: " + str(e)
            except Exception as e:
                return "Ollama/Codex-Fehler: " + str(e)

        try:
            import requests
            payload = {
                "model": MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "options": {"temperature": temperature, "num_ctx": 32768},
            }
            r = requests.post("http://127.0.0.1:11434/api/chat", json=payload, timeout=timeout)
            r.raise_for_status()
            return r.json().get("message", {}).get("content", "").strip()
        except Exception as e:
            return "Ollama/Codex-Fehler: " + str(e)

    def _extract_json(self, raw):
        if not raw:
            return None
        text = raw.strip()
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I).strip()
        text = re.sub(r"\s*```$", "", text).strip()
        try:
            return json.loads(text)
        except Exception:
            pass
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end+1])
            except Exception:
                return None
        return None

    def _validate_files(self, rels):
        py_files = [r for r in rels if str(r).lower().endswith(".py")]
        if not py_files:
            return "Keine Python-Dateien geändert."
        lines = []
        for rel in py_files:
            lines.append(self._tool_run_command({"command": "py_compile", "path": rel}))
        return "\n".join(lines)

    def _has_failed_validation(self, test_result, commands_result):
        checks = [str(test_result or ""), *[str(x or "") for x in commands_result]]
        for line in "\n".join(checks).splitlines():
            low = line.lower()
            if low.startswith("py_compile ") and not low.rstrip().endswith("ok"):
                return True
            if "traceback" in low or "syntaxerror" in low:
                return True
        return False

    def _restore_snapshots(self, snapshots):
        for item in snapshots.values():
            target = item["target"]
            if item["exists"]:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(item["content"], encoding="utf-8")
            elif target.exists():
                target.unlink()

    def _diff_text(self, rel, before, after):
        return "".join(
            difflib.unified_diff(
                str(before or "").splitlines(keepends=True),
                str(after or "").splitlines(keepends=True),
                fromfile=f"a/{rel}",
                tofile=f"b/{rel}",
                n=3,
            )
        ) or f"Keine sichtbare Textaenderung: {rel}\n"

    def _clip_text(self, text, limit=6000):
        text = str(text or "")
        if len(text) <= limit:
            return text
        return text[:limit] + "\n... gekuerzt ..."

    def _write_log(self, kind, task, content):
        try:
            stamp = time.strftime("%Y%m%d_%H%M%S")
            p = self.log_dir / f"{stamp}_{kind}.txt"
            p.write_text(f"TASK:\n{task}\n\nCONTENT:\n{content}", encoding="utf-8", errors="ignore")
        except Exception:
            pass


if __name__ == "__main__":
    try:
        from ollama_client import OllamaClient
        ollama = OllamaClient()
    except Exception:
        ollama = None
    agent = LocalCodexAgent(ollama)
    task = " ".join(os.sys.argv[1:]).strip()
    print(agent.run(task or "status"))
