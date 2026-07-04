import subprocess
import sys
import time
from pathlib import Path

from config import CRASH_LOG_DIR, CRASH_RESTART_DELAY

ROOT = Path(__file__).resolve().parent
LOG = CRASH_LOG_DIR / "jarvis_crash_watcher.log"
STATE = CRASH_LOG_DIR / "last_run_state.txt"


def log(msg: str):
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{stamp}] {msg}\n"
    print(line, end="")
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line)


def main():
    log("Crash-Watcher gestartet.")
    while True:
        STATE.write_text("Jarvis wird gestartet: " + time.strftime("%Y-%m-%d %H:%M:%S"), encoding="utf-8")
        cmd = [sys.executable, "app.py"]
        log("Starte Jarvis...")
        proc = subprocess.Popen(cmd, cwd=str(ROOT))
        code = proc.wait()
        log(f"Jarvis beendet. Exit-Code: {code}")

        if code == 0:
            log("Normal beendet. Crash-Watcher stoppt.")
            break

        STATE.write_text(f"Letzter Crash Exit-Code {code} um {time.strftime('%Y-%m-%d %H:%M:%S')}", encoding="utf-8")
        log(f"Crash erkannt. Neustart in {CRASH_RESTART_DELAY} Sekunden...")
        time.sleep(CRASH_RESTART_DELAY)


if __name__ == "__main__":
    main()
