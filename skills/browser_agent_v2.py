import json
import re
from typing import List

from config import BROWSER_AGENT_MAX_STEPS, BROWSER_AGENT_BLOCK_SUBMIT, OLLAMA_TEXT_MODEL
from ollama_client import OllamaClient
from skills.browser import BrowserSkill


class BrowserAgentV2:
    def __init__(self, browser: BrowserSkill, ollama: OllamaClient):
        self.browser = browser
        self.ollama = ollama

    def run_task(self, task: str) -> str:
        logs = []
        for step in range(BROWSER_AGENT_MAX_STEPS):
            state = self._state()
            plan = self._plan(task, state)
            action = plan.get("action", "read")
            value = plan.get("value", "")
            field = plan.get("field", "")

            if action in {"submit", "buy", "pay", "send"} and BROWSER_AGENT_BLOCK_SUBMIT:
                logs.append("Gestoppt vor finaler riskanter Aktion: " + action)
                break

            if action == "done":
                logs.append("Fertig: " + plan.get("reason", ""))
                break
            if action == "open":
                logs.append(self.browser.goto(value))
            elif action == "google":
                logs.append(self.browser.google(value))
            elif action == "click":
                logs.append(self.browser.click_text(value))
            elif action == "fill":
                logs.append(self.browser.fill_field(field, value))
            elif action == "read":
                page = self.browser.read_page()
                summary = self.ollama.complete(
                    f"Fasse diese Browser-Seite kurz im Kontext der Aufgabe zusammen.\nAufgabe: {task}\n\nSeite:\n{page[:9000]}",
                    model=OLLAMA_TEXT_MODEL,
                    system="Du bist ein Browser-Analyse-Agent. Deutsch, knapp.",
                    temperature=0.05
                )
                logs.append(summary)
                if plan.get("reason", "").lower().startswith("done"):
                    break
            else:
                logs.append("Unbekannte Aktion: " + str(plan))
                break

        return "\n\n".join(logs)

    def _state(self) -> str:
        page = self.browser.read_page()
        return page[:10000]

    def _plan(self, task: str, state: str) -> dict:
        prompt = f"""
Du steuerst einen Browser. Entscheide genau den nächsten Schritt.

Aufgabe:
{task}

Browser-Zustand:
{state}

Erlaubte Aktionen:
- google: Google-Suche öffnen. value=Suchtext
- open: URL öffnen. value=URL
- click: sichtbaren Button/Link klicken. value=Text
- fill: Formularfeld ausfüllen. field=Feldname, value=Text
- read: Seite lesen
- done: Aufgabe fertig
- submit/buy/pay/send: finale Aktion, wird blockiert

Antworte NUR JSON:
{{"action":"...", "field":"...", "value":"...", "reason":"..."}}
"""
        raw = self.ollama.complete(prompt, model=OLLAMA_TEXT_MODEL, system="Du bist ein vorsichtiger Browser-Agent. Nur JSON.", temperature=0.03)
        return self._parse_json(raw) or {"action": "read", "reason": "Fallback"}

    def _parse_json(self, text: str):
        text = text.strip()
        text = re.sub(r"^```(?:json)?", "", text, flags=re.I).strip()
        text = re.sub(r"```$", "", text).strip()
        try:
            return json.loads(text)
        except Exception:
            pass
        m = re.search(r"\{.*\}", text, flags=re.S)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                return None
        return None
