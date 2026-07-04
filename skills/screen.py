import base64
import pyautogui
from config import PROJECT_DIR, OLLAMA_VISION_MODEL
from ollama_client import OllamaClient

class ScreenSkill:
    def __init__(self, ollama: OllamaClient):
        self.ollama = ollama

    def analyze(self, user_prompt: str = "") -> str:
        folder = PROJECT_DIR / "screenshots"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / "screen_current.png"
        img = pyautogui.screenshot()
        img.save(path)
        b64 = base64.b64encode(path.read_bytes()).decode("utf-8")
        prompt = (
            "Du bist ein PC-Assistent. Analysiere den Screenshot. "
            "Erkenne Fenster, Webseiten, Fehlermeldungen, Buttons, sichtbaren Text. "
            "Antworte Deutsch, konkret, ohne erfundene Inhalte.\n\n"
            f"Nutzerauftrag: {user_prompt or 'Lies meinen Bildschirm.'}"
        )
        result = self.ollama.vision(prompt, b64, OLLAMA_VISION_MODEL)
        return f"{result}\n\nScreenshot: {path}"
