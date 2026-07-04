import shutil
import subprocess
import time
import zipfile
from pathlib import Path

from config import PROJECT_BACKUP_DIR


class ProjectRollback:
    def __init__(self):
        self.backup_dir = PROJECT_BACKUP_DIR
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def backup(self, project_path: str, label: str = "") -> str:
        root = Path((project_path or "").strip().strip('"')).expanduser()
        if not root.exists() or not root.is_dir():
            return f"Projektordner nicht gefunden: {root}"

        label_safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in (label or "backup"))[:60]
        out = self.backup_dir / f"{root.name}_{label_safe}_{time.strftime('%Y%m%d_%H%M%S')}.zip"

        skip = {".git", ".venv", "node_modules", "__pycache__", "dist", "build"}
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
            for p in root.rglob("*"):
                rel = p.relative_to(root)
                if any(part in skip for part in rel.parts):
                    continue
                if p.is_file():
                    z.write(p, rel)

        self._git_commit(root, label or "Jarvis backup")
        return f"Backup erstellt: {out}"

    def restore_latest(self, project_path: str) -> str:
        root = Path((project_path or "").strip().strip('"')).expanduser()
        if not root.exists() or not root.is_dir():
            return f"Projektordner nicht gefunden: {root}"

        backups = sorted(self.backup_dir.glob(f"{root.name}_*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not backups:
            return f"Kein Backup gefunden für: {root.name}"

        latest = backups[0]
        before = self.backup(str(root), "before_restore")

        skip_delete = {".git"}
        for p in root.iterdir():
            if p.name in skip_delete:
                continue
            if p.is_dir():
                shutil.rmtree(p)
            else:
                p.unlink()

        with zipfile.ZipFile(latest, "r") as z:
            z.extractall(root)

        return f"Wiederhergestellt aus: {latest}\nSicherheitsbackup vor Restore:\n{before}"

    def git_rollback(self, project_path: str) -> str:
        root = Path((project_path or "").strip().strip('"')).expanduser()
        if not root.exists():
            return f"Projektordner nicht gefunden: {root}"
        if not (root / ".git").exists():
            return "Kein Git-Repository gefunden."
        try:
            result = subprocess.run("git reset --hard HEAD~1", cwd=str(root), shell=True, text=True, capture_output=True, timeout=60)
            return f"Git Rollback Exit {result.returncode}\n{result.stdout}\n{result.stderr}".strip()
        except Exception as e:
            return f"Git Rollback Fehler: {e}"

    def _git_commit(self, root: Path, message: str):
        try:
            subprocess.run("git init", cwd=str(root), shell=True, capture_output=True, text=True, timeout=30)
            subprocess.run("git add .", cwd=str(root), shell=True, capture_output=True, text=True, timeout=30)
            subprocess.run(f'git commit -m "{message}"', cwd=str(root), shell=True, capture_output=True, text=True, timeout=30)
        except Exception:
            pass
