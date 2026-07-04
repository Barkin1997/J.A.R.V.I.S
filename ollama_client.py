import requests
from typing import List, Dict, Optional

from config import OLLAMA_URL, OLLAMA_TEXT_MODEL, OLLAMA_NUM_CTX, OLLAMA_TEMPERATURE, OLLAMA_TIMEOUT


class OllamaClient:
    def __init__(self, url: str = OLLAMA_URL):
        self.url = url.rstrip("/")

    def list_models(self):
        try:
            r = requests.get(f"{self.url}/api/tags", timeout=5)
            r.raise_for_status()
            return [m.get("name", "") for m in r.json().get("models", [])]
        except Exception:
            return []

    def chat(
        self,
        messages: List[Dict],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        ctx: Optional[int] = None,
        num_predict: Optional[int] = None,
        timeout: int = OLLAMA_TIMEOUT,
    ) -> str:
        options = {
            "temperature": OLLAMA_TEMPERATURE if temperature is None else temperature,
            "num_ctx": ctx or OLLAMA_NUM_CTX,
        }
        if num_predict:
            options["num_predict"] = int(num_predict)
        payload = {
            "model": model or OLLAMA_TEXT_MODEL,
            "messages": messages,
            "stream": False,
            "options": options,
        }
        try:
            r = requests.post(f"{self.url}/api/chat", json=payload, timeout=timeout)
            r.raise_for_status()
            return r.json().get("message", {}).get("content", "").strip()
        except requests.exceptions.ConnectionError:
            return "Ollama ist nicht erreichbar. Starte Ollama und lade Modelle mit pull_models_rtx5080.bat."
        except requests.exceptions.HTTPError as e:
            if True:
                try:
                    detail = r.text.strip()
                except Exception:
                    detail = str(e)
                return f"Ollama-Fehler beim Modell {payload.get('model')}. Jarvis bleibt auf diesem Modell. {detail}"
            return f"Ollama-Fehler: {e}. Modellname in .env prüfen und Modell laden."
        except Exception as e:
            return f"Ollama-Fehler: {e}"

    def complete(
        self,
        prompt: str,
        model: Optional[str] = None,
        system: str = "",
        temperature: Optional[float] = None,
        ctx: Optional[int] = None,
        num_predict: Optional[int] = None,
        timeout: int = OLLAMA_TIMEOUT,
    ) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return self.chat(messages, model=model, temperature=temperature, ctx=ctx, num_predict=num_predict, timeout=timeout)

    def vision(self, prompt: str, image_base64: str, model: str) -> str:
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt, "images": [image_base64]}],
            "stream": False,
            "options": {"temperature": 0.1, "num_ctx": 8192}
        }
        try:
            r = requests.post(f"{self.url}/api/chat", json=payload, timeout=OLLAMA_TIMEOUT)
            r.raise_for_status()
            return r.json().get("message", {}).get("content", "").strip()
        except Exception as e:
            return f"Vision-Fehler: {e}"
