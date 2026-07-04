import json
import os
import subprocess
import sys
import time
from pathlib import Path

from config import BASE_DIR

try:
    from skills.reliability_guard import ReliabilityGuard
    from skills.service_watcher import ServiceWatcher
except Exception:
    ReliabilityGuard = None
    ServiceWatcher = None


class AutoRepair:
    """Safe automatic repair for Jarvis runtime state.

    This module fixes things that are safe to repair automatically. It does not
    blindly rewrite source code. If source syntax is broken, it records the error
    so the coding guard can repair with backup/test flow.
    """

    def __init__(self):
        self.root = Path(BASE_DIR).resolve()
        self.data_dir = self.root / "data"
        self.logs_dir = self.root / "logs"
        self.report_file = self.data_dir / "auto_repair_report.json"
        self.lock_file = self.data_dir / "auto_repair.lock"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)

    def run(self, reason: str = "manual", start_services: bool = True) -> str:
        if self._lock_active():
            return "AUTO-REPARATUR: laeuft bereits. Ich starte keine zweite Reparatur."
        self._write_lock(reason)
        actions = []
        warnings = []
        errors = []
        try:
            actions.extend(self._ensure_dirs())
            actions.extend(self._repair_runtime_json())
            actions.extend(self._repair_stale_locks())

            syntax = self._syntax_check()
            if syntax["state"] == "OK":
                actions.append(syntax["detail"])
            else:
                errors.append(syntax["detail"])

            service_result = self._service_repair(start_services=start_services)
            if service_result.startswith("WARNUNG"):
                warnings.append(service_result)
            elif service_result.startswith("FEHLER"):
                errors.append(service_result)
            else:
                actions.append(service_result)

            reliability = self._refresh_reliability()
            if reliability.startswith("WARNUNG"):
                warnings.append(reliability)
            elif reliability.startswith("FEHLER"):
                errors.append(reliability)
            else:
                actions.append(reliability)

            state = "OK" if not errors else "PRUEFEN"
            report = {
                "updated_at": time.time(),
                "updated_at_text": time.strftime("%Y-%m-%d %H:%M:%S"),
                "reason": reason,
                "state": state,
                "actions": actions,
                "warnings": warnings,
                "errors": errors,
            }
            self._write_report(report)

            lines = [
                "AUTO-REPARATUR",
                f"Status: {state}",
                f"Aktionen: {len(actions)} | Warnungen: {len(warnings)} | Fehler: {len(errors)}",
            ]
            if actions:
                lines.append("\nREPARIERT/GEPRUEFT:")
                lines.extend(f"- {item}" for item in actions[:12])
            if warnings:
                lines.append("\nWARNUNGEN:")
                lines.extend(f"- {item}" for item in warnings[:8])
            if errors:
                lines.append("\nFEHLER:")
                lines.extend(f"- {item}" for item in errors[:8])
            lines.append(f"\nReport: {self.report_file}")
            return "\n".join(lines)
        finally:
            try:
                self.lock_file.unlink(missing_ok=True)
            except Exception:
                pass

    def status(self) -> str:
        try:
            if not self.report_file.exists():
                return "noch kein Auto-Reparatur-Report"
            data = json.loads(self.report_file.read_text(encoding="utf-8", errors="replace") or "{}")
            return (
                f"{data.get('state', 'unbekannt')} - "
                f"Aktionen={len(data.get('actions') or [])}, "
                f"Warnungen={len(data.get('warnings') or [])}, "
                f"Fehler={len(data.get('errors') or [])}, "
                f"Zeit={data.get('updated_at_text', '?')}"
            )
        except Exception as e:
            return f"Auto-Reparatur-Status nicht lesbar: {e}"

    def _ensure_dirs(self):
        dirs = [
            self.data_dir,
            self.logs_dir,
            self.root / "project_backups" / "aider",
            self.root / "data" / "work_logs",
            self.root / "data" / "screenshots",
            self.root / "Jarvis_Projects",
        ]
        actions = []
        for path in dirs:
            if not path.exists():
                path.mkdir(parents=True, exist_ok=True)
                actions.append(f"Ordner erstellt: {path}")
        if not actions:
            actions.append("Pflichtordner OK")
        return actions

    def _repair_runtime_json(self):
        defaults = {
            self.data_dir / "coding_dashboard.json": {
                "state": "idle",
                "summary": "Noch kein Coding-Auftrag.",
                "changed_files": [],
            },
            self.data_dir / "service_status.json": {
                "updated_at": time.time(),
                "services": {},
            },
        }
        actions = []
        for path, default in defaults.items():
            if not path.exists():
                path.write_text(json.dumps(default, ensure_ascii=False, indent=2), encoding="utf-8")
                actions.append(f"Statusdatei erstellt: {path.name}")
                continue
            try:
                json.loads(path.read_text(encoding="utf-8", errors="replace") or "{}")
            except Exception:
                bad = path.with_suffix(path.suffix + f".bad_{time.strftime('%Y%m%d_%H%M%S')}")
                path.rename(bad)
                path.write_text(json.dumps(default, ensure_ascii=False, indent=2), encoding="utf-8")
                actions.append(f"Kaputte Statusdatei gesichert und neu erstellt: {path.name}")
        if not actions:
            actions.append("Runtime-JSON OK")
        return actions

    def _repair_stale_locks(self):
        specs = [
            ("aider_job.lock", 60 * 45),
            ("ki_video_job.lock", 60 * 60 * 4),
            ("install_real_video_models.lock", 60 * 60 * 8),
            ("jarvis_app.lock", 60 * 60 * 12),
        ]
        actions = []
        for filename, max_age in specs:
            path = self.data_dir / filename
            if not path.exists():
                continue
            age = int(time.time() - path.stat().st_mtime)
            if age <= max_age:
                continue
            stale = path.with_name(f"{path.name}.stale_{time.strftime('%Y%m%d_%H%M%S')}")
            try:
                path.rename(stale)
                actions.append(f"Alter Lock gesichert: {filename} ({age}s)")
            except Exception as e:
                actions.append(f"Alter Lock nicht verschoben: {filename}: {e}")
        if not actions:
            actions.append("Keine haengenden Locks gefunden")
        return actions

    def _syntax_check(self):
        files = [
            self.root / "app.py",
            self.root / "brain.py",
            self.root / "config.py",
            self.root / "voice.py",
            self.root / "skills" / "aider_agent.py",
            self.root / "skills" / "status_center.py",
            self.root / "skills" / "reliability_guard.py",
            self.root / "skills" / "auto_repair.py",
        ]
        files = [str(p) for p in files if p.exists()]
        try:
            result = subprocess.run(
                [sys.executable, "-m", "py_compile", *files],
                cwd=str(self.root),
                text=True,
                capture_output=True,
                timeout=120,
                encoding="utf-8",
                errors="replace",
            )
            output = ((result.stdout or "") + "\n" + (result.stderr or "")).strip()
            if result.returncode == 0:
                return {"state": "OK", "detail": f"Python-Syntax OK ({len(files)} Kernmodule)"}
            return {"state": "FEHLER", "detail": "Python-Syntax FEHLER:\n" + output[:1200]}
        except Exception as e:
            return {"state": "FEHLER", "detail": f"Python-Syntax-Pruefung fehlgeschlagen: {e}"}

    def _service_repair(self, start_services: bool):
        if ServiceWatcher is None:
            return "WARNUNG: ServiceWatcher nicht ladbar"
        try:
            result = ServiceWatcher().ensure_all() if start_services else ServiceWatcher().check()
            lines = [line for line in result.splitlines() if line.strip()]
            off = [line for line in lines if ": AUS" in line]
            if off:
                return "WARNUNG: Dienste nicht bereit: " + "; ".join(off[:4])
            return "Dienste geprueft/gestartet"
        except Exception as e:
            return f"WARNUNG: Dienst-Reparatur fehlgeschlagen: {e}"

    def _refresh_reliability(self):
        if ReliabilityGuard is None:
            return "WARNUNG: ReliabilityGuard nicht ladbar"
        try:
            text = ReliabilityGuard().check()
            first = "\n".join(text.splitlines()[:3])
            if "Ampel: KRITISCH" in text:
                return "FEHLER: " + first
            if "Ampel: PRUEFEN" in text:
                return "WARNUNG: " + first
            return "Zuverlaessigkeits-Check aktualisiert"
        except Exception as e:
            return f"WARNUNG: Zuverlaessigkeits-Check fehlgeschlagen: {e}"

    def _lock_active(self):
        if not self.lock_file.exists():
            return False
        try:
            age = time.time() - self.lock_file.stat().st_mtime
            if age > 60 * 20:
                self.lock_file.rename(self.lock_file.with_name(f"{self.lock_file.name}.stale_{time.strftime('%Y%m%d_%H%M%S')}"))
                return False
        except Exception:
            pass
        return True

    def _write_lock(self, reason: str):
        self.lock_file.write_text(
            json.dumps({"started_at": time.time(), "reason": reason}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _write_report(self, report: dict):
        try:
            self.report_file.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass
