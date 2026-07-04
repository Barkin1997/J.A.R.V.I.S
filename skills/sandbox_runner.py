import os
import re
import shutil
import subprocess
import time
from pathlib import Path

from config import SANDBOX_DIR, SANDBOX_TIMEOUT


BLOCKED = [
    "format", "diskpart", "shutdown", "restart-computer", "reg delete",
    "del /s", "rmdir /s", "rm -rf", "erase", "cipher /w",
    "takeown", "icacls", "bcdedit", "powershell -enc"
]


class SandboxRunner:
    def __init__(self):
        self.root = SANDBOX_DIR
        self.root.mkdir(parents=True, exist_ok=True)

    def run_project(self, project_path: str, command: str = "") -> str:
        src = Path((project_path or "").strip().strip('"')).expanduser()
        if not src.exists() or not src.is_dir():
            return f"Sandbox: Projektordner nicht gefunden: {src}"

        if command and self._dangerous(command):
            return "Sandbox blockiert: gefährlicher Befehl erkannt."

        run_id = time.strftime("%Y%m%d_%H%M%S")
        target = self.root / f"run_{run_id}_{self._safe_name(src.name)}"

        ignore = shutil.ignore_patterns(
            ".git", ".venv", "node_modules", "__pycache__", "dist", "build",
            "*.exe", "*.dll", "*.obj", "*.o", "*.class"
        )
        shutil.copytree(src, target, ignore=ignore)

        cmd = command.strip() or self._guess_command(target)
        if not cmd:
            return f"Sandbox erstellt: {target}\nKein sicherer Start-/Build-Befehl erkannt."

        code, out = self._run(target, cmd)
        return f"Sandbox: {target}\nBefehl: {cmd}\nExit-Code: {code}\n\n{out[:8000]}"

    def run_command(self, command: str) -> str:
        command = (command or "").strip()
        if not command:
            return "Sandbox: Befehl fehlt."
        if self._dangerous(command):
            return "Sandbox blockiert: gefährlicher Befehl erkannt."

        run_id = time.strftime("%Y%m%d_%H%M%S")
        target = self.root / f"cmd_{run_id}"
        target.mkdir(parents=True, exist_ok=True)

        code, out = self._run(target, command)
        return f"Sandbox: {target}\nBefehl: {command}\nExit-Code: {code}\n\n{out[:8000]}"

    def _guess_command(self, folder: Path) -> str:
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
            return "cmd /c g++ main.cpp -std=c++20 -O2 -Wall -Wextra -o app.exe"
        return ""

    def _run(self, folder: Path, command: str):
        try:
            env = os.environ.copy()
            env["JARVIS_SANDBOX"] = "1"
            result = subprocess.run(
                command,
                cwd=str(folder),
                shell=True,
                text=True,
                capture_output=True,
                timeout=SANDBOX_TIMEOUT,
                env=env,
            )
            out = ""
            if result.stdout:
                out += "STDOUT:\n" + result.stdout
            if result.stderr:
                out += "\nSTDERR:\n" + result.stderr
            return result.returncode, out.strip()
        except subprocess.TimeoutExpired:
            return 124, f"Timeout nach {SANDBOX_TIMEOUT} Sekunden."
        except Exception as e:
            return 1, f"Sandbox-Fehler: {e}"

    def _dangerous(self, command: str) -> bool:
        low = command.lower()
        return any(x in low for x in BLOCKED)

    def _safe_name(self, name: str) -> str:
        return re.sub(r"[^a-zA-Z0-9_-]+", "_", name)[:60] or "project"
