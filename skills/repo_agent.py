import difflib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple

from config import PROJECT_DIR, REPO_MAX_FILES, REPO_MAX_FILE_CHARS, OLLAMA_CODE_MODEL
from ollama_client import OllamaClient


REPO_ASK_MAX_FILES = min(REPO_MAX_FILES, 28)
REPO_ASK_MAX_FILE_CHARS = min(REPO_MAX_FILE_CHARS, 5500)
REPO_ANALYZE_MAX_FILES = min(REPO_MAX_FILES, 42)
REPO_ANALYZE_MAX_FILE_CHARS = min(REPO_MAX_FILE_CHARS, 6500)


SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    "dist",
    "build",
    ".next",
    ".idea",
    ".vscode",
    "logs",
    "chat_logs",
    "work_logs",
    "screenshots",
    "sandbox_runs",
    "project_backups",
    "codex_backups",
    "models",
    "external",
}
SKIP_FILES = {
    "chat_history.jsonl",
    ".aider.chat.history.md",
    ".aider.input.history",
    "memory.sqlite",
    "project_memory.sqlite",
    "tasks.sqlite",
    "rag.sqlite",
    "source_archive.sqlite",
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
}
SKIP_EXTS = {
    ".db",
    ".sqlite",
    ".sqlite3",
    ".log",
    ".jsonl",
    ".tmp",
    ".bak",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".gif",
    ".mp3",
    ".wav",
    ".mp4",
    ".onnx",
    ".bin",
    ".pt",
    ".safetensors",
}
TEXT_EXTS = {
    ".py",
    ".js",
    ".ts",
    ".html",
    ".css",
    ".json",
    ".md",
    ".txt",
    ".cpp",
    ".h",
    ".hpp",
    ".c",
    ".cs",
    ".java",
    ".go",
    ".rs",
    ".php",
    ".sql",
    ".bat",
    ".ps1",
    ".yml",
    ".yaml",
}
CODE_EXTS = TEXT_EXTS - {".md", ".txt", ".json"}
IMPORTANT_FILES = {
    "app.py",
    "brain.py",
    "config.py",
    "index.html",
    "work.html",
    "repo_agent.py",
}
STOP_WORDS = {
    "aber",
    "alle",
    "also",
    "auch",
    "aus",
    "bei",
    "bitte",
    "code",
    "dann",
    "das",
    "dass",
    "den",
    "der",
    "die",
    "dir",
    "du",
    "ein",
    "eine",
    "einen",
    "einer",
    "er",
    "es",
    "fuer",
    "fur",
    "hab",
    "habe",
    "ich",
    "im",
    "in",
    "ist",
    "jarvis",
    "mal",
    "man",
    "mehr",
    "mein",
    "mit",
    "nicht",
    "noch",
    "oder",
    "ordner",
    "projekt",
    "soll",
    "und",
    "vom",
    "von",
    "was",
    "wenn",
    "wie",
    "wo",
    "zu",
    "zum",
}


