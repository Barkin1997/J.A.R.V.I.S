import os


class ModelRouter:
    def __init__(self):
        self.fast_code = os.getenv("JARVIS_FAST_CODE_MODEL", "qwen3-coder:30b")
        self.default_code = os.getenv("JARVIS_DEFAULT_CODE_MODEL", "qwen3-coder-next:latest")
        self.heavy_code = os.getenv("JARVIS_HEAVY_CODE_MODEL", "qwen3-coder:480b")
        self.vision = os.getenv("OLLAMA_VISION_MODEL", "llava:13b")
        self.chat = os.getenv("OLLAMA_TEXT_MODEL", self.default_code)

    def choose(self, task: str, mode: str = "chat") -> str:
        low = (task or "").lower()
        if any(x in low for x in ["bild", "foto", "screenshot", "vision", "analysiere bild"]):
            return self.vision
        if any(x in low for x in ["schnell", "klein", "kurz", "nur status", "nur frage"]):
            return self.fast_code
        if any(x in low for x in [
            "architektur", "komplett", "alles", "grosse", "grosses",
            "refactor", "refaktor", "sehr schwer", "maximal", "ultra",
        ]):
            if os.getenv("JARVIS_ALLOW_480B_AUTO", "0") == "1":
                return self.heavy_code
            return self.default_code
        if mode in {"coding", "code"}:
            return self.default_code
        return self.chat

    def status(self) -> str:
        return (
            "MODELL-ROUTER\n"
            f"- Chat/Standard: {self.chat}\n"
            f"- Coding: {self.default_code}\n"
            f"- Schnell: {self.fast_code}\n"
            f"- Schwer optional: {self.heavy_code} ({'AN' if os.getenv('JARVIS_ALLOW_480B_AUTO', '0') == '1' else 'AUS'})\n"
            f"- Vision: {self.vision}\n"
            "Hinweis: 480B startet nur automatisch, wenn JARVIS_ALLOW_480B_AUTO=1 gesetzt ist."
        )
