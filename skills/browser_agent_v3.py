import json
import re

from config import BROWSER_AGENT_MAX_STEPS, BROWSER_AGENT_BLOCK_SUBMIT, INTERNET_RESEARCH_MODEL


class BrowserAgentV3:
    def __init__(self, browser, ollama):
        self.browser = browser
        self.ollama = ollama

    def run_task(self, task: str) -> str:
        logs = []
        for step in range(BROWSER_AGENT_MAX_STEPS):
            state = self._state()
            plan = self._plan(task, state, logs)
            action = str(plan.get("action", "read")).lower()
            value = str(plan.get("value", ""))
            field = str(plan.get("field", ""))
            reason = str(plan.get("reason", ""))

            if action in {"submit", "buy", "pay", "send", "order", "checkout"} and BROWSER_AGENT_BLOCK_SUBMIT:
                logs.append(f"Gestoppt vor finaler Aktion: {action}. Grund: {reason}")
                break

            if action == "done":
                logs.append("Fertig: " + reason)
                break
            if action == "google":
                logs.append(self.browser.google(value))
            elif action == "open":
                logs.append(self.browser.goto(value))
            elif action == "click":
                logs.append(self.browser.click_text(value))
            elif action == "fill":
                logs.append(self.browser.fill_field(field, value))
            elif action == "read":
                page = self.browser.read_page()
                summary = self.ollama.complete(
                    f"Analysiere diese Seite im Kontext der Aufgabe.\nAufgabe: {task}\n\nSeite:\n{page[:12000]}",
                    model=INTERNET_RESEARCH_MODEL,
                    system="Du bist Browser-Agent V3. Deutsch, direkt, nur sichtbare Inhalte.",
                    temperature=0.02
                )
                logs.append(summary)
            else:
                logs.append("Unbekannte Aktion: " + json.dumps(plan, ensure_ascii=False))
                break

        return "\n\n".join(logs)

    def _state(self) -> str:
        self.browser._ensure()
        dom = self._dom_summary()
        page = self.browser.read_page()
        return f"DOM:\n{dom}\n\nPAGE:\n{page[:12000]}"

    def _dom_summary(self) -> str:
        try:
            return self.browser.page.evaluate("""
                () => {
                  const items = [];
                  for (const el of Array.from(document.querySelectorAll('button,a,input,textarea,select,[role=button],[role=link]')).slice(0,150)) {
                    const r = el.getBoundingClientRect();
                    const visible = r.width > 0 && r.height > 0;
                    if (!visible) continue;
                    items.push({
                      tag: el.tagName,
                      role: el.getAttribute('role') || '',
                      text: (el.innerText || el.value || el.placeholder || el.name || el.ariaLabel || '').trim().slice(0,120),
                      type: el.getAttribute('type') || '',
                      name: el.getAttribute('name') || '',
                      placeholder: el.getAttribute('placeholder') || ''
                    });
                  }
                  return JSON.stringify(items, null, 2);
                }
            """)
        except Exception as e:
            return f"DOM nicht lesbar: {e}"

    def _plan(self, task: str, state: str, logs: list) -> dict:
        prompt = f"""
Du steuerst einen echten Browser. Wähle exakt den nächsten sicheren Schritt.

Aufgabe:
{task}

Bisherige Schritte:
{chr(10).join(logs[-6:])}

Browser-Zustand:
{state[:18000]}

Erlaubte Aktionen:
- google: Google-Suche öffnen. value=Suchtext
- open: URL öffnen. value=URL
- click: sichtbaren Button/Link klicken. value=Text
- fill: Formularfeld ausfüllen. field=Feldname, value=Text
- read: Seite lesen/auswerten
- done: Aufgabe abgeschlossen
- submit/buy/pay/send/order/checkout: finale Aktion, wird blockiert

Regeln:
- Keine Käufe, Zahlungen, E-Mails, Bewerbungen oder finalen Formulare ohne Bestätigung.
- Bei Captcha/Login stoppen oder nur erklären.
- Klicke Cookie-Popups nur, wenn nötig.
- Nutze sichtbare Texte aus DOM.

Antworte NUR JSON:
{{"action":"...", "field":"...", "value":"...", "reason":"..."}}
"""
        raw = self.ollama.complete(prompt, model=INTERNET_RESEARCH_MODEL, system="Du bist Browser-Agent V3. Nur JSON.", temperature=0.01)
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
