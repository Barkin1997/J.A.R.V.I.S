import json
import os
import queue
import re
import shutil
import subprocess
import threading
import time
import webbrowser
import zipfile
import hashlib
from pathlib import Path

from config import BASE_DIR
from skills.project_intelligence import ProjectIntelligence
from skills.status_center import StatusCenter
from skills.model_router import ModelRouter


class AiderAgent:
    def __init__(self, root: Path = None):
        self.jarvis_root = Path(root or BASE_DIR).resolve()
        self.log_dir = self.jarvis_root / "data" / "aider_bridge"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.dashboard_file = self.jarvis_root / "data" / "coding_dashboard.json"
        self.model = os.getenv("JARVIS_AIDER_MODEL", "ollama_chat/qwen3-coder-next:latest")
        self.timeout = int(os.getenv("JARVIS_AIDER_TIMEOUT", "600"))
        self.auto_rollback = os.getenv("JARVIS_AIDER_AUTO_ROLLBACK", "1") == "1"
        self.auto_fix_errors = os.getenv("JARVIS_AIDER_AUTO_FIX_ERRORS", "1") == "1"
        self.use_all_code_resources = os.getenv("JARVIS_USE_ALL_CODE_RESOURCES", "1") == "1"
        self.live_window = os.getenv("JARVIS_AIDER_LIVE_WINDOW", "1") == "1"
        self.stuck_warn = int(os.getenv("JARVIS_AIDER_STUCK_WARN", "75"))
        self.browser_smoke_test = os.getenv("JARVIS_BROWSER_SMOKE_TEST", "1") == "1"
        self.codex_focus_files = os.getenv("JARVIS_CODEX_FOCUS_FILES", "1") == "1"
        self.project_intelligence = ProjectIntelligence(self.jarvis_root)
        self.status_center = StatusCenter()
        self.model_router = ModelRouter()
        self.auto_project_tests = os.getenv("JARVIS_AUTO_PROJECT_TESTS", "1") == "1"
        self.retry_no_change = os.getenv("JARVIS_AIDER_RETRY_NO_CHANGE", "1") == "1"
        self.show_readiness = os.getenv("JARVIS_CODING_SHOW_READINESS", "1") == "1"
        self.show_git_diff = os.getenv("JARVIS_CODING_SHOW_GIT_DIFF", "1") == "1"
        self.split_large_tasks = os.getenv("JARVIS_CODING_SPLIT_LARGE_TASKS", "1") == "1"

    def status(self) -> str:
        config = self.jarvis_root / ".aider.conf.yml"
        model_settings = self.jarvis_root / ".aider.model.settings.yml"
        ok = [
            f"Aider-Bruecke aktiv.",
            f"Projekt: {self.jarvis_root}",
            f"Modell: {self.model}",
            f"Config: {'OK' if config.exists() else 'FEHLT'} - {config}",
            f"Model-Settings: {'OK' if model_settings.exists() else 'FEHLT'} - {model_settings}",
        ]
        return "\n".join(ok)

    def error_database(self, path_text: str = "") -> str:
        root = self._resolve_root(path_text)
        if not root.exists() or not root.is_dir():
            return f"Fehlerdatenbank: Projektordner nicht gefunden: {root}"
        return self.project_intelligence.error_report(root)

    def project_memory_status(self, path_text: str = "", task: str = "") -> str:
        root = self._resolve_root(path_text)
        if not root.exists() or not root.is_dir():
            return f"Projekt-Gedaechtnis: Projektordner nicht gefunden: {root}"
        return self.project_intelligence.project_report(root, task)

    def ask(self, path_text: str, question: str) -> str:
        root = self._resolve_root(path_text)
        if not root.exists() or not root.is_dir():
            return f"Aider: Projektordner nicht gefunden: {root}"
        question = self._expand_followup_task(root, question)
        codex_plan = self.project_intelligence.codex_plan(root, question, allow_write=False)
        focus_files = self.project_intelligence.focus_files(root, question)
        prompt = self._build_prompt(root, question, allow_write=False, codex_plan=codex_plan, focus_files=focus_files)
        return self._run_aider(root, prompt, dry_run=True, task_text=question, codex_plan=codex_plan, focus_files=focus_files)

    def modify(self, path_text: str, task: str) -> str:
        root = self._resolve_root(path_text)
        if not root.exists() or not root.is_dir():
            return f"Aider: Projektordner nicht gefunden: {root}"
        task = self._expand_followup_task(root, task)
        codex_plan = self.project_intelligence.codex_plan(root, task, allow_write=True)
        focus_files = self.project_intelligence.focus_files(root, task)
        prompt = self._build_prompt(root, task, allow_write=True, codex_plan=codex_plan, focus_files=focus_files)
        return self._run_aider(root, prompt, dry_run=False, task_text=task, codex_plan=codex_plan, focus_files=focus_files)

    def run_command(self, command: str) -> str:
        task = re.sub(r"^(aider|aider modus|aider-mode)[:,]?\s*", "", command or "", flags=re.I).strip()
        if not task or task.lower() in {"status", "hilfe", "help", "modus"}:
            return self.status()
        low = task.lower()
        if any(x in low for x in ["analysiere", "analyse", "pruefe", "prüfe", "review", "frage", "was kann", "was fehlt"]):
            return self.ask("", task)
        return self.modify("", task)

    def _aider_job_lock_path(self) -> Path:
        data_dir = self.jarvis_root / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        return data_dir / "aider_job.lock"

    def _acquire_aider_job(self, root: Path, dry_run: bool, task_text: str):
        lock = self._aider_job_lock_path()
        if lock.exists():
            age = max(0, int(time.time() - lock.stat().st_mtime))
            if age > max(900, self.timeout * 2):
                try:
                    lock.unlink()
                except Exception:
                    pass
            else:
                mode = "Analyse" if dry_run else "Aenderung"
                return (
                    "Coding laeuft bereits.\n"
                    f"Aktiver Job seit {age}s: {lock}\n"
                    f"Neuer Auftrag ({mode}) wurde nicht gestartet, damit nichts doppelt laeuft."
                )
        info = {
            "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "root": str(root),
            "mode": "analyse" if dry_run else "modify",
            "task": (task_text or "")[:500],
            "model": self.model,
        }
        try:
            fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(info, f, ensure_ascii=False, indent=2)
            return lock
        except FileExistsError:
            return f"Coding laeuft bereits: {lock}"
        except Exception as e:
            return f"Coding-Lock konnte nicht erstellt werden: {e}"

    def _release_aider_job(self, lock: Path) -> None:
        try:
            if lock and lock.exists():
                lock.unlink()
        except Exception:
            pass

    def _resolve_root(self, text: str) -> Path:
        text = (text or "").strip().strip('"')
        if not text:
            return self.jarvis_root
        p = Path(text).expanduser()
        if not p.is_absolute():
            p = self.jarvis_root / p
        return p.resolve()

    def _build_prompt(self, root: Path, task: str, allow_write: bool, codex_plan: str = "", focus_files=None) -> str:
        mode = "AENDERN ERLAUBT" if allow_write else "NUR ANALYSE, NICHTS AENDERN"
        project_context = self.project_intelligence.context_for(root, task, allow_write)
        focus_text = ", ".join((focus_files or [])[:12]) or "keine sicheren Fokus-Dateien erkannt"
        task_breakdown = self._task_breakdown(task, allow_write)
        action = (
            "Setze die Aufgabe wirklich um. Plane kurz, aendere nur noetige Dateien, danach Diff/Test zusammenfassen."
            if allow_write
            else "Keine Dateien aendern. Nur Plan, Befunde und konkrete Vorschlaege ausgeben."
        )
        return (
            f"Du arbeitest als Aider im Jarvis-Projekt.\n"
            f"Projektordner: {root}\n"
            f"Modus: {mode}\n"
            f"Regeln:\n"
            f"- Antworte auf Deutsch.\n"
            f"- Arbeite gezielt und klein.\n"
            f"- Arbeite wie ein Coding-Assistent: Auftrag verstehen, Plan bilden, Dateien pruefen, dann erst aendern.\n"
            f"- Wenn der Nutzer eine Aenderung verlangt, liefere echte Datei-Aenderungen. Nicht nur erklaeren, nicht nur vorschlagen.\n"
            f"- Wenn der Nutzer 'Nummer 1/2/3' sagt, nimm die letzte gespeicherte Projekt-/Chat-Aufgabe als Kontext und setze genau diesen Punkt um.\n"
            f"- Wenn du keine Datei aenderst, obwohl AENDERN ERLAUBT ist, erklaere den harten Grund und welche konkrete Datei fehlt.\n"
            f"- Nutze alle Jarvis-Coding-Ressourcen: Projekt-Gedaechtnis, Fehlerdatenbank, Fokus-Dateien, Internet-/Doku-Kontext, Tests, Browser-Smoke-Test, Diff, Backup und Rollback.\n"
            f"- Bei grossen Aufgaben arbeite in kleinen sicheren Schritten: erst relevante Dateien, dann Patch, dann Test, dann naechster Schritt.\n"
            f"- Fokus-Dateien fuer diesen Auftrag: {focus_text}.\n"
            f"- Wenn diese Fokus-Dateien nicht reichen, suche gezielt nach Symbolen/Dateinamen statt den ganzen Ordner blind zu lesen.\n"
            f"- Wenn du etwas nicht umsetzen kannst, sage klar warum und wiederhole nicht nur alte Vorschlaege.\n"
            f"- Ignoriere Logs, Backups, .aider*, __pycache__, models, external und Browserdaten.\n"
            f"- jarvis_3d_webgl nur aendern, wenn die Aufgabe ausdruecklich 3D/Hologramm/UI/Design sagt.\n"
            f"- Keine Git-Resets, keine Loeschaktionen ausser der Nutzer verlangt exakt diese Datei.\n"
            f"- Bei Web/Spiel-Projekten pruefe, dass index.html/style.css/script.js zusammenpassen und Start/Neustart funktionieren.\n"
            f"- Bei eigenem oder autorisiertem Spieltesting sind Debug-/Cheat-Menues, Admin-Kommandos, Test-Bots, lokale Test-Clients, Exploit-Simulationen und Anti-Cheat-Testfaelle im eigenen Projekt erlaubt.\n"
            f"- Wenn ein Auftrag fremde Spiele/Server, fremde Accounts, Malware, Credentialdiebstahl oder Anti-Cheat-Bypass gegen Drittanbieter meint, baue stattdessen eine sichere Test-/Debug-Variante fuer das eigene Projekt.\n"
            f"- Zitiere keine langen Nutzungsbedingungen. Wenn etwas nicht geht, sage es kurz und biete direkt die erlaubte Test-Alternative an.\n"
            f"- {action}\n\n"
            f"{task_breakdown}\n\n"
            f"{codex_plan}\n\n"
            f"{project_context}\n\n"
            f"AUFGABE:\n{task}\n"
        )

    def _build_auto_fix_prompt(self, root: Path, original_task: str, failure_summary: str, codex_plan: str = "", focus_files=None) -> str:
        focus_text = ", ".join((focus_files or [])[:12]) or "per gezielter Suche ermitteln"
        profile = self.project_intelligence.profile(root)
        tests = ", ".join(profile.get("test_commands", [])[:4]) or "passende Syntax-/Projektpruefung"
        return (
            "Du bist im automatischen Jarvis-Fehlerbehebungsmodus.\n"
            f"Projektordner: {root}\n"
            "Ziel: Der vorherige Coding-Auftrag hat Fehler verursacht oder Tests sind fehlgeschlagen. "
            "Behebe jetzt gezielt die echte Ursache.\n\n"
            "REGELN:\n"
            "- Wiederhole nicht nur Vorschlaege. Repariere den Fehler wirklich.\n"
            "- Nutze den im Originalauftrag enthaltenen Internet-/Doku-Kontext, falls vorhanden.\n"
            "- Nutze alle Jarvis-Coding-Ressourcen: Projekt-Gedaechtnis, Fehlerdatenbank, Fokus-Dateien, Tests, Browser-Smoke-Test, Diff, Backup und Rollback.\n"
            "- Wenn Bibliotheken/APIs/Versionen betroffen sind, beachte den Internet-/Doku-Kontext besonders.\n"
            "- Pruefe zuerst die Fokus-Dateien und die konkrete Fehlerausgabe.\n"
            "- Aendere nur Dateien, die fuer die Reparatur noetig sind.\n"
            "- Keine Logs, Backups, models, external oder generierte Projektordner durchsuchen.\n"
            "- Nach der Reparatur muss ein passender Test/Syntaxcheck beschrieben oder ausgefuehrt werden.\n"
            "- Wenn der Fehler extern ist, sage kurz was fehlt und baue keinen Fake-Erfolg.\n\n"
            f"Fokus-Dateien: {focus_text}\n"
            f"Empfohlene Tests: {tests}\n\n"
            f"{codex_plan}\n\n"
            f"ORIGINALAUFGABE:\n{self._clip(original_task, 5000)}\n\n"
            f"FEHLER / TESTAUSGABE:\n{self._clip(failure_summary, 6000)}\n\n"
            "AUFGABE JETZT:\n"
            "Repariere den Fehler, pruefe die Aenderung und fasse Diff/Test kurz zusammen.\n"
        )

    def _readiness_summary(self) -> str:
        try:
            text = self.status_center.check()
            lines = []
            capture = False
            for line in text.splitlines():
                if line.strip() == "STATUS-AMPEL:":
                    capture = True
                    continue
                if capture and line.strip() == "DETAILS:":
                    break
                if capture and line.strip():
                    lines.append(line)
            return "\n".join(lines).strip() or "Status-Ampel nicht verfuegbar."
        except Exception as e:
            return f"Status-Ampel nicht verfuegbar: {e}"

    def _write_dashboard(
        self,
        state: str,
        root: Path,
        task: str,
        dry_run: bool,
        live_file: Path,
        log_file: Path,
        backup_file: str = "",
        readiness: str = "",
        focus_files=None,
        changed_files=None,
        diff: str = "",
        tests: str = "",
        summary: str = "",
        rollback: str = "",
        preview: str = "",
    ) -> None:
        data = {
            "updated_at": time.time(),
            "state": state,
            "mode": "analyse" if dry_run else "coding",
            "root": str(root),
            "task": task or "",
            "model": self.model,
            "readiness": readiness or "",
            "focus_files": list(focus_files or [])[:20],
            "changed_files": list(changed_files or [])[:80],
            "diff": self._clip(diff or "", 14000),
            "tests": self._clip(tests or "", 9000),
            "summary": self._clip(summary or "", 9000),
            "rollback": self._clip(rollback or "", 4000),
            "preview": preview or "",
            "backup_file": str(backup_file or ""),
            "live_file": str(live_file),
            "log_file": str(log_file),
        }
        try:
            self.dashboard_file.parent.mkdir(parents=True, exist_ok=True)
            self.dashboard_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _task_breakdown(self, task: str, allow_write: bool) -> str:
        if not allow_write or not self.split_large_tasks:
            return ""
        low = (task or "").lower()
        is_large = len(task or "") > 280 or any(word in low for word in [
            "alles", "komplett", "ganze", "vollstaendig",
            "gross", "grosse", "system", "dashboard",
            "studio", "mehrere", "viele", "perfekt", "alles rein",
        ])
        if not is_large:
            return (
                "KLEINER CODING-ABLAUF:\n"
                "1. Relevante Dateien finden.\n"
                "2. Kleine Aenderung umsetzen.\n"
                "3. Diff und Tests ausfuehren.\n"
            )
        return (
            "GROSSE AUFGABE WIRD AUTOMATISCH IN SICHERE SCHRITTE GETEILT:\n"
            "1. Ziel und Fokus-Dateien bestimmen.\n"
            "2. Nur den naechsten sinnvollen Teil patchen.\n"
            "3. Diff anzeigen.\n"
            "4. Passende Tests/Browser-Pruefung starten.\n"
            "5. Bei Fehlern automatisch Reparaturversuch, sonst fertig melden.\n"
            "6. Weitere grosse Teile erst im naechsten Auftrag oder Folge-Schritt fortsetzen.\n"
        )

    def _changed_files_from_hashes(self, root: Path, before_hashes: dict):
        if not before_hashes:
            return []
        after_hashes = self._snapshot_file_hashes(root)
        before_keys = set(before_hashes)
        after_keys = set(after_hashes)
        created = sorted(after_keys - before_keys)
        deleted = sorted(before_keys - after_keys)
        modified = sorted(rel for rel in (before_keys & after_keys) if before_hashes.get(rel) != after_hashes.get(rel))
        rows = []
        rows.extend(f"geaendert: {rel}" for rel in modified)
        rows.extend(f"neu: {rel}" for rel in created)
        rows.extend(f"entfernt: {rel}" for rel in deleted)
        return rows

    def _run_aider(self, root: Path, prompt: str, dry_run: bool, task_text: str = "", codex_plan: str = "", focus_files=None) -> str:
        lock = self._acquire_aider_job(root, dry_run, task_text)
        if not isinstance(lock, Path):
            return lock
        previous_model = self.model
        self.model = self._aider_model_for_task(task_text, allow_write=not dry_run)
        try:
            return self._run_aider_inner(root, prompt, dry_run, task_text, codex_plan, focus_files, auto_fix_attempt=False)
        finally:
            self.model = previous_model
            self._release_aider_job(lock)

    def _aider_model_for_task(self, task_text: str, allow_write: bool) -> str:
        if os.getenv("JARVIS_MODEL_ROUTER", "1") != "1":
            return self.model
        chosen = self.model_router.choose(task_text, mode="coding" if allow_write else "chat")
        if chosen.startswith(("ollama_chat/", "ollama/", "openai/", "anthropic/")):
            return chosen
        return "ollama_chat/" + chosen

    def _run_aider_inner(self, root: Path, prompt: str, dry_run: bool, task_text: str = "", codex_plan: str = "", focus_files=None, auto_fix_attempt: bool = False) -> str:
        stamp = time.strftime("%Y%m%d_%H%M%S")
        msg_file = self.log_dir / f"{stamp}_prompt.txt"
        live_file = self.log_dir / f"{stamp}_live.txt"
        log_file = self.log_dir / f"{stamp}_result.txt"
        msg_file.write_text(prompt, encoding="utf-8")

        started = time.time()
        before_status = self._git_status(root)
        before_files = self._snapshot_safe_files(root) if not dry_run else set()
        before_hashes = self._snapshot_file_hashes(root) if not dry_run else {}
        backup_file = self._backup_safe_files(root, stamp, before_files) if not dry_run else ""
        readiness = self._readiness_summary() if self.show_readiness else ""
        self._write_dashboard(
            state="running",
            root=root,
            task=task_text,
            dry_run=dry_run,
            live_file=live_file,
            log_file=log_file,
            backup_file=backup_file,
            readiness=readiness,
            focus_files=focus_files or [],
            summary="Aider/Codex startet.",
        )
        cmd = [
            "aider",
            "--config",
            str(self.jarvis_root / ".aider.conf.yml"),
            "--message-file",
            str(msg_file),
            "--model",
            self.model,
            "--no-pretty",
            "--no-auto-commits",
            "--no-dirty-commits",
            "--no-suggest-shell-commands",
            "--no-show-model-warnings",
            "--no-check-update",
            "--no-fancy-input",
            "--no-detect-urls",
            "--no-gitignore",
            "--encoding",
            "utf-8",
        ]
        if dry_run:
            cmd.append("--dry-run")
        aider_files = self._aider_focus_args(root, focus_files or [], task_text)
        cmd.extend(aider_files)

        env = os.environ.copy()
        env.setdefault("OLLAMA_API_BASE", "http://127.0.0.1:11434")
        env.setdefault("PYTHONIOENCODING", "utf-8")
        self._prepare_live_log(live_file, root, task_text, dry_run, cmd, codex_plan, focus_files or [], readiness)
        if not dry_run:
            self._minimize_external_coding_windows()
        if self.live_window:
            self._open_live_window(live_file, dry_run)
            if not dry_run:
                self._minimize_external_coding_windows()

        try:
            result = self._run_aider_live(
                cmd,
                root=root,
                env=env,
                live_file=live_file,
                started=started,
            )
        except subprocess.TimeoutExpired:
            self._append_live(
                live_file,
                "\n\nZEITLIMIT ERREICHT.\n"
                "Der Auftrag wurde sauber abgebrochen. Jarvis hat keine halbfertige Aider-Antwort uebernommen.\n"
                "Naechster Versuch: Auftrag automatisch kleiner machen oder eine konkrete Datei nennen.\n",
            )
            self.project_intelligence.remember_result(
                root,
                task_text,
                f"Aider-Zeitlimit nach {self.timeout}s mit Modell {self.model}",
                False,
            )
            self._write_dashboard(
                state="timeout",
                root=root,
                task=task_text,
                dry_run=dry_run,
                live_file=live_file,
                log_file=log_file,
                backup_file=backup_file,
                readiness=readiness,
                focus_files=focus_files or [],
                summary=f"Zeitlimit nach {self.timeout}s erreicht.",
            )
            return (
                "Aider-Fehler: Zeitlimit erreicht. Der Auftrag wurde abgebrochen.\n"
                f"Modell: {self.model}\n"
                "Jarvis hat den Fehler in der Fehlerdatenbank gespeichert.\n"
                "Tipp: Auftrag kleiner machen oder nur eine Datei nennen."
            )
        except FileNotFoundError:
            self._write_dashboard(
                state="error",
                root=root,
                task=task_text,
                dry_run=dry_run,
                live_file=live_file,
                log_file=log_file,
                backup_file=backup_file,
                readiness=readiness,
                focus_files=focus_files or [],
                summary="aider.exe wurde nicht gefunden.",
            )
            return "Aider-Fehler: aider.exe wurde nicht gefunden."
        except Exception as e:
            self._write_dashboard(
                state="error",
                root=root,
                task=task_text,
                dry_run=dry_run,
                live_file=live_file,
                log_file=log_file,
                backup_file=backup_file,
                readiness=readiness,
                focus_files=focus_files or [],
                summary=f"Aider-Fehler: {e}",
            )
            return f"Aider-Fehler: {e}"

        after_status = self._git_status(root)
        codex_changes = "" if dry_run else self._codex_change_report(root, before_hashes)
        git_diff = "" if dry_run or not self.show_git_diff else self._git_diff_report(root, before_hashes)
        verify = "" if dry_run else self._verify_changed_python(root)
        web_verify = "" if dry_run else self._verify_changed_web(root)
        project_verify = "" if dry_run else self._verify_project_profile(root)
        test_gate = self._test_gate_report(verify, web_verify, project_verify, dry_run)
        rollback = ""
        has_verify_error = (
            "FEHLER:" in (verify or "")
            or "FEHLER:" in (web_verify or "")
            or "FEHLER:" in (project_verify or "")
        )
        if not dry_run and self.auto_rollback and backup_file and (result.returncode != 0 or has_verify_error):
            rollback = self._restore_backup(root, backup_file, before_files)
            after_status = self._git_status(root)
        preview = ""
        if not dry_run and result.returncode == 0 and self._wants_browser_preview(task_text):
            preview = self._open_browser_preview(root, before_status, after_status, started)
        output = ((result.stdout or "") + "\n" + (result.stderr or "")).strip()
        log_file.write_text(output, encoding="utf-8", errors="ignore")
        self._append_live(live_file, "\n\n--- JARVIS PRUEFUNG ---\n")
        if verify:
            self._append_live(live_file, verify + "\n")
        if web_verify:
            self._append_live(live_file, web_verify + "\n")
        if project_verify:
            self._append_live(live_file, project_verify + "\n")
        if rollback:
            self._append_live(live_file, "ROLLBACK:\n" + rollback + "\n")
        if codex_changes:
            self._append_live(live_file, "CODEX-DIFF:\n" + codex_changes + "\n")
        if git_diff:
            self._append_live(live_file, "GIT-DIFF:\n" + git_diff + "\n")
        if test_gate:
            self._append_live(live_file, test_gate + "\n")
        self._append_live(live_file, "\nFERTIG.\n")
        no_text_changes = (not codex_changes) or codex_changes.startswith("Keine Text-/Code-Datei")
        success = result.returncode == 0 and not has_verify_error and not rollback
        no_change_error = (
            self.retry_no_change
            and not dry_run
            and result.returncode == 0
            and not has_verify_error
            and not rollback
            and before_status == after_status
            and no_text_changes
            and self._looks_like_modify_task(task_text)
        )
        if no_change_error:
            success = False
        result_summary = "\n".join(
            part for part in [
                f"Exit-Code: {result.returncode}",
                output[:3000] if output else "",
                codex_changes or "",
                git_diff or "",
                verify or "",
                web_verify or "",
                project_verify or "",
                test_gate or "",
                rollback or "",
            ] if part
        )
        self.project_intelligence.remember_result(root, task_text, result_summary or "OK", success)
        self._write_dashboard(
            state="done" if success else ("no_change" if no_change_error else "error"),
            root=root,
            task=task_text,
            dry_run=dry_run,
            live_file=live_file,
            log_file=log_file,
            backup_file=backup_file,
            readiness=readiness,
            focus_files=focus_files or [],
            changed_files=self._changed_files_from_hashes(root, before_hashes) if not dry_run else [],
            diff=git_diff or codex_changes,
            tests="\n".join(part for part in [verify, web_verify, project_verify, test_gate] if part),
            summary=result_summary or "OK",
            rollback=rollback,
            preview=preview,
        )

        parts = [
            "Aider fertig." if result.returncode == 0 else f"Aider beendet mit Fehlercode {result.returncode}.",
            f"Modell: {self.model}",
            f"Modus: {'Analyse ohne Schreiben' if dry_run else 'Aendern erlaubt'}",
        ]
        if readiness:
            parts.append("Bereitschaft vor Start:\n" + readiness)
        if output:
            parts.append("Ausgabe:\n" + self._clip(output, 9000))
        if before_status != after_status:
            parts.append("Git-Status vorher:\n" + (before_status or "<leer>"))
            parts.append("Git-Status nachher:\n" + (after_status or "<leer>"))
        elif not dry_run and result.returncode == 0:
            parts.append("Ich habe nichts geaendert: Git-Status ist unveraendert. Falls du eine echte Aenderung wolltest, Auftrag genauer auf Datei/Funktion beziehen.")
        if no_change_error:
            parts.append(
                "Jarvis-Waechter: Der Auftrag sah nach echter Code-Aenderung aus, aber es wurde keine Datei geaendert. "
                "Ich werte das als nicht fertig und starte eine gezielte zweite Runde."
            )
        if backup_file:
            parts.append(f"Rollback-Backup: {backup_file}")
        if codex_changes:
            parts.append("Codex-Diff:\n" + codex_changes)
        if git_diff:
            parts.append("Git-Diff:\n" + git_diff)
        if verify:
            parts.append("Pruefung:\n" + verify)
        if web_verify:
            parts.append("Web-Pruefung:\n" + web_verify)
        if project_verify:
            parts.append("Projekt-Pruefung:\n" + project_verify)
        if test_gate:
            parts.append(test_gate)
        if rollback:
            parts.append("Rollback:\n" + rollback)
        if preview:
            parts.append(preview)
        parts.append(f"Live-Log: {live_file}")
        parts.append(f"Log: {log_file}")
        final_text = "\n\n".join(parts).strip()
        if self.auto_fix_errors and not dry_run and not success and not auto_fix_attempt:
            if no_change_error:
                result_summary = (result_summary + "\n\nJARVIS-WAECHTER: Keine Datei geaendert, obwohl der Auftrag eine Aenderung verlangt.").strip()
            repair_prompt = self._build_auto_fix_prompt(root, task_text, result_summary, codex_plan, focus_files or [])
            self._append_live(
                live_file,
                "\n\nAUTO-REPARATUR STARTET.\n"
                "Jarvis nutzt Fehlerausgabe, Diff/Test und den vorhandenen Internet-/Doku-Kontext fuer einen gezielten zweiten Versuch.\n",
            )
            repair_result = self._run_aider_inner(
                root,
                repair_prompt,
                dry_run=False,
                task_text="AUTO-REPARATUR: " + (task_text or ""),
                codex_plan=codex_plan,
                focus_files=focus_files or [],
                auto_fix_attempt=True,
            )
            return (
                final_text
                + "\n\nAUTO-REPARATUR WURDE GESTARTET\n\n"
                + repair_result
            ).strip()
        return final_text

    def _prepare_live_log(self, live_file: Path, root: Path, task_text: str, dry_run: bool, cmd, codex_plan: str = "", focus_files=None, readiness: str = "") -> None:
        mode = "ANALYSE" if dry_run else "CODING"
        profile = self.project_intelligence.profile(root)
        focus_text = ", ".join((focus_files or [])[:10]) or "keine"
        task_breakdown = self._task_breakdown(task_text, not dry_run)
        header = [
            "JARVIS LIVE",
            f"Modus: {mode}",
            f"Projekt: {root}",
            f"Modell: {self.model}",
            f"Projekttyp: {profile.get('type', 'unbekannt')}",
            f"Sprachen: {', '.join(profile.get('languages', [])) or 'unbekannt'}",
            f"Tests: {', '.join(profile.get('test_commands', [])[:4]) or 'Basispruefung'}",
            f"Fokus-Dateien: {focus_text}",
            f"Auftrag: {task_text or '<kein Text>'}",
            "",
            "BEREITSCHAFT:",
            readiness or "Status-Ampel wird nicht angezeigt.",
            "",
            task_breakdown,
            "",
            codex_plan or "CODEX-AUFGABENPLAN: wird aus dem Projektkontext abgeleitet.",
            "",
            "Internet/Doku-Kontext: wird vom Jarvis-Brain vor dem Agentenauftrag ergaenzt.",
            "Fehlerdatenbank: wird geladen und nach dem Auftrag aktualisiert.",
            "Aider startet...",
            "----------------------------------------",
            "",
        ]
        live_file.write_text("\n".join(header), encoding="utf-8", errors="ignore")

    def _append_live(self, live_file: Path, text: str) -> None:
        try:
            with live_file.open("a", encoding="utf-8", errors="ignore") as f:
                f.write(text)
                if text and not text.endswith("\n"):
                    f.write("\n")
        except Exception:
            pass

    def _open_live_window(self, live_file: Path, dry_run: bool) -> None:
        if os.name != "nt":
            return
        title = "JARVIS ANALYSE LIVE" if dry_run else "JARVIS CODING LIVE"
        script_file = live_file.with_suffix(".ps1")
        safe_title = title.replace('"', "'")
        safe_path = str(live_file).replace('"', '`"')
        script = (
            f'$host.UI.RawUI.WindowTitle = "{safe_title}"\n'
            "Clear-Host\n"
            f'Write-Host "{safe_title}" -ForegroundColor Cyan\n'
            f'Write-Host "Live-Datei: {safe_path}"\n'
            'Write-Host ""\n'
            "try { (New-Object -ComObject WScript.Shell).AppActivate($host.UI.RawUI.WindowTitle) | Out-Null } catch {}\n"
            f'Get-Content -LiteralPath "{safe_path}" -Wait\n'
        )
        try:
            script_file.write_text(script, encoding="utf-8", errors="ignore")
            start_command = (
                f'start "{title}" /MIN powershell.exe -NoExit -NoProfile '
                f'-ExecutionPolicy Bypass -File "{script_file}"'
            )
            subprocess.Popen(["cmd.exe", "/c", start_command], cwd=str(self.jarvis_root))
        except Exception:
            try:
                subprocess.Popen(
                    ["powershell.exe", "-NoExit", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script_file)],
                    cwd=str(self.jarvis_root),
                    creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0),
                )
            except Exception:
                pass

    def _minimize_external_coding_windows(self) -> None:
        if os.name != "nt" or os.getenv("JARVIS_MINIMIZE_CODING_WINDOWS", "1") != "1":
            return
        script = r'''
$ErrorActionPreference = 'SilentlyContinue'
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class WinApi {
  [DllImport("user32.dll")]
  public static extern bool ShowWindowAsync(IntPtr hWnd, int nCmdShow);
}
"@
$targets = Get-Process | Where-Object {
  $_.MainWindowHandle -ne 0 -and (
    $_.ProcessName -match '^(Code|VSCodium)$' -or
    $_.MainWindowTitle -match 'Roo|Roo Code|Visual Studio Code|JARVIS CODING LIVE|JARVIS ANALYSE LIVE|JARVIS Arbeitet Live'
  )
}
foreach($p in $targets){
  [WinApi]::ShowWindowAsync($p.MainWindowHandle, 6) | Out-Null
}
'''
        try:
            subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
                capture_output=True,
                text=True,
                timeout=5,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except Exception:
            pass

    def _run_aider_live(self, cmd, root: Path, env, live_file: Path, started: float):
        output_queue = queue.Queue()
        output_lines = []
        process = subprocess.Popen(
            cmd,
            cwd=str(root),
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )

        def read_output():
            try:
                for line in process.stdout:
                    output_queue.put(line)
            finally:
                output_queue.put(None)

        reader = threading.Thread(target=read_output, daemon=True)
        reader.start()
        stream_done = False
        last_output_at = time.time()
        last_stuck_note = 0
        while True:
            try:
                item = output_queue.get(timeout=0.2)
                if item is None:
                    stream_done = True
                else:
                    output_lines.append(item)
                    self._append_live(live_file, item)
                    last_output_at = time.time()
            except queue.Empty:
                pass

            silent_for = time.time() - last_output_at
            if self.stuck_warn > 0 and silent_for > self.stuck_warn and time.time() - last_stuck_note > self.stuck_warn:
                last_stuck_note = time.time()
                elapsed = int(time.time() - started)
                self._append_live(
                    live_file,
                    f"\n[JARVIS] Aider arbeitet noch. Laufzeit: {elapsed}s, kein neuer Output seit {int(silent_for)}s.\n",
                )

            if time.time() - started > self.timeout:
                self._kill_process_tree(process)
                raise subprocess.TimeoutExpired(cmd, self.timeout, output="".join(output_lines))

            if process.poll() is not None and stream_done:
                break

        return subprocess.CompletedProcess(cmd, process.returncode, "".join(output_lines), "")

    def _kill_process_tree(self, process) -> None:
        try:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(process.pid)],
                    capture_output=True,
                    text=True,
                    timeout=15,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
            else:
                process.kill()
        except Exception:
            try:
                process.kill()
            except Exception:
                pass

    def _git_status(self, root: Path) -> str:
        try:
            result = subprocess.run(
                ["git", "status", "--short"],
                cwd=str(root),
                text=True,
                capture_output=True,
                timeout=20,
                encoding="utf-8",
                errors="replace",
            )
            return (result.stdout or result.stderr or "").strip()
        except Exception:
            return ""

    def _snapshot_safe_files(self, root: Path):
        safe_suffixes = {
            ".py", ".js", ".ts", ".tsx", ".jsx", ".html", ".htm", ".css", ".json",
            ".md", ".txt", ".bat", ".ps1", ".yml", ".yaml", ".toml", ".ini", ".env",
        }
        blocked = {
            ".git", ".venv", "__pycache__", ".aider.tags.cache.v4", "logs", "data",
            "models", "external", "project_backups", "codex_backups", "sandbox_runs",
            "comfyui_workflows", "comfyui_video_workflows", "jarvis_projects",
        }
        files = set()
        try:
            for current, dirs, names in os.walk(root):
                dirs[:] = [d for d in dirs if d.lower() not in blocked]
                current_path = Path(current)
                if not self._is_relative_to(current_path.resolve(), root.resolve()):
                    continue
                for name in names:
                    path = current_path / name
                    if path.suffix.lower() not in safe_suffixes:
                        continue
                    try:
                        if path.stat().st_size > 2_000_000:
                            continue
                        rel = path.resolve().relative_to(root.resolve()).as_posix()
                    except Exception:
                        continue
                    files.add(rel)
        except Exception:
            pass
        return files

    def _aider_focus_args(self, root: Path, focus_files, task_text: str):
        if not self.codex_focus_files:
            return []
        low_task = (task_text or "").lower()
        broad_create = any(x in low_task for x in [
            "neues projekt", "neue app", "neue webseite", "neues spiel",
            "erstelle ein spiel", "erstelle eine webseite", "komplett neu",
        ])
        if broad_create:
            return []
        args = []
        for rel in (focus_files or [])[:8]:
            try:
                path = (root / rel).resolve()
                if not self._is_relative_to(path, root.resolve()):
                    continue
                if not path.exists() or not path.is_file():
                    continue
                if path.stat().st_size > 1_000_000:
                    continue
                args.append(str(path))
            except Exception:
                continue
        return args

    def _snapshot_file_hashes(self, root: Path):
        hashes = {}
        for rel in self._snapshot_safe_files(root):
            path = root / rel
            try:
                h = hashlib.sha1()
                with path.open("rb") as f:
                    for chunk in iter(lambda: f.read(65536), b""):
                        h.update(chunk)
                hashes[rel] = h.hexdigest()
            except Exception:
                continue
        return hashes

    def _codex_change_report(self, root: Path, before_hashes: dict) -> str:
        if not before_hashes:
            return ""
        after_hashes = self._snapshot_file_hashes(root)
        before_keys = set(before_hashes)
        after_keys = set(after_hashes)
        created = sorted(after_keys - before_keys)
        deleted = sorted(before_keys - after_keys)
        modified = sorted(rel for rel in (before_keys & after_keys) if before_hashes.get(rel) != after_hashes.get(rel))
        lines = [
            f"Snapshot-Diff: {len(modified)} geaendert, {len(created)} neu, {len(deleted)} entfernt"
        ]
        if modified:
            lines.append("Geaendert:")
            lines.extend(f"- {rel}" for rel in modified[:30])
        if created:
            lines.append("Neu:")
            lines.extend(f"- {rel}" for rel in created[:30])
        if deleted:
            lines.append("Entfernt:")
            lines.extend(f"- {rel}" for rel in deleted[:30])
        if len(lines) == 1 and not (modified or created or deleted):
            return "Keine Text-/Code-Datei wurde durch diesen Auftrag veraendert."
        if len(modified) + len(created) + len(deleted) > 90:
            lines.append("... weitere Dateien gekuerzt ...")
        stat = self._git_diff_stat(root, modified + created + deleted)
        if stat:
            lines.append("")
            lines.append("Diff-Stat:")
            lines.append(stat)
        return "\n".join(lines)

    def _git_diff_report(self, root: Path, before_hashes: dict) -> str:
        if not before_hashes:
            return ""
        after_hashes = self._snapshot_file_hashes(root)
        before_keys = set(before_hashes)
        after_keys = set(after_hashes)
        created = sorted(after_keys - before_keys)
        deleted = sorted(before_keys - after_keys)
        modified = sorted(rel for rel in (before_keys & after_keys) if before_hashes.get(rel) != after_hashes.get(rel))
        if not (created or deleted or modified):
            return "Git-Diff: Ich habe nichts geaendert."

        lines = ["Git-Diff (Auszug):"]
        tracked_modified = [rel for rel in modified if (root / rel).exists()]
        if tracked_modified:
            try:
                result = subprocess.run(
                    ["git", "diff", "--no-color", "--", *tracked_modified[:20]],
                    cwd=str(root),
                    text=True,
                    capture_output=True,
                    timeout=30,
                    encoding="utf-8",
                    errors="replace",
                )
                diff_text = (result.stdout or result.stderr or "").strip()
                if diff_text:
                    lines.append(self._clip(diff_text, 12000))
            except Exception as e:
                lines.append(f"Git-Diff fuer geaenderte Dateien nicht verfuegbar: {e}")

        for rel in created[:8]:
            path = root / rel
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
                lines.append(f"Neue Datei: {rel}\n" + self._clip(text, 2500))
            except Exception:
                lines.append(f"Neue Datei: {rel}")

        if deleted:
            lines.append("Entfernt:\n" + "\n".join(f"- {rel}" for rel in deleted[:20]))

        if len(lines) == 1:
            lines.append("Kein Git-Patch sichtbar. Vermutlich untracked Dateien; Snapshot-Diff oben ist verbindlich.")
        return "\n\n".join(lines)

    def _git_diff_stat(self, root: Path, files) -> str:
        existing = []
        for rel in files[:40]:
            path = root / rel
            if path.exists():
                existing.append(rel)
        if not existing:
            return ""
        try:
            result = subprocess.run(
                ["git", "diff", "--stat", "--", *existing],
                cwd=str(root),
                text=True,
                capture_output=True,
                timeout=20,
                encoding="utf-8",
                errors="replace",
            )
            return (result.stdout or result.stderr or "").strip()[:2500]
        except Exception:
            return ""

    def _backup_safe_files(self, root: Path, stamp: str, files) -> str:
        if not files:
            return ""
        backup_dir = self.jarvis_root / "project_backups" / "aider"
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup_file = backup_dir / f"aider_backup_{stamp}.zip"
        count = 0
        try:
            with zipfile.ZipFile(backup_file, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                for rel in sorted(files):
                    path = root / rel
                    if path.exists() and path.is_file():
                        zf.write(path, rel)
                        count += 1
            if count == 0:
                backup_file.unlink(missing_ok=True)
                return ""
            return str(backup_file)
        except Exception:
            return ""

    def _restore_backup(self, root: Path, backup_file: str, before_files) -> str:
        restored = 0
        removed = 0
        try:
            backup_path = Path(backup_file)
            with zipfile.ZipFile(backup_path, "r") as zf:
                for info in zf.infolist():
                    target = (root / info.filename).resolve()
                    if not self._is_relative_to(target, root.resolve()):
                        continue
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(zf.read(info.filename))
                    restored += 1
            after_files = self._snapshot_safe_files(root)
            for rel in sorted(after_files - set(before_files)):
                path = (root / rel).resolve()
                if self._is_relative_to(path, root.resolve()) and path.exists() and path.is_file():
                    path.unlink()
                    removed += 1
            return f"Automatisch zurueckgerollt. Wiederhergestellt: {restored}. Neue Textdateien entfernt: {removed}."
        except Exception as e:
            return f"Rollback fehlgeschlagen: {e}"

    def _verify_changed_python(self, root: Path) -> str:
        status = self._git_status(root)
        py_files = []
        for line in status.splitlines():
            rel = line[3:].strip().strip('"')
            if rel.endswith(".py"):
                p = root / rel
                if p.exists() and p.is_file():
                    py_files.append(rel)
        if not py_files:
            return ""
        try:
            result = subprocess.run(
                [os.sys.executable, "-m", "py_compile", *py_files[:40]],
                cwd=str(root),
                text=True,
                capture_output=True,
                timeout=120,
                encoding="utf-8",
                errors="replace",
            )
            if result.returncode == 0:
                return "Python-Syntax OK fuer geaenderte Python-Dateien."
            return "Python-Syntax FEHLER:\n" + ((result.stdout or "") + "\n" + (result.stderr or "")).strip()
        except Exception as e:
            return f"Python-Pruefung fehlgeschlagen: {e}"

    def _verify_changed_web(self, root: Path) -> str:
        status = self._git_status(root)
        changed = []
        for line in status.splitlines():
            rel = line[3:].strip().strip('"')
            if " -> " in rel:
                rel = rel.split(" -> ", 1)[1].strip().strip('"')
            if not rel:
                continue
            p = root / rel
            if p.exists() and p.is_file() and p.suffix.lower() in {".html", ".htm", ".css", ".js", ".json"}:
                if self._is_safe_preview_html(root, p) or p.suffix.lower() != ".html":
                    changed.append(p)
        if not changed:
            return ""

        logs = []
        html_candidates = []
        node = shutil.which("node")
        for path in changed[:40]:
            suffix = path.suffix.lower()
            rel = str(path.relative_to(root)) if self._is_relative_to(path, root) else str(path)
            if suffix in {".html", ".htm"}:
                html_candidates.append(path)
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except Exception as e:
                logs.append(f"FEHLER: {rel} konnte nicht gelesen werden: {e}")
                continue
            if not text.strip():
                logs.append(f"FEHLER: {rel} ist leer.")
                continue
            if suffix == ".json":
                try:
                    json.loads(text)
                except Exception as e:
                    logs.append(f"FEHLER: {rel} ist kein valides JSON: {e}")
            if suffix == ".js":
                if node:
                    try:
                        result = subprocess.run(
                            [node, "--check", str(path)],
                            cwd=str(root),
                            text=True,
                            capture_output=True,
                            timeout=30,
                            encoding="utf-8",
                            errors="replace",
                        )
                        if result.returncode != 0:
                            logs.append(f"FEHLER: JS-Syntax {rel}:\n{(result.stderr or result.stdout).strip()[:2500]}")
                    except Exception as e:
                        logs.append(f"JS-Pruefung fuer {rel} fehlgeschlagen: {e}")
                else:
                    logs.append(f"Hinweis: Node fehlt, JS-Syntax fuer {rel} nicht geprueft.")

        if self.browser_smoke_test and html_candidates:
            smoke = self._browser_smoke_test(root, html_candidates[0])
            if smoke:
                logs.append(smoke)

        if any(line.startswith("FEHLER:") for line in logs):
            return "\n".join(logs)
        return "HTML/CSS/JS/JSON Basispruefung OK." if logs else ""

    def _browser_smoke_test(self, root: Path, html: Path) -> str:
        try:
            from playwright.sync_api import sync_playwright
        except Exception as e:
            return f"Hinweis: Browser-Smoke-Test nicht verfuegbar: {e}"

        screenshot = self.log_dir / f"browser_check_{time.strftime('%Y%m%d_%H%M%S')}.png"
        console_errors = []
        page_errors = []
        clicked = []
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page(viewport={"width": 1280, "height": 720})

                def on_console(msg):
                    if msg.type == "error":
                        console_errors.append(msg.text[:500])

                page.on("console", on_console)
                page.on("pageerror", lambda exc: page_errors.append(str(exc)[:500]))
                page.goto(html.resolve().as_uri(), wait_until="load", timeout=20000)
                page.wait_for_timeout(800)
                for label in ["Start", "STARTEN", "Neustart", "NEUSTART", "Play", "Spielen", "Restart"]:
                    try:
                        button = page.get_by_text(label, exact=False)
                        if button.count() > 0:
                            button.first.click(timeout=1200)
                            clicked.append(label)
                            page.wait_for_timeout(500)
                            break
                    except Exception:
                        pass
                for key in ["Space", "ArrowRight", "ArrowLeft"]:
                    try:
                        page.keyboard.press(key)
                        page.wait_for_timeout(150)
                    except Exception:
                        pass
                page.screenshot(path=str(screenshot), full_page=True)
                browser.close()
        except Exception as e:
            return f"FEHLER: Browser-Smoke-Test fehlgeschlagen fuer {html.name}: {e}"

        if page_errors or console_errors:
            issues = "\n".join((page_errors + console_errors)[:8])
            return f"FEHLER: Browser-Konsole/PageError in {html.name}:\n{issues}\nScreenshot: {screenshot}"

        rel = str(html.relative_to(root)) if self._is_relative_to(html, root) else str(html)
        extra = f" | Klick getestet: {', '.join(clicked)}" if clicked else ""
        return f"Browser-Smoke-Test OK: {rel}{extra}\nScreenshot: {screenshot}"

    def _verify_project_profile(self, root: Path) -> str:
        if not self.auto_project_tests:
            return ""
        commands = self.project_intelligence.suggest_tests(root)
        if not commands:
            return ""
        logs = []
        ran = 0
        for command in commands:
            if command.startswith("python -m py_compile"):
                continue
            if command == "HTML/CSS/JS-Dateipruefung":
                continue
            if command.startswith("npm ") and not shutil.which("npm"):
                logs.append(f"Hinweis: {command} nicht ausgefuehrt, npm fehlt.")
                continue
            if command.startswith("python ") and not shutil.which("python") and not os.sys.executable:
                logs.append(f"Hinweis: {command} nicht ausgefuehrt, Python fehlt.")
                continue
            if command.startswith("python -m pytest") and not (root / "tests").exists() and not (root / "pytest.ini").exists() and not (root / "pyproject.toml").exists():
                continue
            if ran >= 2:
                break
            try:
                args = command.split()
                if args[:2] == ["python", "-m"]:
                    args[0] = os.sys.executable
                result = subprocess.run(
                    args,
                    cwd=str(root),
                    text=True,
                    capture_output=True,
                    timeout=180,
                    encoding="utf-8",
                    errors="replace",
                )
                ran += 1
                output = ((result.stdout or "") + "\n" + (result.stderr or "")).strip()
                if result.returncode == 0:
                    logs.append(f"OK: {command}")
                else:
                    logs.append(f"FEHLER: {command}\n{output[:3000]}")
            except subprocess.TimeoutExpired:
                logs.append(f"FEHLER: {command} Zeitlimit erreicht.")
            except Exception as e:
                logs.append(f"Hinweis: {command} konnte nicht laufen: {e}")
        if not logs:
            return ""
        return "Projekt-Tests:\n" + "\n".join(logs)

    def _test_gate_report(self, verify: str, web_verify: str, project_verify: str, dry_run: bool) -> str:
        if dry_run:
            return ""
        checks = [text for text in [verify, web_verify, project_verify] if text]
        joined = "\n".join(checks)
        if "FEHLER:" in joined or " FEHLER" in joined:
            return "Test-Gate: FEHLER - Jarvis meldet erst nach Pruefung fertig und startet ggf. Auto-Reparatur."
        if checks:
            return "Test-Gate: OK - automatische Pruefungen wurden ausgefuehrt."
        return "Test-Gate: HINWEIS - keine passenden automatischen Tests erkannt; Diff/Snapshot wurde trotzdem geprueft."

    def _wants_browser_preview(self, task: str) -> bool:
        low = (task or "").lower()
        low = (
            low.replace("ä", "ae")
            .replace("ö", "oe")
            .replace("ü", "ue")
            .replace("ß", "ss")
        )
        return any(x in low for x in [
            "browser", "webseite", "website", "homepage", "landing page",
            "html", "css", "javascript", "spiel", "game", "canvas",
            "web app", "webapp", "seite", "vorschau", "oeffne",
            "aufmachen", "im browser",
        ])

    def _looks_like_modify_task(self, task: str) -> bool:
        low = (task or "").lower()
        low = (
            low.replace("Ã¤", "ae")
            .replace("Ã¶", "oe")
            .replace("Ã¼", "ue")
            .replace("ÃŸ", "ss")
        )
        readonly_words = [
            "was kann", "vorschlagen", "analyse", "analysiere", "pruefe nur",
            "nur pruefen", "review", "frage", "erklaere", "warum",
        ]
        if any(word in low for word in readonly_words) and not any(word in low for word in ["mach nummer", "mache nummer", "nr", "punkt umsetzen"]):
            return False
        modify_words = [
            "mach", "mache", "erstelle", "baue", "fuege", "hinzu", "einbauen",
            "aendere", "ändere", "repariere", "fix", "loese", "lös", "verbessere",
            "codier", "codiere", "programmier", "implementier", "erstelle mir",
            "nummer", "nr", "punkt", "spiel", "homepage", "webseite", "funktion",
        ]
        return any(word in low for word in modify_words)

    def _looks_like_followup_task(self, task: str) -> bool:
        low = (task or "").lower()
        low = (
            low.replace("Ã¤", "ae")
            .replace("Ã¶", "oe")
            .replace("Ã¼", "ue")
            .replace("ÃŸ", "ss")
        )
        return bool(
            re.search(r"\b(nr|nummer|punkt|option|idee)\s*\d+\b", low)
            or re.search(r"^(mach|mache|nimm|baue|setze|setz|implementier)\s+\d+\b", low)
            or any(low.startswith(prefix) for prefix in [
                "mach das", "mache das", "mach es", "mache es", "nimm das",
                "genau das", "weiter", "mach weiter", "mach nummer", "mache nummer",
            ])
        )

    def _expand_followup_task(self, root: Path, task: str) -> str:
        if not self._looks_like_followup_task(task):
            return task
        context = ""
        try:
            context = self.project_intelligence.followup_context(root)
        except Exception:
            context = ""
        if not context:
            return task
        return (
            "PROJEKT-GEDAECHTNIS FUER FOLGEAUFTRAG:\n"
            f"{context}\n\n"
            "AKTUELLER FOLGEAUFTRAG:\n"
            f"{task}\n\n"
            "Leite Nummern, Optionen und 'mach das' aus dem Projekt-Gedaechtnis und dem Chat-Kontext ab. "
            "Wenn der Nutzer eine Nummer meint, setze genau diesen Punkt um."
        )

    def _open_browser_preview(self, root: Path, before_status: str, after_status: str, started: float) -> str:
        candidate = self._find_preview_html(root, before_status, after_status, started)
        if not candidate:
            return "Browser-Vorschau: Keine neu geaenderte HTML-Datei gefunden."
        try:
            webbrowser.open(candidate.resolve().as_uri(), new=2)
            return f"Browser-Vorschau geoeffnet: {candidate}"
        except Exception as e:
            return f"Browser-Vorschau konnte nicht geoeffnet werden: {e}"

    def _find_preview_html(self, root: Path, before_status: str, after_status: str, started: float):
        candidates = []
        seen = set()

        def add(path: Path):
            try:
                path = path.resolve()
            except Exception:
                return
            if path in seen or not self._is_safe_preview_html(root, path):
                return
            seen.add(path)
            candidates.append(path)

        before_paths = set(self._changed_paths(before_status))
        for rel in self._changed_paths(after_status):
            path = root / rel
            is_new_status = rel not in before_paths
            if path.is_file() and path.suffix.lower() in {".html", ".htm"}:
                if is_new_status or self._path_recent(path, started):
                    add(path)
            elif path.is_dir():
                if is_new_status or self._path_recent(path, started):
                    for name in ("index.html", "game.html", "app.html"):
                        add(path / name)
                for html in self._recent_html_files(path, started):
                    add(html)

        for html in self._recent_html_files(root, started):
            add(html)

        def score(path: Path):
            name = path.name.lower()
            rel = str(path.relative_to(root)).lower() if self._is_relative_to(path, root) else str(path).lower()
            points = 0
            if name == "index.html":
                points += 40
            if any(x in rel for x in ["game", "spiel", "web", "homepage", "site", "app"]):
                points += 25
            try:
                points += min(20, max(0, int(path.stat().st_mtime - started + 5)))
            except Exception:
                pass
            return points

        return sorted(candidates, key=score, reverse=True)[0] if candidates else None

    def _changed_paths(self, status: str):
        paths = []
        for line in (status or "").splitlines():
            if len(line) < 4:
                continue
            rel = line[3:].strip().strip('"')
            if " -> " in rel:
                rel = rel.split(" -> ", 1)[1].strip().strip('"')
            if rel:
                paths.append(rel)
        return paths

    def _recent_html_files(self, root: Path, started: float):
        blocked = {
            ".git", ".venv", "__pycache__", ".aider.tags.cache.v4",
            "logs", "data", "models", "external", "project_backups",
            "codex_backups", "sandbox_runs", "comfyui_workflows",
            "comfyui_video_workflows", "jarvis_3d_webgl",
        }
        try:
            for current, dirs, files in os.walk(root):
                dirs[:] = [d for d in dirs if d.lower() not in blocked]
                current_path = Path(current)
                if not self._is_relative_to(current_path.resolve(), root.resolve()):
                    continue
                for file_name in files:
                    path = current_path / file_name
                    if path.suffix.lower() not in {".html", ".htm"}:
                        continue
                    if not self._is_safe_preview_html(root, path):
                        continue
                    if self._path_recent(path, started):
                        yield path
        except Exception:
            return

    def _path_recent(self, path: Path, started: float) -> bool:
        try:
            return path.exists() and path.stat().st_mtime >= started - 3
        except Exception:
            return False

    def _is_safe_preview_html(self, root: Path, path: Path) -> bool:
        if not path.exists() or not path.is_file():
            return False
        if path.suffix.lower() not in {".html", ".htm"}:
            return False
        try:
            rel_parts = [part.lower() for part in path.resolve().relative_to(root.resolve()).parts]
        except Exception:
            return False
        blocked = {
            ".git", ".venv", "__pycache__", ".aider.tags.cache.v4",
            "logs", "data", "models", "external", "project_backups",
            "codex_backups", "sandbox_runs", "comfyui_workflows",
            "comfyui_video_workflows", "jarvis_3d_webgl",
        }
        return not any(part in blocked for part in rel_parts[:-1])

    def _is_relative_to(self, path: Path, root: Path) -> bool:
        try:
            path.relative_to(root)
            return True
        except Exception:
            return False

    def _clip(self, text: str, limit: int) -> str:
        text = text or ""
        if len(text) <= limit:
            return text
        return text[:limit] + "\n... gekuerzt ..."
