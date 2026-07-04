import subprocess
from pathlib import Path
from typing import List
import pyautogui
from PIL import ImageGrab
from config import PROJECT_DIR

class PCSkill:
    def open_program(self, name_or_path: str) -> str:
        target = name_or_path.strip().strip('"')
        if not target:
            return "Programmname fehlt."
        known = {
            "notepad": "notepad.exe", "editor": "notepad.exe",
            "rechner": "calc.exe", "calculator": "calc.exe",
            "cmd": "cmd.exe", "terminal": "cmd.exe",
            "explorer": "explorer.exe", "dateimanager": "explorer.exe",
            "paint": "mspaint.exe"
        }
        cmd = known.get(target.lower(), target)
        try:
            subprocess.Popen(cmd, shell=True)
            return f"Programm gestartet: {target}"
        except Exception as e:
            return f"Programm konnte nicht gestartet werden: {e}"

    def search_files(self, query: str, base: str = None, limit: int = 40) -> str:
        query = (query or "").lower().strip()
        if not query:
            return "Suchbegriff fehlt."
        roots = []
        if base:
            roots.append(Path(base).expanduser())
        else:
            home = Path.home()
            roots.extend([home / "Desktop", home / "Downloads", home / "Documents", home / "OneDrive", PROJECT_DIR])
        results: List[str] = []
        for root in roots:
            if not root.exists():
                continue
            try:
                for p in root.rglob("*"):
                    if len(results) >= limit:
                        break
                    if query in p.name.lower():
                        results.append(str(p))
            except Exception:
                continue
        return "Keine Dateien gefunden." if not results else "Gefundene Dateien:\n" + "\n".join(results)

    def create_folder(self, folder: str) -> str:
        p = Path(folder.strip().strip('"')).expanduser()
        if not p.is_absolute():
            p = PROJECT_DIR / p
        p.mkdir(parents=True, exist_ok=True)
        return f"Ordner erstellt: {p}"

    def screenshot(self) -> str:
        folder = PROJECT_DIR / "screenshots"
        folder.mkdir(parents=True, exist_ok=True)
        file = folder / "screenshot.png"
        ImageGrab.grab().save(file)
        return f"Screenshot gespeichert: {file}"

    def switch_window(self) -> str:
        pyautogui.hotkey("alt", "tab")
        return "Fenster gewechselt."

    def type_text(self, text: str) -> str:
        pyautogui.write(text, interval=0.01)
        return "Text geschrieben."

    def press(self, key: str) -> str:
        pyautogui.press(key)
        return f"Taste gedrückt: {key}"
