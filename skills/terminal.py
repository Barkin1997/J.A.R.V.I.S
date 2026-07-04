import subprocess
from config import PROJECT_DIR
from skills.safety import risky_terminal

class TerminalSkill:
    def run(self, command: str, confirmed: bool = False, timeout: int = 90) -> str:
        command = (command or "").strip()
        if not command:
            return "Terminal-Befehl fehlt."
        if risky_terminal(command) and not confirmed:
            return "Terminal-Befehl blockiert. Risiko für System oder Dateien. Nutze BESTÄTIGE nur bewusst."
        try:
            result = subprocess.run(command, cwd=str(PROJECT_DIR), shell=True, text=True, capture_output=True, timeout=timeout)
            out = result.stdout.strip()
            err = result.stderr.strip()
            text = f"Exit-Code: {result.returncode}\n"
            if out:
                text += f"\nAusgabe:\n{out[:6000]}"
            if err:
                text += f"\nFehler:\n{err[:6000]}"
            return text.strip()
        except subprocess.TimeoutExpired:
            return f"Befehl abgebrochen. Timeout nach {timeout} Sekunden."
        except Exception as e:
            return f"Terminal-Fehler: {e}"
