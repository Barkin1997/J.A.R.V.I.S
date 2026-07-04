import json
import re
import subprocess
from pathlib import Path

from config import OLLAMA_CODE_MODEL


class TestGenerator:
    def __init__(self, ollama):
        self.ollama = ollama

    def generate_tests(self, path_text: str, goal: str = "") -> str:
        root = Path((path_text or "").strip().strip('"')).expanduser()
        if not root.exists() or not root.is_dir():
            return f"Projektordner nicht gefunden: {root}"

        files = self._read_project(root)
        prompt = f"""
Erstelle passende Tests für dieses Projekt.

Projektziel:
{goal}

Projektdateien:
{files}

Antworte NUR JSON:
{{
  "summary": "kurz",
  "run": "Test-Befehl",
  "files": [
    {{"path": "relativer/pfad", "content": "vollständiger Dateiinhalt"}}
  ]
}}

Regeln:
- Python: pytest bevorzugen.
- JavaScript/Node: package.json test script oder einfache test-Datei.
- C++: einfache test_main.cpp oder CTest-Struktur.
- Java: JUnit-Struktur oder einfache Testklasse, falls kein Buildsystem.
- C#: dotnet test, falls csproj vorhanden.
- Keine gefährlichen Befehle.
"""
        raw = self.ollama.complete(prompt, model=OLLAMA_CODE_MODEL, system="Du bist Test-Generator-Agent. Nur JSON.", temperature=0.02)
        data = self._parse_json(raw)
        if not data:
            return "Test-Generator: Kein valides JSON erhalten.\n\n" + raw[:4000]

        written = []
        for item in data.get("files", []):
            rel = str(item.get("path", "")).replace("\\", "/").strip()
            if not rel or rel.startswith("/") or ".." in Path(rel).parts:
                continue
            target = root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(item.get("content", ""), encoding="utf-8")
            written.append(str(target))

        run = data.get("run", "").strip()
        run_log = ""
        if run and self._safe_cmd(run):
            run_log = self._run(root, run)

        return (
            f"Tests erstellt: {root}\n"
            f"{data.get('summary','')}\n"
            f"Dateien:\n" + "\n".join(written) +
            (f"\n\nTestlauf:\n{run_log}" if run_log else "")
        ).strip()

    def _read_project(self, root: Path) -> str:
        exts = {".py", ".js", ".ts", ".cpp", ".h", ".hpp", ".java", ".cs", ".go", ".rs", ".php", ".json", ".md", ".html", ".css"}
        skip = {".git", ".venv", "node_modules", "__pycache__", "dist", "build"}
        parts = []
        for p in root.rglob("*"):
            if any(part in skip for part in p.parts):
                continue
            if p.is_file() and p.suffix.lower() in exts:
                try:
                    parts.append(f"--- {p.relative_to(root)} ---\n{p.read_text(encoding='utf-8', errors='ignore')[:10000]}")
                    if len(parts) >= 80:
                        break
                except Exception:
                    pass
        return "\n\n".join(parts)

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

    def _safe_cmd(self, cmd: str) -> bool:
        low = cmd.lower()
        blocked = ["del ", "erase", "format", "shutdown", "rm -rf", "rmdir", "diskpart", "reg delete"]
        return not any(x in low for x in blocked)

    def _run(self, root: Path, cmd: str) -> str:
        try:
            result = subprocess.run(cmd, cwd=str(root), shell=True, text=True, capture_output=True, timeout=180)
            return f"Exit-Code: {result.returncode}\nSTDOUT:\n{result.stdout[:4000]}\nSTDERR:\n{result.stderr[:4000]}".strip()
        except Exception as e:
            return f"Testlauf-Fehler: {e}"
