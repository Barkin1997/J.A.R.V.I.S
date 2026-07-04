import json
import os
import re
import shutil
import subprocess
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

from config import (
    PROJECT_DIR,
    OLLAMA_CODE_MODEL,
    OLLAMA_MAX_CODE_MODEL,
    OLLAMA_AGENT_CODE_MODEL,
    OLLAMA_STRONG_CODE_MODEL,
    OLLAMA_BEAST_CODE_MODEL,
    AUTO_BUILD_TEST,
    AUTO_FIX_ROUNDS,
    AUTO_GIT_SNAPSHOT,
)
from ollama_client import OllamaClient


class CoderSkill:
    def __init__(self, ollama: OllamaClient):
        self.ollama = ollama

    def create_website(self, prompt: str) -> str:
        return self._create_project(
            kind="website",
            prompt=prompt,
            system=(
                "Du bist ein Elite-Frontend-Architekt. "
                "Erstelle eine hochwertige, responsive, sichtbar animierte Homepage/Webseite mit sauberer Struktur, UX, Accessibility und robustem JavaScript. "
                "Die Seite darf nicht statisch wirken: nutze animierte Hero-Sektion, dezente Scroll-Reveals, Hover-Interaktionen, aktive UI-Elemente und motion-safe Fallbacks. "
                "Design: dunkel, orange, futuristisch, Jarvis-Stil. "
                "Keine kostenpflichtigen externen Dienste."
            ),
            project_rules=(
                "- Erzeuge index.html, style.css, script.js.\n"
                "- Muss direkt lokal im Browser laufen.\n"
                "- Saubere Trennung und klare UI.\n"
                "- Baue sichtbare Animationen ein: Hero-Bewegung, Scroll-Reveal, Hover-Effekte und mindestens eine JavaScript-gesteuerte Animation.\n"
                "- Respektiere prefers-reduced-motion mit reduziertem Bewegungsmodus.\n"
                "- Keine rein statische Homepage liefern.\n"
            ),
            open_index=True,
            force_model=None,
        )

    def create_game(self, prompt: str) -> str:
        return self._create_project(
            kind="game",
            prompt=prompt,
            system=(
                "Du bist ein Elite-Game-Developer. "
                "Erstelle ein vollständiges spielbares Browser-Spiel mit Startmenü, Score, Neustart, Level/Schwierigkeit und klarer Steuerung. "
                "Design: dunkel, orange, futuristisch. "
                "Keine kostenpflichtigen externen Dienste."
            ),
            project_rules=(
                "- Erzeuge index.html, style.css, script.js.\n"
                "- Muss direkt lokal im Browser spielbar sein.\n"
                "- Startscreen und Game-Over-Screen muessen standardmaessig versteckt sein, ausser sie haben eine aktive Klasse.\n"
                "- Beim Start/Neustart muessen Game-Over-Overlay, alte Gegner, alte Projektile, alte Tasten und alte Animation-Loops sauber zurueckgesetzt werden.\n"
                "- Das Spiel darf nicht sofort nach Start Game Over zeigen.\n"
                "- Keine Build-Tools nötig.\n"
            ),
            open_index=True,
            force_model=None,
        )

    def create_code_project(self, prompt: str) -> str:
        language = self._detect_language(prompt)
        rules = self._rules_for_language(language)
        return self._create_project(
            kind=f"code_{self._safe_kind(language)}",
            prompt=prompt,
            system=(
                "Du bist ein Elite-Softwarearchitekt und Senior-Entwickler. "
                "Erstelle komplette, lauffähige Projekte. "
                "Unterstütze C++, C, C#, Python, Java, JavaScript, TypeScript, Node, React, Go, Rust, PHP, SQL, PowerShell, Batch und weitere Sprachen. "
                "Schreibe robusten, sauberen, wartbaren Code. "
                "Antworte strikt als JSON."
            ),
            project_rules=rules,
            open_index=False,
            force_model=None,
        )

    def code_answer(self, prompt: str) -> str:
        model = self._select_model(prompt)
        return self.ollama.complete(
            prompt=prompt,
            model=model,
            system=(
                "Du bist ein Elite-Softwareentwickler. "
                "Antworte auf Deutsch. Gib lauffähigen Code, Dateinamen, Installationsschritte und Startbefehl. "
                "Unterstütze C++, C, C#, Python, Java, JavaScript, TypeScript, Node, React, Go, Rust, PHP, SQL, PowerShell, Batch und weitere Sprachen. "
                "Keine unnötige Theorie."
            ),
            temperature=0.06
        )

    def analyze_error(self, error_text: str) -> str:
        model = self._select_model(error_text, prefer_debug=True)
        return self.ollama.complete(
            prompt=f"Analysiere diesen Fehler. Gib konkrete Korrekturen und korrigierten Code, falls nötig:\n\n{error_text}",
            model=model,
            system="Du bist ein Debugging-Spezialist. Deutsch, präzise, umsetzbar.",
            temperature=0.05
        )

    def _create_project(self, kind: str, prompt: str, system: str, project_rules: str, open_index: bool, force_model: Optional[str]) -> str:
        model = force_model or self._select_model(prompt)
        request = f"""
Erstelle ein vollständiges lokales Projekt.

Antworte NUR als valides JSON. Kein Markdown. Kein Text außerhalb JSON.

JSON-Format:
{{
  "summary": "kurze Beschreibung",
  "language": "Programmiersprache",
  "run": "Start- oder Build-Befehl",
  "files": [
    {{"path": "Dateiname", "content": "Dateiinhalt"}}
  ]
}}

Projektregeln:
{project_rules}

Allgemeine Regeln:
- Alle nötigen Dateien erzeugen.
- Keine gefährlichen Aktionen.
- Keine echten API-Keys.
- Keine absoluten Pfade.
- Keine kostenpflichtigen Dienste.
- Bei C++: main.cpp und build_run.bat erzeugen.
- Bei Python: main.py, run.bat und requirements.txt falls nötig erzeugen.
- Bei Node/React: package.json, run.bat und klare Startanweisung erzeugen.
- Bei Java: Main.java und build_run.bat erzeugen.
- Bei C#: Program.cs und build_run.bat erzeugen.
- Erzeuge README.md mit Startanleitung.
- Code soll robust, kommentiert und testbar sein.

Nutzerwunsch:
{prompt}
"""
        raw = self.ollama.complete(request, model=model, system=system, temperature=0.04)
        if self._looks_like_model_error(raw):
            return (
                "Projekt nicht erstellt: Das aktive Modell konnte keinen Code liefern.\n"
                f"Modell: {model}\n"
                "Grund:\n"
                + raw[:1600]
            )

        data = self._parse_json(raw)

        folder = PROJECT_DIR / f"{kind}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        folder.mkdir(parents=True, exist_ok=True)
        written = self._write_project_files(folder, data, raw)
        if not written:
            return (
                "Projekt nicht erstellt: Das Modell hat keine Dateien geliefert.\n"
                f"Modell: {model}\n"
                "Antwort:\n"
                + raw[:1600]
            )

        run_cmd = data.get("run", "") if data else ""
        language = data.get("language", self._detect_language(prompt)) if data else self._detect_language(prompt)

        build_log = ""
        if AUTO_BUILD_TEST:
            build_log = self._build_test_and_fix(folder, run_cmd, language, prompt, model)
        if open_index:
            browser_checks = self._static_browser_checks(folder)
            if "FEHLER:" in browser_checks and AUTO_FIX_ROUNDS > 0:
                browser_checks += "\n\nAuto-Fix:\n" + self._fix_browser_project(folder, browser_checks, prompt, model)
            build_log = ("\n\n".join(x for x in [build_log, "Browser-Projekt-Pruefung:\n" + browser_checks] if x)).strip()

        git_log = ""
        if AUTO_GIT_SNAPSHOT:
            git_log = self._git_snapshot(folder)

        index = folder / "index.html"
        if open_index and index.exists():
            webbrowser.open(index.resolve().as_uri(), new=2)
        if not open_index:
            self._show_project_folder(folder)

        summary = data.get("summary", "") if data else "Modell lieferte kein valides JSON. Rohantwort gespeichert."
        result = [
            f"Projekt erstellt: {folder}",
            f"Modell: {model}",
            summary,
            f"Start/Build: {run_cmd or self._guess_run_command(folder, language)}",
            "Dateien:",
            "\n".join(str(p) for p in written),
        ]
        if build_log:
            result += ["", "Build/Test:", build_log]
        if git_log:
            result += ["", "Git:", git_log]
        return "\n".join(x for x in result if x is not None).strip()

    def _write_project_files(self, folder: Path, data, raw: str):
        written = []
        if data:
            for item in data.get("files", []):
                rel = str(item.get("path", "")).strip().replace("\\", "/")
                content = item.get("content", "")
                if not rel or rel.startswith("/") or ".." in Path(rel).parts:
                    continue
                target = folder / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")
                written.append(target)
        else:
            target = folder / "README_GENERATED.txt"
            target.write_text(raw, encoding="utf-8")
            written.append(target)
        return written

    def _build_test_and_fix(self, folder: Path, run_cmd: str, language: str, prompt: str, model: str) -> str:
        logs = []
        for round_no in range(AUTO_FIX_ROUNDS + 1):
            cmd = self._guess_run_command(folder, language, run_cmd)
            if not cmd:
                return "Kein sicherer Build-/Testbefehl erkannt."
            code, out = self._run_safe(folder, cmd)
            logs.append(f"Runde {round_no + 1}: {cmd}\nExit-Code: {code}\n{out[:4000]}".strip())
            if code == 0:
                return "\n\n".join(logs)

            if round_no >= AUTO_FIX_ROUNDS:
                break

            fix_prompt = f"""
Das Projekt hat einen Fehler.

Originalauftrag:
{prompt}

Build/Test-Befehl:
{cmd}

Fehlerausgabe:
{out[:8000]}

Korrigiere nur nötige Dateien.

Antworte NUR als JSON:
{{
  "summary": "was wurde korrigiert",
  "files": [
    {{"path": "Dateiname", "content": "vollständiger neuer Dateiinhalt"}}
  ]
}}
"""
            raw_fix = self.ollama.complete(
                fix_prompt,
                model=model,
                system="Du bist ein Build-Fix-Agent. Korrigiere lauffähig. Antworte strikt als JSON.",
                temperature=0.03
            )
            fix_data = self._parse_json(raw_fix)
            if not fix_data:
                logs.append("Fix fehlgeschlagen: Modell lieferte kein valides JSON.")
                break
            self._write_project_files(folder, fix_data, raw_fix)
            logs.append(f"Fix angewendet: {fix_data.get('summary', '')}")

        return "\n\n".join(logs)

    def _run_safe(self, folder: Path, cmd: str) -> Tuple[int, str]:
        dangerous = ["rm -rf", "format", "del /s", "rmdir /s", "shutdown", "diskpart", "reg delete"]
        low = cmd.lower()
        if any(x in low for x in dangerous):
            return 99, "Blockiert: gefährlicher Build-Befehl."
        try:
            result = subprocess.run(
                cmd,
                cwd=str(folder),
                shell=True,
                text=True,
                capture_output=True,
                timeout=120,
            )
            out = ""
            if result.stdout:
                out += "STDOUT:\n" + result.stdout
            if result.stderr:
                out += "\nSTDERR:\n" + result.stderr
            return result.returncode, out.strip()
        except subprocess.TimeoutExpired:
            return 124, "Timeout nach 120 Sekunden."
        except Exception as e:
            return 1, f"Build/Test-Fehler: {e}"

    def _static_browser_checks(self, folder: Path) -> str:
        logs = []
        index = folder / "index.html"
        style = folder / "style.css"
        script = folder / "script.js"
        for path in [index, style, script]:
            if not path.exists():
                logs.append(f"FEHLER: {path.name} fehlt.")
            else:
                try:
                    if not path.read_text(encoding="utf-8", errors="replace").strip():
                        logs.append(f"FEHLER: {path.name} ist leer.")
                except Exception as e:
                    logs.append(f"FEHLER: {path.name} konnte nicht gelesen werden: {e}")

        node = shutil.which("node")
        for js in folder.rglob("*.js"):
            if not js.is_file():
                continue
            rel = js.relative_to(folder)
            if node:
                try:
                    result = subprocess.run(
                        [node, "--check", str(js)],
                        cwd=str(folder),
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

        for json_file in folder.rglob("*.json"):
            try:
                json.loads(json_file.read_text(encoding="utf-8", errors="replace"))
            except Exception as e:
                logs.append(f"FEHLER: JSON {json_file.relative_to(folder)} ist ungueltig: {e}")

        try:
            all_text = "\n".join(
                p.read_text(encoding="utf-8", errors="replace")
                for p in [index, style, script]
                if p.exists()
            ).lower()
            if "game over" in all_text and not any(x in all_text for x in ["hidden", "active", "classlist", "restart", "neustart"]):
                logs.append("Warnung: Game-Over-Overlay erkannt, aber kein klarer Hide/Restart-Mechanismus gefunden.")
        except Exception:
            pass

        errors = [x for x in logs if x.startswith("FEHLER:")]
        if errors:
            return "\n".join(logs)
        return "\n".join(logs) if logs else "Statische Browser-Pruefung OK."

    def _fix_browser_project(self, folder: Path, report: str, prompt: str, model: str) -> str:
        files_text = []
        for path in [folder / "index.html", folder / "style.css", folder / "script.js"]:
            if path.exists() and path.is_file():
                try:
                    files_text.append(f"DATEI: {path.name}\n{path.read_text(encoding='utf-8', errors='replace')[:12000]}")
                except Exception:
                    pass
        fix_prompt = f"""
Das Browserprojekt hat Fehler.

Originalauftrag:
{prompt}

Pruefbericht:
{report}

Aktuelle Dateien:
{chr(10).join(files_text)}

Korrigiere nur noetige Dateien. Das Spiel/die Seite muss direkt lokal im Browser starten.
Wenn es ein Spiel ist: kein sofortiges Game Over, Start/Neustart muessen Overlays sauber verstecken.

Antworte NUR als valides JSON:
{{
  "summary": "was wurde korrigiert",
  "files": [
    {{"path": "Dateiname", "content": "vollstaendiger neuer Dateiinhalt"}}
  ]
}}
"""
        raw_fix = self.ollama.complete(
            fix_prompt,
            model=model,
            system="Du bist ein Browser-Game/Web-Fix-Agent. Korrigiere lauffaehig. Antworte strikt als JSON.",
            temperature=0.03,
        )
        fix_data = self._parse_json(raw_fix)
        if not fix_data:
            return "Auto-Fix fehlgeschlagen: Modell lieferte kein valides JSON."
        written = self._write_project_files(folder, fix_data, raw_fix)
        after = self._static_browser_checks(folder)
        return f"Fix angewendet: {fix_data.get('summary', '')}\nDateien: {', '.join(p.name for p in written)}\nNachpruefung:\n{after}"

    def _guess_run_command(self, folder: Path, language: str, run_cmd: str = "") -> str:
        if run_cmd and self._safe_cmd(run_cmd):
            return run_cmd
        if (folder / "build_run.bat").exists():
            return "cmd /c build_run.bat"
        if (folder / "run.bat").exists():
            return "cmd /c run.bat"
        if (folder / "package.json").exists():
            return "cmd /c npm install && npm test --if-present"
        if (folder / "requirements.txt").exists() and (folder / "main.py").exists():
            return "cmd /c pip install -r requirements.txt && python main.py --help"
        if (folder / "main.py").exists():
            return "cmd /c python main.py --help"
        if (folder / "Main.java").exists():
            return "cmd /c javac Main.java"
        if (folder / "main.cpp").exists():
            if shutil.which("g++"):
                return "cmd /c g++ main.cpp -std=c++20 -O2 -Wall -Wextra -o app.exe"
            return ""
        return ""

    def _safe_cmd(self, cmd: str) -> bool:
        low = (cmd or "").lower()
        blocked = ["del ", "erase", "format", "shutdown", "rm -rf", "rmdir", "powershell -enc", "curl |", "wget |"]
        return not any(x in low for x in blocked)

    def _show_project_folder(self, folder: Path):
        try:
            if os.name == "nt":
                os.startfile(str(folder))
        except Exception:
            pass

    def _git_snapshot(self, folder: Path) -> str:
        if not shutil.which("git"):
            return "Git nicht gefunden."
        try:
            subprocess.run("git init", cwd=str(folder), shell=True, capture_output=True, text=True, timeout=30)
            subprocess.run("git add .", cwd=str(folder), shell=True, capture_output=True, text=True, timeout=30)
            result = subprocess.run('git commit -m "Jarvis initial version"', cwd=str(folder), shell=True, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                return "Git-Version erstellt."
            return (result.stderr or result.stdout or "Git Commit nicht erstellt.").strip()[:1000]
        except Exception as e:
            return f"Git-Fehler: {e}"

    def _select_model(self, prompt: str, prefer_debug: bool = False) -> str:
        t = (prompt or "").lower()
        beast_words = [
            "beste", "stärkste", "maximal", "beast", "enterprise", "großes projekt",
            "komplex", "compiler", "engine", "framework", "full stack", "production"
        ]
        fast_words = ["schnell", "kurz", "klein", "einfach", "nur beispiel"]
        if any(w in t for w in beast_words):
            return OLLAMA_BEAST_CODE_MODEL or OLLAMA_MAX_CODE_MODEL
        if any(w in t for w in fast_words):
            return OLLAMA_AGENT_CODE_MODEL or OLLAMA_CODE_MODEL
        if prefer_debug:
            return OLLAMA_STRONG_CODE_MODEL or OLLAMA_CODE_MODEL
        return OLLAMA_CODE_MODEL

    def _detect_language(self, prompt: str) -> str:
        t = prompt.lower()
        if any(x in t for x in ["c++", "cpp", "c plus plus", "cc plus plus"]):
            return "C++"
        if any(x in t for x in ["c#", "csharp", "c sharp"]):
            return "C#"
        if "python" in t:
            return "Python"
        if re.search(r"\bjava\b", t):
            return "Java"
        if "typescript" in t:
            return "TypeScript"
        if "javascript" in t or "node" in t:
            return "JavaScript"
        if "rust" in t:
            return "Rust"
        if re.search(r"\bgo\b", t) or "golang" in t:
            return "Go"
        if "php" in t:
            return "PHP"
        if "sql" in t:
            return "SQL"
        if "powershell" in t:
            return "PowerShell"
        if "batch" in t or ".bat" in t:
            return "Batch"
        if "html" in t or "css" in t or "webseite" in t:
            return "HTML/CSS/JavaScript"
        return "gewünschte Sprache"

    def _rules_for_language(self, language: str) -> str:
        l = language.lower()
        if "c++" in l:
            return (
                "- Erzeuge main.cpp.\n"
                "- Erzeuge build_run.bat mit Compiler-Erkennung.\n"
                "- Bevorzugt g++: g++ main.cpp -std=c++20 -O2 -Wall -Wextra -o app.exe.\n"
                "- Wenn g++ fehlt, Hinweis auf Visual Studio Build Tools oder MinGW.\n"
                "- Verwende moderne C++20-Struktur.\n"
            )
        if "python" in l:
            return "- Erzeuge main.py.\n- Erzeuge run.bat.\n- Falls Pakete nötig sind, requirements.txt erzeugen.\n"
        if l == "java":
            return "- Erzeuge Main.java.\n- Erzeuge build_run.bat mit javac Main.java und java Main.\n"
        if "c#" in l:
            return "- Erzeuge Program.cs.\n- Erzeuge build_run.bat mit dotnet run oder csc.\n"
        if "javascript" in l or "typescript" in l:
            return "- Erzeuge package.json, src-Dateien und run.bat, falls Node-Projekt.\n"
        if "html" in l:
            return "- Erzeuge index.html, style.css, script.js.\n"
        return "- Erzeuge sinnvolle Projektdateien und eine run.bat oder README mit Startbefehl.\n"

    def _safe_kind(self, language: str) -> str:
        return re.sub(r"[^a-z0-9]+", "_", language.lower()).strip("_") or "project"

    def _looks_like_model_error(self, text: str) -> bool:
        low = (text or "").lower()
        return any(x in low for x in [
            "ollama-fehler",
            "server error",
            "serverfehler",
            "failed to allocate",
            "unable to allocate",
            "cuda_host",
            "nicht erreichbar",
        ])

    def _parse_json(self, text: str):
        text = text.strip()
        text = re.sub(r"^```(?:json)?", "", text, flags=re.I).strip()
        text = re.sub(r"```$", "", text).strip()
        try:
            return json.loads(text)
        except Exception:
            pass
        m = re.search(r"\{.*\}", text, flags=re.S)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                return None
        return None
