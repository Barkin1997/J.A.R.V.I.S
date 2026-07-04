import os
import subprocess
import time
from pathlib import Path

import pyautogui

from config import WINDOWS_AGENT_SCREENSHOT_DIR, OCR_LANGUAGE, OLLAMA_VISION_MODEL


class WindowsAppAgentV2:
    def __init__(self, ollama=None):
        self.ollama = ollama
        self.screenshot_dir = WINDOWS_AGENT_SCREENSHOT_DIR
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)

    def list_windows(self) -> str:
        try:
            import pygetwindow as gw
            wins = [w for w in gw.getAllTitles() if w and w.strip()]
            if not wins:
                return "Keine sichtbaren Fenster gefunden."
            return "Fenster:\n" + "\n".join(f"- {w}" for w in wins[:80])
        except Exception as e:
            return f"Fensterliste nicht verfügbar: {e}"

    def focus_window(self, title: str) -> str:
        title = (title or "").strip()
        if not title:
            return "Fenstertitel fehlt."
        try:
            import pygetwindow as gw
            wins = gw.getWindowsWithTitle(title)
            if not wins:
                return f"Fenster nicht gefunden: {title}"
            win = wins[0]
            if win.isMinimized:
                win.restore()
            win.activate()
            time.sleep(0.5)
            return f"Fenster aktiviert: {win.title}"
        except Exception as e:
            return f"Fenster konnte nicht aktiviert werden: {e}"

    def open_app(self, app: str) -> str:
        app = (app or "").strip()
        if not app:
            return "Programmname fehlt."
        try:
            subprocess.Popen(app, shell=True)
            return f"Programm gestartet: {app}"
        except Exception as e:
            return f"Programmstart fehlgeschlagen: {e}"

    def screenshot(self) -> str:
        path = self.screenshot_dir / f"screen_{time.strftime('%Y%m%d_%H%M%S')}.png"
        img = pyautogui.screenshot()
        img.save(path)
        return str(path)

    def read_screen_ocr(self) -> str:
        path = self.screenshot()
        try:
            import pytesseract
            from PIL import Image
            text = pytesseract.image_to_string(Image.open(path), lang=OCR_LANGUAGE)
            if text.strip():
                return f"OCR-Screenshot: {path}\n\n{text.strip()[:8000]}"
            return f"OCR hat keinen Text gefunden. Screenshot: {path}"
        except Exception as e:
            if self.ollama:
                try:
                    answer = self.ollama.vision(
                        "Lies den Text auf diesem Screenshot. Antworte auf Deutsch. Wenn kein Text lesbar ist, sag es.",
                        image_path=path,
                        model=OLLAMA_VISION_MODEL
                    )
                    return f"OCR-Fallback Vision. Screenshot: {path}\n\n{answer}"
                except Exception as e2:
                    return f"OCR nicht verfügbar: {e}\nVision-Fallback fehlgeschlagen: {e2}\nScreenshot: {path}"
            return f"OCR nicht verfügbar: {e}\nInstalliere Tesseract oder nutze Vision-Fallback."

    def click_text(self, text: str) -> str:
        text = (text or "").strip()
        if not text:
            return "Text zum Klicken fehlt."
        path = self.screenshot()
        try:
            import pytesseract
            from PIL import Image
            data = pytesseract.image_to_data(Image.open(path), lang=OCR_LANGUAGE, output_type=pytesseract.Output.DICT)
            wanted = text.lower()
            for i, word in enumerate(data.get("text", [])):
                if word and wanted in word.lower():
                    x = data["left"][i] + data["width"][i] // 2
                    y = data["top"][i] + data["height"][i] // 2
                    pyautogui.click(x, y)
                    return f"Geklickt auf Text '{word}' bei {x},{y}."
            return f"Text nicht gefunden: {text}. Screenshot: {path}"
        except Exception as e:
            return f"OCR-Klick nicht möglich: {e}. Screenshot: {path}"

    def type_text(self, text: str) -> str:
        pyautogui.write(text, interval=0.01)
        return "Text geschrieben."

    def hotkey(self, keys: str) -> str:
        parts = [x.strip().lower() for x in keys.replace("+", " ").split() if x.strip()]
        if not parts:
            return "Hotkey fehlt."
        pyautogui.hotkey(*parts)
        return "Hotkey gedrückt: " + " + ".join(parts)
