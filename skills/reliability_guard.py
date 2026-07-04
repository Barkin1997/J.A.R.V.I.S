import json
import os
import subprocess
import sys
import time
from pathlib import Path

from config import BASE_DIR

try:
    from skills.service_watcher import ServiceWatcher
except Exception:
    ServiceWatcher = None


class ReliabilityGuard:
    """Central self-check for Jarvis reliability and false-finished prevention."""

    def __init__(self):
        self.root = Path(BASE_DIR).resolve()
        self.data_dir = self.root / "data"
        self.report_file = self.data_dir / "reliability_report.json"
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def check(self) -> str:
        checks = []
        checks.extend(self._required_files_checks())
        checks.append(self._python_compile_check())
        checks.extend(self._dashboard_checks())
        checks.extend(self._coding_safety_checks())
        checks.extend(self._lock_checks())
        checks.append(self._service_check())
        checks.append(self._last_error_check())

        score = self._score(checks)
        state = "OK" if score >= 85 else ("PRUEFEN" if score >= 65 else "KRITISCH")
        report = {
            "updated_at": time.time(),
            "updated_at_text": time.strftime("%Y-%m-%d %H:%M:%S"),
            "score": score,
            "state": state,
            "checks": checks,
        }
        self._write_report(report)

        critical = [c for c in checks if c["state"] == "FEHLER"]
        warnings = [c for c in checks if c["state"] == "WARNUNG"]
        ok_count = len([c for c in checks if c["state"] == "OK"])

        lines = [
            "JARVIS ZUVERLAESSIGKEITS-CHECK",
            f"Ampel: {state}",
            f"Score: {score}/100",
            f"OK: {ok_count} | Warnungen: {len(warnings)} | Fehler: {len(critical)}",
            "",
            "PRUEFUNGEN:",
        ]
        for check in checks:
            lines.append(f"- {check['state']}: {check['name']} - {check['detail']}")
        lines.extend([
            "",
            "REGELN FUER STABILES CODING:",
            "- Kein 'fertig', wenn Tests/Pruefungen Fehler melden.",
            "- Kein 'fertig', wenn ein Aenderungsauftrag keine Datei geaendert hat.",
            "- Bei Fehlern: Auto-Reparatur versuchen oder Rollback-Backup nutzen.",
            "- Bei Web/Spiel: Browser-Check und Console-Fehler pruefen.",
            f"Report: {self.report_file}",
        ])
        return "\n".join(lines)

    def short_status(self) -> str:
        try:
            if not self.report_file.exists():
                return "noch kein Zuverlaessigkeitsreport"
            data = json.loads(self.report_file.read_text(encoding="utf-8", errors="replace") or "{}")
            return f"{data.get('state', 'unbekannt')} - Score {data.get('score', '?')}/100"
        except Exception as e:
            return f"nicht lesbar: {e}"

    def _required_files_checks(self):
        required = [
            "app.py",
            "brain.py",
            "config.py",
            "voice.py",
            "skills/aider_agent.py",
            "skills/status_center.py",
            "skills/service_watcher.py",
            "skills/model_router.py",
            "jarvis_3d_webgl/index.html",
            "jarvis_3d_webgl/coding_dashboard.html",
            "jarvis_3d_webgl/video_dashboard.html",
        ]
        checks = []
        for rel in required:
            path = self.root / rel
            checks.append({
                "name": f"Datei {rel}",
                "state": "OK" if path.exists() else "FEHLER",
                "detail": "vorhanden" if path.exists() else "fehlt",
            })
        return checks

    def _python_compile_check(self):
        files = [
            self.root / "app.py",
            self.root / "brain.py",
            self.root / "config.py",
            self.root / "voice.py",
            self.root / "skills" / "aider_agent.py",
            self.root / "skills" / "status_center.py",
            self.root / "skills" / "service_watcher.py",
            self.root / "skills" / "model_router.py",
            self.root / "skills" / "reliability_guard.py",
        ]
        files = [str(p) for p in files if p.exists()]
        if not files:
            return {"name": "Python-Syntax Kernmodule", "state": "FEHLER", "detail": "keine Dateien gefunden"}
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
                return {"name": "Python-Syntax Kernmodule", "state": "OK", "detail": f"{len(files)} Dateien OK"}
            return {"name": "Python-Syntax Kernmodule", "state": "FEHLER", "detail": output[:800] or "py_compile fehlgeschlagen"}
        except Exception as e:
            return {"name": "Python-Syntax Kernmodule", "state": "FEHLER", "detail": str(e)[:500]}

    def _dashboard_checks(self):
        checks = []
        coding_page = self.root / "jarvis_3d_webgl" / "coding_dashboard.html"
        video_page = self.root / "jarvis_3d_webgl" / "video_dashboard.html"
        checks.append(self._html_check("Coding-Dashboard Seite", coding_page))
        checks.append(self._html_check("Video-Dashboard Seite", video_page))

        coding_json = self.root / "data" / "coding_dashboard.json"
        if coding_json.exists():
            checks.append(self._json_file_check("Coding-Dashboard JSON", coding_json))
        else:
            checks.append({"name": "Coding-Dashboard JSON", "state": "OK", "detail": "noch kein Coding-Auftrag, Datei darf fehlen"})
        return checks

    def _coding_safety_checks(self):
        checks = []
        env_flags = {
            "JARVIS_AIDER_AUTO_ROLLBACK": os.getenv("JARVIS_AIDER_AUTO_ROLLBACK", "1"),
            "JARVIS_AIDER_AUTO_FIX_ERRORS": os.getenv("JARVIS_AIDER_AUTO_FIX_ERRORS", "1"),
            "JARVIS_AUTO_PROJECT_TESTS": os.getenv("JARVIS_AUTO_PROJECT_TESTS", "1"),
            "JARVIS_CODING_SHOW_GIT_DIFF": os.getenv("JARVIS_CODING_SHOW_GIT_DIFF", "1"),
            "JARVIS_AIDER_RETRY_NO_CHANGE": os.getenv("JARVIS_AIDER_RETRY_NO_CHANGE", "1"),
        }
        for name, value in env_flags.items():
            checks.append({
                "name": name,
                "state": "OK" if value == "1" else "WARNUNG",
                "detail": "aktiv" if value == "1" else f"deaktiviert ({value})",
            })
        conf = self.root / ".aider.conf.yml"
        checks.append({
            "name": "Aider-Konfiguration",
            "state": "OK" if conf.exists() else "WARNUNG",
            "detail": str(conf) if conf.exists() else ".aider.conf.yml fehlt",
        })
        return checks

    def _lock_checks(self):
        data_dir = self.root / "data"
        specs = [
            ("aider_job.lock", "Coding-Lock", 60 * 45),
            ("ki_video_job.lock", "KI-Video-Lock", 60 * 60 * 4),
            ("install_real_video_models.lock", "Video-Download-Lock", 60 * 60 * 8),
        ]
        checks = []
        for filename, label, max_age in specs:
            path = data_dir / filename
            if not path.exists():
                checks.append({"name": label, "state": "OK", "detail": "frei"})
                continue
            age = int(time.time() - path.stat().st_mtime)
            state = "WARNUNG" if age > max_age else "OK"
            detail = f"aktiv seit {age}s" if state == "OK" else f"moeglich haengend, Lock {age}s alt"
            checks.append({"name": label, "state": state, "detail": detail})
        return checks

    def _service_check(self):
        if ServiceWatcher is None:
            return {"name": "Service-Waechter", "state": "WARNUNG", "detail": "Modul nicht ladbar"}
        try:
            data = ServiceWatcher().snapshot()
            services = data.get("services", {})
            off = [name for name, info in services.items() if not info.get("ok")]
            if off:
                return {"name": "Service-Waechter", "state": "WARNUNG", "detail": "aus/nicht erreichbar: " + ", ".join(off)}
            return {"name": "Service-Waechter", "state": "OK", "detail": "alle Kerndienste erreichbar/bereit"}
        except Exception as e:
            return {"name": "Service-Waechter", "state": "WARNUNG", "detail": str(e)[:500]}

    def _last_error_check(self):
        logs = self.root / "logs"
        if not logs.exists():
            return {"name": "Letzte Fehlerlogs", "state": "OK", "detail": "kein logs-Ordner"}
        candidates = []
        for pattern in ("*.err.log", "*error*.log", "*.log"):
            candidates.extend(p for p in logs.glob(pattern) if p.is_file())
        if not candidates:
            return {"name": "Letzte Fehlerlogs", "state": "OK", "detail": "keine Logs gefunden"}
        latest = max(set(candidates), key=lambda p: p.stat().st_mtime)
        age = int(time.time() - latest.stat().st_mtime)
        try:
            text = latest.read_text(encoding="utf-8", errors="replace").strip()
            tail = text.splitlines()[-1] if text else "leer"
        except Exception as e:
            tail = f"nicht lesbar: {e}"
        state = "WARNUNG" if age < 3600 and self._looks_like_error(tail) else "OK"
        return {"name": "Letzte Fehlerlogs", "state": state, "detail": f"{latest.name}, {age}s alt: {tail[:240]}"}

    def _html_check(self, name: str, path: Path):
        if not path.exists():
            return {"name": name, "state": "FEHLER", "detail": "fehlt"}
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            return {"name": name, "state": "FEHLER", "detail": f"nicht lesbar: {e}"}
        needed = ["<!doctype", "<html", "</html>"]
        ok = all(part in text.lower() for part in needed)
        return {"name": name, "state": "OK" if ok else "WARNUNG", "detail": "HTML-Grundstruktur OK" if ok else "HTML-Grundstruktur unvollstaendig"}

    def _json_file_check(self, name: str, path: Path):
        try:
            json.loads(path.read_text(encoding="utf-8", errors="replace") or "{}")
            return {"name": name, "state": "OK", "detail": "valides JSON"}
        except Exception as e:
            return {"name": name, "state": "WARNUNG", "detail": f"nicht lesbar/kein JSON: {e}"}

    def _score(self, checks) -> int:
        score = 100
        for check in checks:
            if check["state"] == "FEHLER":
                score -= 18
            elif check["state"] == "WARNUNG":
                score -= 6
        return max(0, min(100, score))

    def _looks_like_error(self, text: str) -> bool:
        low = (text or "").lower()
        return any(word in low for word in ["fehler", "error", "exception", "traceback", "timeout", "failed", "fehlgeschlagen"])

    def _write_report(self, report: dict) -> None:
        try:
            self.report_file.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass
