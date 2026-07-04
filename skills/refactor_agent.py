import json
import re
import subprocess
from pathlib import Path

from config import OLLAMA_CODE_MODEL, REPO_MAX_FILES, REPO_MAX_FILE_CHARS


class RefactorAgent:
    def __init__(self, ollama):
        self.ollama = ollama

    def refactor(self, path_text: str, instruction: str) -> str:
        root = Path((path_text or "").strip().strip('"')).expanduser()
        if not root.exists() or not root.is_dir():
            return f"Projektordner nicht gefunden: {root}"

        files = self._read_project(root)
        prompt = f"""
Refactore dieses Projekt.

Anweisung:
{instruction}

Projekt:
{files}

Antworte NUR JSON:
{{
  "summary": "was wurde refactored",
  "run": "Build/Test-Befehl",
  "files": [
    {{"path": "relativer/pfad", "content": "vollständiger neuer Dateiinhalt"}}
  ]
}}

Ziele:
- Architektur verbessern.
- Duplikate reduzieren.
- Dateien sinnvoll strukturieren.
- Keine Features kaputt machen.
- Build/Test-Befehl liefern.
- Nur nötige Dateien ändern.
"""
        raw = self.ollama.complete(prompt, model=OLLAMA_CODE_MODEL, system="Du bist Refactor-Agent. Nur JSON.", temperature=0.02)
        data = self._parse_json(raw)
        if not data:
            return "Refactor-Agent: Kein valides JSON erhalten.\n\n" + raw[:4000]

        written = []
        for item in data.get("files", []):
            rel = str(item.get("path", "")).replace("\\", "/").strip()
            if not rel or rel.startswith("/") or ".." in Path(rel).parts:
                continue
            target = root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(item.get("content", ""), encoding="utf-8")
            written.append(str(target))

        run_log = ""
        run = data.get("run", "").strip()
        if run and self._safe_cmd(run):
            run_log = self._run(root, run)
        self._git_snapshot(root)

        return (
            f"Refactor fertig: {root}\n"
            f"{data.get('summary','')}\n"
            f"Dateien:\n" + "\n".join(written) +
            (f"\n\nBuild/Test:\n{run_log}" if run_log else "")
        ).strip()

    def _read_project(self, root: Path) -> str:
        exts = {".py", ".js", ".ts", ".html", ".css", ".json", ".md", ".cpp", ".hpp", ".h", ".c", ".cs", ".java", ".go", ".rs", ".php", ".sql", ".bat", ".ps1"}
        skip = {".git", ".venv", "node_modules", "__pycache__", "dist", "build"}
        parts = []
        count = 0
        for p in root.rglob("*"):
            if count >= REPO_MAX_FILES:
                break
            if any(part in skip for part in p.parts):
                continue
            if p.is_file() and p.suffix.lower() in exts:
                try:
                    parts.append(f"--- {p.relative_to(root)} ---\n{p.read_text(encoding='utf-8', errors='ignore')[:REPO_MAX_FILE_CHARS]}")
                    count += 1
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
            return f"Exit-Code: {result.returncode}\n{result.stdout[:4000]}\n{result.stderr[:4000]}".strip()
        except Exception as e:
            return f"Build/Test-Fehler: {e}"

    def _git_snapshot(self, root: Path):
        try:
            subprocess.run("git init", cwd=str(root), shell=True, capture_output=True, text=True, timeout=30)
            subprocess.run("git add .", cwd=str(root), shell=True, capture_output=True, text=True, timeout=30)
            subprocess.run('git commit -m "Jarvis refactor"', cwd=str(root), shell=True, capture_output=True, text=True, timeout=30)
        except Exception:
            pass
