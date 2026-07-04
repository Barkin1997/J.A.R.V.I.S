import re

RISK_WORDS = [
    "lösche", "delete", "entferne endgültig", "format", "rm -rf", "del /", "erase",
    "geld senden", "überweisung", "kaufen", "bezahlen", "zahlung", "purchase", "buy",
    "passwort ändern", "password change", "konto löschen", "account löschen",
    "email senden", "e-mail senden", "mail senden", "bewerbung absenden", "absenden",
    "kündigen", "vertrag abschließen", "bestellen", "submit", "send"
]

DANGEROUS_TERMINAL = [
    "rm -rf", "format ", "shutdown", "del /s", "del /q", "rmdir /s",
    "diskpart", "bcdedit", "reg delete", "cipher /w", "takeown",
    "remove-item -recurse", "remove-item -force", ":(){ :|:& };:"
]

def normalized(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip()).lower()

def is_confirmed(text: str) -> bool:
    return normalized(text).startswith("bestätige ")

def strip_confirmation(text: str) -> str:
    if is_confirmed(text):
        return re.sub(r"^\s*bestätige\s+", "", text, flags=re.I).strip()
    return text

def risky_user_action(text: str) -> bool:
    t = normalized(text)
    return any(w.lower() in t for w in RISK_WORDS)

def risky_terminal(command: str) -> bool:
    t = normalized(command)
    return any(w.lower() in t for w in DANGEROUS_TERMINAL)

def confirmation_message(command: str) -> str:
    return (
        "Sicherheitsmodus aktiv. Riskante Aktion blockiert.\n"
        "Zum Ausführen den Befehl mit BESTÄTIGE wiederholen.\n\n"
        f"BESTÄTIGE {command}"
    )
