import os
import shutil
import time
from pathlib import Path

from config import BASE_DIR


class JarvisCleanup:
    """Safe cleanup for generated runtime files only."""

    def __init__(self):
        self.root = Path(BASE_DIR).resolve()
        self.protected_names = {
            ".git",
            ".venv",
            "assets",
            "data",
            "external",
            "jarvis_3d_webgl",
            "models",
            "plugins",
            "skills",
        }

    def clean(self, request: str = "") -> str:
        request_low = (request or "").lower()
        aggressive = any(term in request_low for term in ["alles", "komplett", "voll"])
        log_days = 0 if aggressive else int(os.getenv("JARVIS_CLEANUP_LOG_DAYS", "1"))

        deleted_files = 0
        deleted_dirs = 0
        freed_bytes = 0
        notes = []

        for pycache in self._iter_pycache_dirs():
            stats = self._delete_path(pycache)
            deleted_files += stats[0]
            deleted_dirs += stats[1]
            freed_bytes += stats[2]

        for cache_dir in [self.root / ".aider.tags.cache.v4", self.root / "sandbox_runs"]:
            if cache_dir.exists():
                stats = self._delete_path(cache_dir)
                deleted_files += stats[0]
                deleted_dirs += stats[1]
                freed_bytes += stats[2]

        stats = self._clean_logs(log_days)
        deleted_files += stats[0]
        deleted_dirs += stats[1]
        freed_bytes += stats[2]

        notes.append("Chats, Modelle, external, skills, jarvis_3d_webgl und .env wurden nicht geloescht.")
        notes.append("Jarvis_Projects wird nicht bereinigt. Diesen Ordner loeschst du selbst.")
        if not aggressive:
            notes.append(f"Logs nur aelter als {log_days} Tag(e).")
        else:
            notes.append("Komplett-Modus: nur Cache-/Log-Dateien entfernt, keine Projekt-Ausgaben.")

        mb = freed_bytes / (1024 * 1024)
        return (
            "Jarvis-Aufraeumen fertig.\n"
            f"- Dateien entfernt: {deleted_files}\n"
            f"- Ordner entfernt: {deleted_dirs}\n"
            f"- Speicher frei: {mb:.1f} MB\n"
            + "\n".join(f"- {note}" for note in notes)
        )

    def _is_safe(self, path: Path) -> bool:
        try:
            resolved = path.resolve()
        except Exception:
            return False
        if resolved == self.root:
            return False
        if self.root not in resolved.parents:
            return False
        rel_parts = resolved.relative_to(self.root).parts
        if not rel_parts:
            return False
        return rel_parts[0] not in self.protected_names

    def _iter_pycache_dirs(self):
        skip = {"external", ".venv", "models", "data"}
        for path in self.root.rglob("__pycache__"):
            try:
                rel = path.relative_to(self.root)
            except Exception:
                continue
            if rel.parts and rel.parts[0] in skip:
                continue
            if path.is_dir():
                yield path

    def _delete_path(self, path: Path):
        if not self._is_safe(path):
            return (0, 0, 0)
        if not path.exists():
            return (0, 0, 0)
        files = 0
        dirs = 0
        size = 0
        if path.is_file() or path.is_symlink():
            try:
                size = path.stat().st_size
                path.unlink()
                return (1, 0, size)
            except Exception:
                return (0, 0, 0)

        for child in path.rglob("*"):
            try:
                if child.is_file() or child.is_symlink():
                    files += 1
                    size += child.stat().st_size
            except Exception:
                pass
        try:
            shutil.rmtree(path)
            dirs = 1
        except Exception:
            return (0, 0, 0)
        return (files, dirs, size)

    def _clean_logs(self, days: int):
        logs = self.root / "logs"
        if not logs.exists():
            return (0, 0, 0)
        cutoff = time.time() - max(0, days) * 86400
        totals = [0, 0, 0]
        for path in list(logs.glob("*")):
            try:
                if path.stat().st_mtime > cutoff:
                    continue
            except Exception:
                continue
            stats = self._delete_path(path)
            totals[0] += stats[0]
            totals[1] += stats[1]
            totals[2] += stats[2]
        return tuple(totals)