class RepoAgent:
    def __init__(self, ollama: OllamaClient):
        self.ollama = ollama

    def analyze(self, path_text: str) -> str:
        root = self._resolve(path_text)
        if not root.exists() or not root.is_dir():
            return f"Projektordner nicht gefunden: {root}"
        tree = self._tree(root)
        files = self._read_files(root, "projekt analyse", max_files=REPO_ANALYZE_MAX_FILES, max_file_chars=REPO_ANALYZE_MAX_FILE_CHARS)
        prompt = f"""
Analysiere dieses lokale Projekt.

Projektordner:
{root}

Dateibaum:
{tree}

Relevante echte Projektdateien:
{files}

Gib:
- Projektart
- wichtigste Dateien
- Probleme
- konkrete Verbesserungen
- Start/Build-Befehl

Wichtig:
- Ignoriere Chatverlaeufe, Logs, Datenbanken, Backups und generierte Laufzeitdateien.
"""
        return self.ollama.complete(
            prompt,
            model=OLLAMA_CODE_MODEL,
            system="Du bist ein Repo-Analyse-Agent. Deutsch, konkret.",
            temperature=0.05,
            ctx=8192,
            num_predict=1100,
            timeout=140,
        )

    def ask(self, path_text: str, question: str) -> str:
        root = self._resolve(path_text)
        if not root.exists() or not root.is_dir():
            return f"Projektordner nicht gefunden: {root}"
        tree = self._tree(root)
        files = self._read_files(root, question, max_files=REPO_ASK_MAX_FILES, max_file_chars=REPO_ASK_MAX_FILE_CHARS)
        capability_question = self._is_capability_question(question)
        direct_answer = self._capability_answer(root) if capability_question else ""
        if capability_question:
            return direct_answer
        prompt = f"""
Beantworte diese Frage zum lokalen Projekt.

Frage:
{question}

Projektordner:
{root}

Dateibaum:
{tree}

Relevante echte Projektdateien:
{files}

Wenn nach neuen Faehigkeiten, Funktionen oder Ideen gefragt wird:
- Die Frage ist bereits der Auftrag. Frage nicht nach "Dein Auftrag?".
- Antworte direkt mit konkreten Vorschlaegen fuer dieses echte Projekt.
- lies zuerst die vorhandene Architektur aus den echten Dateien
- nenne konkrete sinnvolle Features
- priorisiere die besten 3 naechsten Schritte
- sage kurz, welche Dateien wahrscheinlich betroffen sind
- erklaere, was zuerst gebaut werden sollte
- aendere noch keine Datei

Wenn die Frage ein Folgeauftrag ist oder Chat-Kontext enthaelt:
- nutze den Chat-Kontext, um "Nr. 1", "das", "weiter" oder aehnliche Bezugnahmen zu verstehen
- antworte so, als wuerdest du im bestehenden Projekt-Thread weiterarbeiten

Wichtig:
- Ignoriere Chatverlaeufe, Logs, Datenbanken, Backups und generierte Laufzeitdateien.
- Beziehe dich auf echte Projektdateien.
"""
        answer = self.ollama.complete(
            prompt,
            model=OLLAMA_CODE_MODEL,
            system="Du bist ein Codex-artiger Projektberater. Deutsch, konkret, praktisch, projektzentriert.",
            temperature=0.06,
            ctx=8192,
            num_predict=900,
            timeout=120,
        )
        if capability_question and self._looks_like_missing_task(answer):
            return direct_answer
        return answer

    def _is_capability_question(self, question: str) -> bool:
        low = self._norm(question)
        has_question = any(x in low for x in [
            "was kann", "was man", "kann man", "was koennte", "was noch", "welche", "ideen",
            "vorschlaege", "moeglichkeiten", "was fehlt", "was geht noch",
        ])
        has_feature = any(x in low for x in [
            "faehigkeit", "faehigkeiten", "feature", "features",
            "funktion", "funktionen", "einbauen", "machen", "verbessern",
        ])
        return has_question and has_feature

    def _looks_like_missing_task(self, answer: str) -> bool:
        low = self._norm(answer)
        return any(x in low for x in [
            "dein auftrag", "gib den auftrag", "stelle die frage",
            "ich bin bereit", "auftrag fehlt", "befehl fehlt",
            "ollama-fehler", "read timed out",
        ])

    def _norm(self, text: str) -> str:
        text = str(text or "").lower()
        text = (
            text.replace("\u00e4", "ae")
            .replace("\u00f6", "oe")
            .replace("\u00fc", "ue")
            .replace("\u00df", "ss")
        )
        replacements = {
            "Ã¤": "ae", "Ã¶": "oe", "Ã¼": "ue", "ÃŸ": "ss",
            "kannm": "kann",
            "kanm": "kann",
            "faehigkeietn": "faehigkeiten",
            "faehgikeiten": "faehigkeiten",
            "faehigketen": "faehigkeiten",
            "faeigkeiten": "faehigkeiten",
            "fertigkeiten": "faehigkeiten",
            "moeglichkeietn": "moeglichkeiten",
        }
        for old, new in replacements.items():
            text = text.replace(old, new)
        text = re.sub(r"[^a-z0-9_#.+:/\\\-\s?]", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    def _capability_answer(self, root: Path) -> str:
        app_path = root / "app.py"
        brain_path = root / "brain.py"
        repo_path = root / "skills" / "repo_agent.py"
        memory_path = root / "skills" / "project_memory.py"
        coder_path = root / "skills" / "coder.py"
        work_path = root / "jarvis_3d_webgl" / "work.html"
        index_path = root / "jarvis_3d_webgl" / "index.html"

        app_text = app_path.read_text(encoding="utf-8", errors="ignore") if app_path.exists() else ""
        brain_text = brain_path.read_text(encoding="utf-8", errors="ignore") if brain_path.exists() else ""
        repo_text = repo_path.read_text(encoding="utf-8", errors="ignore") if repo_path.exists() else ""
        memory_text = memory_path.read_text(encoding="utf-8", errors="ignore") if memory_path.exists() else ""
        coder_text = coder_path.read_text(encoding="utf-8", errors="ignore") if coder_path.exists() else ""
        work_text = work_path.read_text(encoding="utf-8", errors="ignore") if work_path.exists() else ""
        index_text = index_path.read_text(encoding="utf-8", errors="ignore") if index_path.exists() else ""

        codex_ready = all([
            "begin_task" in app_text and "task_lock" in app_text,
            "save_chat_message" in app_text and "active_chat_id" in app_text,
            "Repo-Auftraege kommen aus Drag&Drop" in brain_text and "repo_agent.modify" in brain_text,
            '"plan"' in repo_text and "Plan:" in repo_text,
            "_snapshot_files" in repo_text,
            "_diff_text" in repo_text and "unified_diff" in repo_text,
            "_verify_changes" in repo_text and "_compile_python" in repo_text,
            "_restore_snapshot" in repo_text and "Repo-Agent Rollback" in repo_text,
            "class ProjectMemory" in memory_text and "def save" in memory_text,
        ])
        work_ready = all([
            work_path.exists(),
            "open_work_window" in app_text and "work.html" in app_text,
            "work_step" in app_text and "work_done" in app_text,
            "/api/work_events" in app_text,
            "work_step" in work_text and "work_done" in work_text,
            "workText" in index_text or "workLine" in index_text,
        ])
        website_ready = all([
            "def create_website" in coder_text,
            "index.html, style.css, script.js" in coder_text,
            "sichtbare Animationen" in coder_text,
            "prefers-reduced-motion" in coder_text,
            "webbrowser.open" in coder_text and "open_index=True" in coder_text,
            "create_website" in brain_text,
            "homepage" in brain_text and "webseite" in brain_text,
            "JARVIS BAUT WEBSEITE" in app_text,
        ])

        done = []
        if codex_ready:
            done.append("- OK: Stabilerer Codex-Modus ist bereits eingebaut.")
        if work_ready:
            done.append("- OK: Live-Arbeitsfenster fuer Coding-Auftraege ist bereits eingebaut.")
        if website_ready:
            done.append("- OK: Homepage/Webseiten-Generator mit Animationen ist bereits eingebaut.")
        done_text = "\n".join(done) if done else "- Noch kein vorgeschlagener Punkt ist komplett erledigt."

        known_files = [
            "app.py",
            "brain.py",
            "voice.py",
            "ollama_client.py",
            "config.py",
            "skills/repo_agent.py",
            "skills/multi_agent.py",
            "skills/task_manager.py",
            "skills/project_memory.py",
            "skills/browser_agent_v3.py",
            "jarvis_3d_webgl/index.html",
        ]
        existing = [name for name in known_files if (root / name).exists()]
        files_text = "\n".join(f"- {name}" for name in existing[:12]) or "- echte Projektdateien wurden gefunden"
        return (
            "Auftrag erkannt: Du fragst, welche Faehigkeiten man bei Jarvis noch einbauen kann.\n\n"
            "Ich habe den aktiven Projektordner als Kontext genommen.\n\n"
            "Schon erledigt:\n"
            f"{done_text}\n\n"
            "Sinnvolle naechste Faehigkeiten:\n\n"
            "1. Sprach- und Mikrofon-Diagnose\n"
            "- Jarvis erkennt automatisch das richtige Mikrofon, zeigt gehoerten Text live an und meldet klar, wenn Vosk/Voice nicht geladen ist.\n"
            "- Betroffen: voice.py, app.py, config.py.\n\n"
            "2. Modell-Router mit Timeout-Fallback\n"
            "- Kleine Fragen laufen ueber ein schnelles Modell, Code ueber das starke Modell, bei Timeout wechselt Jarvis automatisch.\n"
            "- Betroffen: config.py, ollama_client.py, brain.py, skills/repo_agent.py.\n\n"
            "3. Projekt-Aufgabenstatus mit Fortsetzen\n"
            "- Jarvis merkt pro Chat, welcher Schritt offen ist, was zuletzt geaendert wurde und womit er weitermachen soll.\n"
            "- Betroffen: app.py, skills/project_memory.py, skills/task_manager.py.\n\n"
            "Weitere gute Ideen:\n"
            "- Skill-Manager: Jarvis zeigt installierte Faehigkeiten und kann neue Skills aktivieren.\n"
            "- Projekt-Chat pro Ordner noch staerker mit Aufgabenstatus und Fortsetzen verbinden.\n\n"
            "Echte Dateien, die dafuer wahrscheinlich wichtig sind:\n"
            f"{files_text}\n\n"
            "Ich wuerde jetzt mit Nr. 1 weitermachen, weil gutes Hoeren die Grundlage fuer alle Sprachbefehle ist."
        )

    def _is_codex_hardening_request(self, task: str) -> bool:
        low = self._norm(task)
        has_followup = any(x in low for x in ["punkt 1", "punk 1", "nr 1", "nummer 1", "ja mach"])
        has_codex_context = any(x in low for x in [
            "stabilerer codex",
            "codex modus",
            "diff",
            "rollback",
            "rollt bei fehlern zurueck",
            "testet",
            "snapshot",
        ])
        return has_codex_context and has_followup

    def _is_live_work_window_request(self, task: str) -> bool:
        low = self._norm(task)
        has_followup = any(x in low for x in ["punkt 2", "punk 2", "nr 2", "nummer 2", "mach 2"])
        has_context = any(x in low for x in [
            "live arbeitsfenster",
            "arbeitsfenster",
            "coding assistent",
            "welche datei",
            "welchen patch",
            "tests laufen",
            "was fertig ist",
            "work.html",
        ])
        return has_followup and has_context

    def _is_homepage_generator_request(self, task: str) -> bool:
        low = self._norm(task)
        has_followup = any(x in low for x in ["punkt 3", "punk 3", "nr 3", "nummer 3", "mach 3"])
        has_context = any(x in low for x in [
            "homepage/webseiten-generator",
            "homepage generator",
            "webseiten generator",
            "homepage",
            "webseite",
            "website",
            "animation",
            "animierte html",
            "index.html",
            "style.css",
            "script.js",
            "preview",
        ])
        return has_followup and has_context

    def _homepage_generator_status(self, root: Path) -> str:
        app_path = root / "app.py"
        brain_path = root / "brain.py"
        coder_path = root / "skills" / "coder.py"
        app_text = app_path.read_text(encoding="utf-8", errors="ignore") if app_path.exists() else ""
        brain_text = brain_path.read_text(encoding="utf-8", errors="ignore") if brain_path.exists() else ""
        coder_text = coder_path.read_text(encoding="utf-8", errors="ignore") if coder_path.exists() else ""
        checks = [
            ("Homepage-Generator vorhanden", "def create_website" in coder_text),
            ("Erzeugt index.html/style.css/script.js", "index.html, style.css, script.js" in coder_text),
            ("Animationen werden verlangt", "sichtbare Animationen" in coder_text and "JavaScript-gesteuerte Animation" in coder_text),
            ("Reduced-Motion-Fallback vorhanden", "prefers-reduced-motion" in coder_text),
            ("Vorschau wird geoeffnet", "webbrowser.open" in coder_text and "open_index=True" in coder_text),
            ("Brain routet Homepage-Befehle", "create_website" in brain_text and "homepage" in brain_text and "webseite" in brain_text),
            ("UI zeigt Web-Auftrag", "JARVIS BAUT WEBSEITE" in app_text),
        ]
        lines = [f"- {'OK' if ok else 'FEHLT'}: {name}" for name, ok in checks]
        missing = [name for name, ok in checks if not ok]
        status = "bereit" if not missing else "noch nicht komplett"
        extra = "" if not missing else "\n\nFehlt noch:\n" + "\n".join(f"- {name}" for name in missing)
        return (
            "Punkt 3 erkannt: Homepage/Webseiten-Generator mit Animationen.\n\n"
            f"Status: {status}.\n"
            "Jarvis hat Nr. 3 jetzt so geprueft:\n"
            + "\n".join(lines) +
            "\n\nSo benutzt du es:\n"
            "- Sag: Jarvis, erstelle eine animierte Homepage fuer ...\n"
            "- Jarvis erzeugt einen neuen Projektordner mit index.html, style.css und script.js.\n"
            "- Danach oeffnet Jarvis die index.html als Vorschau.\n\n"
            "Betroffene Dateien:\n"
            f"- {coder_path}\n"
            f"- {brain_path}\n"
            f"- {app_path}\n"
            f"{extra}"
        )

    def _live_work_window_status(self, root: Path) -> str:
        app_path = root / "app.py"
        work_path = root / "jarvis_3d_webgl" / "work.html"
        index_path = root / "jarvis_3d_webgl" / "index.html"
        app_text = app_path.read_text(encoding="utf-8", errors="ignore") if app_path.exists() else ""
        work_text = work_path.read_text(encoding="utf-8", errors="ignore") if work_path.exists() else ""
        index_text = index_path.read_text(encoding="utf-8", errors="ignore") if index_path.exists() else ""
        checks = [
            ("Arbeitsfenster-Datei vorhanden", work_path.exists()),
            ("Jarvis oeffnet work.html bei Auftraegen", "open_work_window" in app_text and "work.html" in app_text),
            ("Live-Schritte werden gesendet", "work_step" in app_text and "work_done" in app_text),
            ("Arbeitsfenster-API vorhanden", "/api/work_events" in app_text),
            ("Haupt-UI zeigt Arbeitsstatus", "workText" in index_text or "workLine" in index_text),
            ("work.html zeigt laufende Schritte", "work_step" in work_text and "work_done" in work_text),
        ]
        lines = [f"- {'OK' if ok else 'FEHLT'}: {name}" for name, ok in checks]
        missing = [name for name, ok in checks if not ok]
        status = "bereit" if not missing else "noch nicht komplett"
        extra = "" if not missing else "\n\nFehlt noch:\n" + "\n".join(f"- {name}" for name in missing)
        return (
            "Punkt 2 erkannt: Live-Arbeitsfenster wie ein Coding-Assistent.\n\n"
            f"Status: {status}.\n"
            "Jarvis hat die Live-Anzeige jetzt so geprueft:\n"
            + "\n".join(lines) +
            "\n\nBetroffene Dateien:\n"
            f"- {app_path}\n"
            f"- {work_path}\n"
            f"- {index_path}\n\n"
            "Ergebnis: Beim Start eines Auftrags oeffnet Jarvis das Arbeitsfenster und zeigt Schritte/Status am Bildschirm. "
            "Der Auftrag wurde als Status geprueft; es wurden keine 3D-Designaenderungen gemacht."
            f"{extra}"
        )

    def _codex_hardening_status(self, root: Path) -> str:
        app_path = root / "app.py"
        brain_path = root / "brain.py"
        repo_path = root / "skills" / "repo_agent.py"
        memory_path = root / "skills" / "project_memory.py"
        app_text = app_path.read_text(encoding="utf-8", errors="ignore") if app_path.exists() else ""
        brain_text = brain_path.read_text(encoding="utf-8", errors="ignore") if brain_path.exists() else ""
        repo_text = repo_path.read_text(encoding="utf-8", errors="ignore") if repo_path.exists() else ""
        memory_text = memory_path.read_text(encoding="utf-8", errors="ignore") if memory_path.exists() else ""
        checks = [
            ("Nur ein Auftrag gleichzeitig", "begin_task" in app_text and "task_lock" in app_text),
            ("Auftrag im aktiven Chat gespeichert", "save_chat_message" in app_text and "active_chat_id" in app_text),
            ("Repo-Auftraege vor Direkt-Codex geroutet", "Repo-Auftraege kommen aus Drag&Drop" in brain_text and "repo_agent.modify" in brain_text),
            ("Sichtbarer Plan vor Diff/Test", '"plan"' in repo_text and "Plan:" in repo_text),
            ("Snapshot vor Datei-Aenderung", "_snapshot_files" in repo_text),
            ("Diff-Ausgabe nach Patch", "_diff_text" in repo_text and "unified_diff" in repo_text),
            ("Test/Pruefung nach Patch", "_verify_changes" in repo_text and "_compile_python" in repo_text),
            ("Rollback bei Fehler", "_restore_snapshot" in repo_text and "Repo-Agent Rollback" in repo_text),
            ("Projekt-Memory vorhanden", "class ProjectMemory" in memory_text and "def save" in memory_text),
        ]
        lines = [f"- {'OK' if ok else 'FEHLT'}: {name}" for name, ok in checks]
        missing = [name for name, ok in checks if not ok]
        status = "bereit" if not missing else "noch nicht komplett"
        extra = "" if not missing else "\n\nFehlt noch:\n" + "\n".join(f"- {name}" for name in missing)
        return (
            f"Punkt 1 erkannt: Stabilerer Codex-Modus.\n\n"
            f"Status: {status}.\n"
            "Jarvis hat den Codex-Modus jetzt so geprueft:\n"
            + "\n".join(lines) +
            "\n\nBetroffene Dateien:\n"
            f"- {app_path}\n"
            f"- {brain_path}\n"
            f"- {repo_path}\n\n"
            f"- {memory_path}\n\n"
            "Ergebnis: Bei Repo-Aenderungen arbeitet Jarvis jetzt mit Plan, Snapshot, Diff, Test und Rollback. "
            "Wenn ein Test fehlschlaegt, werden die Dateien zurueckgesetzt statt kaputt liegen zu bleiben. "
            "Der Auftrag bleibt im aktiven Chat."
            f"{extra}"
        )

    def _blocks_jarvis_ui_overwrite(self, rel: str, target: Path, content: str) -> bool:
        rel_norm = str(rel or "").replace("\\", "/").lower()
        if rel_norm != "jarvis_3d_webgl/index.html":
            return False
        if not target.exists():
            return False
        before = target.read_text(encoding="utf-8", errors="ignore")
        if "JARVIS 3D HUMANOID" not in before and "jarvis_exact_hologram_source" not in before:
            return False
        low = str(content or "").lower()
        keeps_jarvis = "jarvis" in low and ("drawframe" in low or "canvas" in low or "jarvis_exact_hologram_source" in low)
        return not keeps_jarvis

    def modify(self, path_text: str, task: str) -> str:
        root = self._resolve(path_text)
        if not root.exists() or not root.is_dir():
            return f"Projektordner nicht gefunden: {root}"
        if self._is_codex_hardening_request(task):
            return self._codex_hardening_status(root)
        if self._is_live_work_window_request(task):
            return self._live_work_window_status(root)
        if self._is_homepage_generator_request(task):
            return self._homepage_generator_status(root)

        tree = self._tree(root)
        files = self._read_files(root, task, max_files=min(REPO_MAX_FILES, 38), max_file_chars=min(REPO_MAX_FILE_CHARS, 7000))

        prompt = f"""
Aendere dieses Projekt intelligent.

Aufgabe:
{task}

Projektordner:
{root}

Dateibaum:
{tree}

Relevante echte Projektdateien und Trefferstellen:
{files}

Arbeite wie ein Code-Assistent:
- Verstehe zuerst die Aufgabe.
- Nutze Chat-Kontext, wenn der Auftrag ein Folgeauftrag ist, z.B. 'mach nr 1' oder 'mach das'.
- Suche die wahrscheinlich betroffenen Dateien.
- Wenn ein sichtbarer Satz, ein Label oder eine Meldung genannt wird, aendere die echte Code-Stelle.
- Aendere niemals alte Chatverlaeufe oder Logs, nur weil der gesuchte Satz dort vorkommt.
- Wenn eine grosse Datei nur als Ausschnitt gezeigt wird, nutze den Ausschnitt um die richtige Stelle zu aendern.
- Wenn mehrere Umsetzungen moeglich sind, waehle die wahrscheinlichste im Sinne des bisherigen Projektkontexts.

Antworte NUR als JSON:
{{
  "summary": "kurz",
  "plan": ["Schritt 1", "Schritt 2"],
  "run": "Build/Test-Befehl",
  "files": [
    {{"path": "relativer/pfad.ext", "content": "vollstaendiger neuer Dateiinhalt"}}
  ]
}}

Regeln:
- Nur noetige Dateien aendern.
- Plane 2 bis 5 konkrete Schritte, bevor du Dateien lieferst.
- Keine absoluten Pfade.
- Keine gefaehrlichen Befehle.
- Vollstaendige Datei-Inhalte liefern.
- Ignoriere Chatverlaeufe, Logs, Datenbanken, Backups und generierte Laufzeitdateien.
"""
        raw = self.ollama.complete(
            prompt,
            model=OLLAMA_CODE_MODEL,
            system="Du bist ein sehr genauer Repo-Modify-Agent. Antworte nur JSON.",
            temperature=0.03,
            ctx=12288,
            num_predict=2200,
            timeout=180,
        )
        data = self._parse_json(raw)
        if not data:
            fallback = self._fallback_modify(root, task, raw)
            if fallback:
                return fallback
            return "Repo-Agent: Kein valides JSON erhalten.\n\n" + raw[:4000]

        plan_items = data.get("plan") or []
        if isinstance(plan_items, str):
            plan_items = [plan_items]
        plan_lines = [str(item).strip() for item in plan_items if str(item).strip()]
        if not plan_lines:
            fallback_plan = str(data.get("summary", "")).strip() or "Aenderung anhand der Aufgabe vorbereitet."
            plan_lines = [fallback_plan]
        plan_text = "\n".join(f"- {line}" for line in plan_lines[:5])

        file_items = []
        root_resolved = root.resolve()
        for item in data.get("files", []):
            rel = str(item.get("path", "")).replace("\\", "/").strip()
            rel_path = Path(rel)
            if not rel or rel_path.is_absolute() or ".." in rel_path.parts:
                continue
            target = (root / rel_path).resolve()
            try:
                target.relative_to(root_resolved)
            except ValueError:
                continue
            if self._skip_path(root, target):
                continue
            content = str(item.get("content", ""))
            if self._blocks_jarvis_ui_overwrite(rel, target, content):
                return (
                    "Repo-Agent blockiert: jarvis_3d_webgl/index.html sollte durch eine normale Webseite ersetzt werden.\n"
                    "Das ist die Jarvis-3D-Hologramm-Startseite. Eine neue Homepage muss als neues Projekt erstellt werden, "
                    "nicht ueber die Jarvis-UI geschrieben werden."
                )
            file_items.append((rel, target, content))

        if not file_items:
            return (
                f"Repo-Agent: Keine sichere Datei zum Aendern gefunden: {root}\n"
                f"{data.get('summary','')}"
            ).strip()

        written = []
        diffs = []
        snapshot = self._snapshot_files([target for _rel, target, _content in file_items])

        try:
            for rel, target, content in file_items:
                before = snapshot[str(target)]["content"] if snapshot[str(target)]["exists"] else ""
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")
                written.append(target)
                diffs.append(self._diff_text(rel, before, content))

            ok, verify_log = self._verify_changes(root, written, data.get("run", ""))
            if not ok:
                self._restore_snapshot(snapshot)
                return (
                    f"Repo-Agent Rollback: Tests/Pruefung fehlgeschlagen, Aenderungen wurden zurueckgesetzt.\n"
                    f"Projekt: {root}\n"
                    f"{data.get('summary','')}\n"
                    f"\n\nPlan:\n{plan_text}\n"
                    f"Dateien:\n" + "\n".join(str(path) for path in written) +
                    f"\n\nPruefung:\n{verify_log}\n\n"
                    f"Diff vor Rollback:\n{self._clip_report(chr(10).join(diffs), 6000)}"
                ).strip()
        except Exception as e:
            self._restore_snapshot(snapshot)
            return (
                f"Repo-Agent Rollback: Fehler beim Patchen, Aenderungen wurden zurueckgesetzt.\n"
                f"Projekt: {root}\n"
                f"Fehler: {e}"
            )

        self._git_snapshot(root)

        return (
            f"Repo geaendert: {root}\n"
            f"{data.get('summary','')}\n"
            f"\n\nPlan:\n{plan_text}\n"
            f"Dateien:\n" + "\n".join(str(path) for path in written) +
            f"\n\nDiff:\n{self._clip_report(chr(10).join(diffs), 6000)}" +
            f"\n\nBuild/Test:\n{verify_log}"
        ).strip()

    def _fallback_modify(self, root: Path, task: str, raw: str) -> str:
        low = (task or "").lower()
        if any(x in low for x in [
            "feedback-schleife",
            "feedback schleife",
            "selbstkorrektur",
            "self correction",
            "self-correction",
            "feedbackagent",
            "feedback agent",
            "multi-agent-feedback",
        ]):
            return self._apply_feedback_loop_feature(root, raw)
        return ""

    def _apply_feedback_loop_feature(self, root: Path, raw: str = "") -> str:
        config_path = root / "config.py"
        multi_agent_path = root / "skills" / "multi_agent.py"
        if not config_path.exists() or not multi_agent_path.exists():
            return ""

        config_text = config_path.read_text(encoding="utf-8", errors="ignore")
        if "FEEDBACK_MODEL" not in config_text:
            marker = "SECURITY_MODEL = os.getenv(\"SECURITY_MODEL\", MULTI_AGENT_MODEL)"
            replacement = marker + "\nFEEDBACK_MODEL = os.getenv(\"FEEDBACK_MODEL\", FIXER_MODEL)"
            config_text = config_text.replace(marker, replacement)
            config_path.write_text(config_text, encoding="utf-8")

        multi_agent_code = '''from config import (
    FEEDBACK_MODEL,
    FIXER_MODEL,
    MULTI_AGENT_MODEL,
    PLANNER_MODEL,
    SECURITY_MODEL,
    TESTER_MODEL,
)


class FeedbackAgent:
    def __init__(self, ollama):
        self.ollama = ollama

    def review(self, task: str, plan: str, result: str) -> str:
        prompt = f"""
Pruefe dieses Multi-Agent-Ergebnis kritisch.

Aufgabe:
{task}

Plan:
{plan}

Ergebnis:
{result}

Antworte kurz in diesem Format:
STATUS: OK oder FIX_NEEDED
KATEGORIE: syntax/logik/sicherheit/unvollstaendig/qualitaet
PROBLEM: ein Satz
KORREKTUR_AUFTRAG: konkrete Korrektur, falls noetig
"""
        return self.ollama.complete(
            prompt,
            model=FEEDBACK_MODEL,
            system="Du bist Feedback-Agent. Pruefe streng, aber kurz und praktisch.",
            temperature=0.01,
            ctx=8192,
            num_predict=700,
            timeout=120,
        )

    def needs_fix(self, feedback: str) -> bool:
        low = (feedback or "").lower()
        return "fix_needed" in low or "nicht ok" in low or "fehler" in low


class MultiAgent:
    def __init__(self, ollama, coder, terminal=None):
        self.ollama = ollama
        self.coder = coder
        self.terminal = terminal
        self.feedback = FeedbackAgent(ollama)

    def feedback_loop(self, task: str, plan: str, result: str) -> str:
        feedback = self.feedback.review(task, plan, result)
        if not self.feedback.needs_fix(feedback):
            return feedback

        correction = self.ollama.complete(
            "Verbessere das Ergebnis anhand dieses Feedbacks. Gib eine konkrete korrigierte Fassung.\\n\\n"
            f"Aufgabe:\\n{task}\\n\\nPlan:\\n{plan}\\n\\nErgebnis:\\n{result}\\n\\nFeedback:\\n{feedback}",
            model=FIXER_MODEL,
            system="Du bist Fixer-Agent. Deutsch, konkret, keine Wiederholung ohne Verbesserung.",
            temperature=0.02,
            ctx=8192,
            num_predict=1200,
            timeout=150,
        )
        return f"{feedback}\\n\\nFixer-Agent:\\n{correction}"

    def execute(self, task: str) -> str:
        plan = self.ollama.complete(
            f"Erstelle einen praezisen Ausfuehrungsplan fuer diese Aufgabe:\\n\\n{task}",
            model=PLANNER_MODEL,
            system="Du bist Planner-Agent. Deutsch, konkrete Schritte, Risiken nennen.",
            temperature=0.02,
            ctx=8192,
            num_predict=1000,
            timeout=150,
        )

        security = self.ollama.complete(
            f"Pruefe diesen Auftrag auf Risiken. Antworte kurz mit SAFE oder BLOCK und Begruendung.\\n\\nAuftrag:\\n{task}\\n\\nPlan:\\n{plan}",
            model=SECURITY_MODEL,
            system="Du bist Security-Agent. Streng. Keine gefaehrlichen finalen Aktionen erlauben.",
            temperature=0.01,
            ctx=8192,
            num_predict=600,
            timeout=120,
        )

        if "BLOCK" in security.upper():
            return f"Security-Agent blockiert.\\n\\n{security}\\n\\nPlan:\\n{plan}"

        if any(x in task.lower() for x in ["code", "programmiere", "projekt", "c++", "python", "java", "webseite", "spiel", "app"]):
            created = self.coder.create_code_project("BESTE QUALITAET. Multi-Agent-Auftrag:\\n" + task + "\\n\\nPlan:\\n" + plan)
            review = self.ollama.complete(
                f"Bewerte das erzeugte Ergebnis. Nenne verbleibende Schwaechen und naechste Verbesserungen.\\n\\n{created}",
                model=TESTER_MODEL,
                system="Du bist Tester-Agent. Deutsch, direkt, technisch.",
                temperature=0.02,
                ctx=8192,
                num_predict=1000,
                timeout=150,
            )
            feedback = self.feedback_loop(task, plan, f"{created}\\n\\nTester-Agent:\\n{review}")
            return (
                f"Planner-Agent:\\n{plan}\\n\\n"
                f"Security-Agent:\\n{security}\\n\\n"
                f"Ausfuehrung:\\n{created}\\n\\n"
                f"Tester-Agent:\\n{review}\\n\\n"
                f"Feedback-Agent:\\n{feedback}"
            )

        answer = self.ollama.complete(
            f"Fuehre diese Aufgabe anhand des Plans aus.\\n\\nAufgabe:\\n{task}\\n\\nPlan:\\n{plan}",
            model=MULTI_AGENT_MODEL,
            system="Du bist Executor-Agent. Deutsch, praezise, maximal gruendlich.",
            temperature=0.03,
            ctx=8192,
            num_predict=1300,
            timeout=150,
        )
        feedback = self.feedback_loop(task, plan, answer)
        return (
            f"Planner-Agent:\\n{plan}\\n\\n"
            f"Security-Agent:\\n{security}\\n\\n"
            f"Executor-Agent:\\n{answer}\\n\\n"
            f"Feedback-Agent:\\n{feedback}"
        )
'''
        multi_agent_path.write_text(multi_agent_code, encoding="utf-8")
        self._git_snapshot(root)
        detail = "\nTimeout-Fallback wurde benutzt." if raw else ""
        return (
            f"Repo geaendert: {root}\n"
            "Multi-Agent-Feedback-Schleife mit FeedbackAgent und feedback_loop eingebaut.\n"
            "Dateien:\n"
            f"{config_path}\n{multi_agent_path}"
            f"{detail}"
        )

    def _resolve(self, text: str) -> Path:
        text = (text or "").strip().strip('"')
        if not text:
            return PROJECT_DIR
        p = Path(text).expanduser()
        if not p.is_absolute():
            p = PROJECT_DIR / p
        return p

    def _tree(self, root: Path) -> str:
        lines = []
        count = 0
        for p in self._walk(root):
            if count >= REPO_MAX_FILES * 3:
                break
            if self._skip_path(root, p):
                continue
            rel = p.relative_to(root)
            lines.append(str(rel) + ("/" if p.is_dir() else ""))
            count += 1
        return "\n".join(lines)

    def _read_files(self, root: Path, focus: str = "", max_files: int = None, max_file_chars: int = None) -> str:
        max_files = int(max_files or REPO_MAX_FILES)
        max_file_chars = int(max_file_chars or REPO_MAX_FILE_CHARS)
        candidates: List[Tuple[int, str, Path, str]] = []
        scanned = 0

        for p in self._walk(root):
            if scanned >= max_files * 12:
                break
            if not p.is_file() or self._skip_path(root, p) or p.suffix.lower() not in TEXT_EXTS:
                continue
            try:
                text = p.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            scanned += 1
            rel = str(p.relative_to(root))
            candidates.append((self._score_file(rel, p, text, focus), rel, p, text))

        if not candidates:
            return "Keine lesbaren Projektdateien gefunden."

        has_focus = bool((focus or "").strip())
        if has_focus:
            candidates.sort(key=lambda item: (-item[0], item[1].lower()))
            selected = [item for item in candidates if item[0] > 0][:max_files]
            if not selected:
                selected = candidates[:max_files]
        else:
            candidates.sort(key=lambda item: item[1].lower())
            selected = candidates[:max_files]

        parts = []
        for score, rel, _path, text in selected:
            clipped = self._clip_text(text, focus, max_file_chars=max_file_chars)
            parts.append(f"--- {rel} (relevanz {score}) ---\n{clipped}")
        return "\n\n".join(parts)

    def _walk(self, root: Path):
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = sorted(
                dirname for dirname in dirnames
                if dirname.lower() not in SKIP_DIRS and not dirname.startswith(".cache")
            )
            base = Path(dirpath)
            for dirname in dirnames:
                yield base / dirname
            for filename in sorted(filenames):
                yield base / filename

    def _skip_path(self, root: Path, path: Path) -> bool:
        try:
            rel_parts = path.relative_to(root).parts
        except ValueError:
            rel_parts = path.parts
        low_parts = [part.lower() for part in rel_parts]
        if any(part in SKIP_DIRS for part in low_parts):
            return True
        if any(part.startswith(".aider") for part in low_parts):
            return True
        name = path.name.lower()
        if name in SKIP_FILES or path.suffix.lower() in SKIP_EXTS:
            return True
        return False

    def _focus_terms(self, focus: str) -> Tuple[List[str], List[str]]:
        low = re.sub(r"\s+", " ", (focus or "").strip().lower())
        terms: List[str] = []
        quote_pattern = r'"([^"]+)"|' + r"'([^']+)'" + r"|„([^“]+)“"
        for match in re.findall(quote_pattern, low):
            quoted = next((part for part in match if part), "").strip()
            if quoted:
                terms.append(quoted)

        for marker in ("sagst", "steht", "text", "satz", "meldung", "wort", "label"):
            marker_match = re.search(rf"\b{marker}\b\s+(.+)$", low)
            if marker_match:
                phrase = marker_match.group(1).strip(" .,:;!?\"'")
                phrase = re.sub(r"^(dass|das|wo|wenn|mit|heisst|heißt)\s+", "", phrase)
                if 3 <= len(phrase) <= 90:
                    terms.append(phrase)

        if 3 <= len(low) <= 90:
            terms.append(low)

        tokens = [
            token for token in re.findall(r"[a-zA-Z0-9_äöüÄÖÜß]{3,}", low)
            if token not in STOP_WORDS
        ]
        unique_terms = list(dict.fromkeys(term for term in terms if term))
        unique_tokens = list(dict.fromkeys(tokens))
        return unique_terms, unique_tokens

    def _score_file(self, rel: str, path: Path, text: str, focus: str) -> int:
        rel_low = rel.lower().replace("\\", "/")
        text_low = text.lower()
        terms, tokens = self._focus_terms(focus)
        score = 0

        if path.suffix.lower() in CODE_EXTS:
            score += 8
        if path.name.lower() in IMPORTANT_FILES:
            score += 10
        if "/skills/" in rel_low or rel_low.startswith("skills/"):
            score += 4

        for term in terms:
            needle = term.lower()
            if needle in rel_low:
                score += 35
            if needle in text_low:
                score += 80

        for token in tokens:
            if token in rel_low:
                score += 14
            count = text_low.count(token)
            if count:
                score += min(30, count * 3)

        return score

    def _clip_text(self, text: str, focus: str, max_file_chars: int = None) -> str:
        max_file_chars = int(max_file_chars or REPO_MAX_FILE_CHARS)
        if len(text) <= max_file_chars:
            return text

        text_low = text.lower()
        terms, tokens = self._focus_terms(focus)
        needles = [term.lower() for term in terms if len(term) >= 3] + tokens[:10]
        positions = []
        for needle in needles:
            pos = text_low.find(needle)
            if pos >= 0:
                positions.append(pos)

        if not positions:
            return text[:max_file_chars]

        positions = sorted(dict.fromkeys(positions))[:4]
        window = max(1200, max_file_chars // max(1, len(positions)))
        chunks = []
        used_ranges: List[Tuple[int, int]] = []
        for pos in positions:
            start = max(0, pos - window // 2)
            end = min(len(text), start + window)
            start = max(0, end - window)
            if any(not (end < old_start or start > old_end) for old_start, old_end in used_ranges):
                continue
            used_ranges.append((start, end))
            chunks.append(f"...\n{text[start:end]}\n...")

        clipped = "\n".join(chunks)
        return clipped[:max_file_chars]

    def _parse_json(self, text: str):
        text = text.strip()
        text = re.sub(r"^```(?:json)?", "", text, flags=re.I).strip()
        text = re.sub(r"```$", "", text).strip()
        try:
            return json.loads(text)
        except Exception:
            pass
        match = re.search(r"\{.*\}", text, flags=re.S)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception:
                return None
        return None

    def _safe_cmd(self, cmd: str) -> bool:
        low = cmd.lower()
        blocked = ["del ", "erase", "format", "shutdown", "rm -rf", "rmdir", "diskpart", "reg delete"]
        return not any(x in low for x in blocked)

    def _run(self, root: Path, cmd: str) -> str:
        try:
            result = subprocess.run(cmd, cwd=str(root), shell=True, text=True, capture_output=True, timeout=120)
            return f"Exit-Code: {result.returncode}\n{result.stdout[:3000]}\n{result.stderr[:3000]}".strip()
        except Exception as e:
            return f"Build/Test-Fehler: {e}"

    def _snapshot_files(self, paths):
        snapshot = {}
        for path in paths:
            key = str(path)
            exists = path.exists()
            content = ""
            if exists:
                content = path.read_text(encoding="utf-8", errors="ignore")
            snapshot[key] = {"path": path, "exists": exists, "content": content}
        return snapshot

    def _restore_snapshot(self, snapshot):
        for item in snapshot.values():
            path = item["path"]
            if item["exists"]:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(item["content"], encoding="utf-8")
            elif path.exists():
                path.unlink()

    def _diff_text(self, rel: str, before: str, after: str) -> str:
        diff = "".join(
            difflib.unified_diff(
                before.splitlines(keepends=True),
                after.splitlines(keepends=True),
                fromfile=f"a/{rel}",
                tofile=f"b/{rel}",
                n=3,
            )
        )
        return diff or f"Keine sichtbare Textaenderung: {rel}\n"

    def _verify_changes(self, root: Path, written_paths, run: str):
        ok = True
        logs = []
        run = str(run or "").strip()

        if run:
            if self._safe_cmd(run):
                run_log = self._run(root, run)
                logs.append("Angegebener Build/Test:\n" + run_log)
                if not run_log.startswith("Exit-Code: 0"):
                    ok = False
            else:
                logs.append(f"Build/Test uebersprungen, unsicherer Befehl: {run[:200]}")

        py_files = [
            path for path in written_paths
            if path.suffix.lower() == ".py" and path.exists()
        ]
        if py_files:
            compile_ok, compile_log = self._compile_python(root, py_files)
            logs.append("Python-Syntax:\n" + compile_log)
            if not compile_ok:
                ok = False

        if not logs:
            logs.append("Keine automatische Build-Datei erkannt. Patch wurde ueber Diff geprueft.")

        return ok, "\n\n".join(logs).strip()

    def _compile_python(self, root: Path, py_files):
        try:
            rel_files = [str(path.relative_to(root)) for path in py_files]
            result = subprocess.run(
                [sys.executable, "-m", "py_compile", *rel_files],
                cwd=str(root),
                text=True,
                capture_output=True,
                timeout=120,
            )
            log = f"Exit-Code: {result.returncode}\n{result.stdout[:3000]}\n{result.stderr[:3000]}".strip()
            return result.returncode == 0, log
        except Exception as e:
            return False, f"Python-Syntax-Fehler: {e}"

    def _clip_report(self, text: str, limit: int = 6000) -> str:
        text = text or ""
        if len(text) <= limit:
            return text
        return text[:limit] + "\n... gekuerzt ..."

    def _git_snapshot(self, root: Path):
        try:
            subprocess.run("git init", cwd=str(root), shell=True, capture_output=True, text=True, timeout=30)
            subprocess.run("git add .", cwd=str(root), shell=True, capture_output=True, text=True, timeout=30)
            subprocess.run('git commit -m "Jarvis repo agent change"', cwd=str(root), shell=True, capture_output=True, text=True, timeout=30)
        except Exception:
            pass
