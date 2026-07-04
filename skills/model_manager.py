import subprocess
from pathlib import Path

ENV_PATH = Path(".env")


PROFILES = {
    "ultra": {
        "OLLAMA_TEXT_MODEL": "qwen3-coder-next:latest",
        "OLLAMA_CODE_MODEL": "qwen3-coder-next:latest",
        "OLLAMA_AGENT_CODE_MODEL": "qwen3-coder-next:latest",
        "OLLAMA_STRONG_CODE_MODEL": "qwen3-coder-next:latest",
        "OLLAMA_BEAST_CODE_MODEL": "qwen3-coder-next:latest",
        "MULTI_AGENT_MODEL": "qwen3-coder-next:latest",
        "INTERNET_RESEARCH_MODEL": "qwen3-coder-next:latest",
        "OLLAMA_EMBED_MODEL": "nomic-embed-text-v2-moe",
        "OLLAMA_NUM_CTX": "65536",
        "OLLAMA_TEMPERATURE": "0.04",
    },
    "agent": {
        "OLLAMA_TEXT_MODEL": "qwen3-next:80b",
        "OLLAMA_CODE_MODEL": "qwen3-coder-next:latest",
        "OLLAMA_AGENT_CODE_MODEL": "qwen3-coder-next:latest",
        "OLLAMA_STRONG_CODE_MODEL": "qwen3-coder:30b",
        "OLLAMA_BEAST_CODE_MODEL": "qwen3-coder-next:latest",
        "MULTI_AGENT_MODEL": "qwen3-coder-next:latest",
        "INTERNET_RESEARCH_MODEL": "qwen3-next:80b",
        "OLLAMA_EMBED_MODEL": "nomic-embed-text-v2-moe",
        "OLLAMA_NUM_CTX": "32768",
        "OLLAMA_TEMPERATURE": "0.05",
    },
    "strong": {
        "OLLAMA_TEXT_MODEL": "qwen3-next:80b",
        "OLLAMA_CODE_MODEL": "qwen3-coder:30b",
        "OLLAMA_AGENT_CODE_MODEL": "qwen3-coder-next:latest",
        "OLLAMA_STRONG_CODE_MODEL": "qwen3-coder:30b",
        "OLLAMA_BEAST_CODE_MODEL": "qwen3-coder-next:latest",
        "MULTI_AGENT_MODEL": "qwen3-coder:30b",
        "INTERNET_RESEARCH_MODEL": "qwen3-next:80b",
        "OLLAMA_EMBED_MODEL": "nomic-embed-text-v2-moe",
        "OLLAMA_NUM_CTX": "32768",
        "OLLAMA_TEMPERATURE": "0.06",
    },
}


class ModelManager:
    def list_profiles(self) -> str:
        return (
            "Model-Profile:\n"
            "- ultra  = qwen3-coder-next:latest, starkes Coding-Modell\n"
            "- agent  = schneller Agent-Modus\n"
            "- strong = stabiler Alltag\n\n"
            "Befehl:\n"
            "Jarvis, modell profil ultra\n"
            "Jarvis, modell profil agent\n"
            "Jarvis, modell profil strong"
        )

    def set_profile(self, name: str) -> str:
        name = (name or "").strip().lower()
        if name not in PROFILES:
            return self.list_profiles()

        if not ENV_PATH.exists():
            if Path(".env.example").exists():
                ENV_PATH.write_text(Path(".env.example").read_text(encoding="utf-8"), encoding="utf-8")
            else:
                ENV_PATH.write_text("", encoding="utf-8")

        text = ENV_PATH.read_text(encoding="utf-8")
        for key, value in PROFILES[name].items():
            if f"{key}=" in text:
                text = self._replace(text, key, value)
            else:
                text += f"\n{key}={value}"
        text = self._replace_or_add(text, "MODEL_MANAGER_PROFILE", name)
        ENV_PATH.write_text(text, encoding="utf-8")
        return f"Modell-Profil aktiviert: {name}\nStarte Jarvis neu, damit alle Einstellungen sicher übernommen werden."

    def pull_profile_models(self, name: str) -> str:
        name = (name or "").strip().lower()
        if name not in PROFILES:
            return self.list_profiles()

        models = []
        for key, value in PROFILES[name].items():
            if key.startswith("OLLAMA_") or key.endswith("_MODEL"):
                if ":" in value or value.startswith("nomic-"):
                    if value not in models:
                        models.append(value)

        logs = []
        for model in models:
            try:
                result = subprocess.run(f"ollama pull {model}", shell=True, text=True, capture_output=True, timeout=36000)
                logs.append(f"{model}: Exit {result.returncode}\n{(result.stdout + result.stderr)[-1200:]}")
            except Exception as e:
                logs.append(f"{model}: Fehler {e}")
        return "\n\n".join(logs)

    def ollama_list(self) -> str:
        try:
            result = subprocess.run("ollama list", shell=True, text=True, capture_output=True, timeout=30)
            return result.stdout or result.stderr or "Keine Ausgabe."
        except Exception as e:
            return f"Ollama list Fehler: {e}"

    def _replace(self, text: str, key: str, value: str) -> str:
        import re
        return re.sub(rf"^{key}=.*$", f"{key}={value}", text, flags=re.M)

    def _replace_or_add(self, text: str, key: str, value: str) -> str:
        if f"{key}=" in text:
            return self._replace(text, key, value)
        return text.rstrip() + f"\n{key}={value}\n"
