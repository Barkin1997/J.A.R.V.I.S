import base64
import os
import re
import webbrowser
from pathlib import Path

from config import ASSISTANT_NAME, OLLAMA_TEXT_MODEL, OLLAMA_CODE_MODEL, OLLAMA_VISION_MODEL, OLLAMA_NUM_CTX
from ollama_client import OllamaClient
from skills.browser import BrowserSkill
from skills.coder import CoderSkill
from skills.documents import DocumentSkill
from skills.memory import Memory
from skills.pc import PCSkill
from skills.safety import is_confirmed, strip_confirmation, risky_user_action, confirmation_message
from skills.screen import ScreenSkill
from skills.terminal import TerminalSkill
from plugin_manager import PluginManager
try:
    from local_codex_agent import LocalCodexAgent
except Exception:
    LocalCodexAgent = None

from config import REQUIRE_WAKE_WORD, WAKE_WORD
from skills.comfyui_skill import ComfyUISkill
from skills.browser_agent_v2 import BrowserAgentV2
from skills.repo_agent import RepoAgent
from skills.rag_memory import RAGMemory
from skills.image_ai import ImageAISkill
from skills.video_ai import VideoAISkill
from skills.task_manager import TaskManager
from skills.autopilot import Autopilot
from skills.model_manager import ModelManager
from skills.autopilot_loop import AutopilotLoop
from skills.project_rollback import ProjectRollback
from skills.windows_app_agent_v2 import WindowsAppAgentV2
from skills.sandbox_runner import SandboxRunner
from skills.toolchain_checker import ToolchainChecker
from skills.status_center import StatusCenter
from skills.hybrid_rag import HybridRAG
from skills.source_archive import SourceArchive
from skills.refactor_agent import RefactorAgent
from skills.test_generator import TestGenerator
from skills.project_memory import ProjectMemory
from skills.browser_agent_v3 import BrowserAgentV3
from skills.internet_research import InternetResearch
from skills.multi_agent import MultiAgent
from skills.aider_agent import AiderAgent
from skills.cleanup import JarvisCleanup
from skills.service_watcher import ServiceWatcher
from skills.model_router import ModelRouter
from skills.reliability_guard import ReliabilityGuard
from skills.auto_repair import AutoRepair


class JarvisBrain:
    def __init__(self):
        self.ollama = OllamaClient()
        self.memory = Memory()
        self.browser = BrowserSkill()
        self.pc = PCSkill()
        self.terminal = TerminalSkill()
        self.screen = ScreenSkill(self.ollama)
        self.documents = DocumentSkill()
        self.coder = CoderSkill(self.ollama)
        self.image_ai = ImageAISkill()
        self.video_ai = VideoAISkill()
        self.rag = RAGMemory()
        self.repo_agent = RepoAgent(self.ollama)
        self.browser_agent_v2 = BrowserAgentV2(self.browser, self.ollama)
        self.comfyui = ComfyUISkill()
        self.plugins = PluginManager()
        self.local_codex = LocalCodexAgent(self.ollama) if LocalCodexAgent else None
        self.aider_agent = AiderAgent()
        self.multi_agent = MultiAgent(self.ollama, self.coder, self.terminal)
        self.source_archive = SourceArchive()
        self.internet = InternetResearch(self.browser, self.ollama, self.rag, self.source_archive)
        self.always_research_code = os.getenv("JARVIS_ALWAYS_RESEARCH_CODE", "1") == "1"
        self.browser_agent_v3 = BrowserAgentV3(self.browser, self.ollama)
        self.project_memory = ProjectMemory()
        self.task_manager = TaskManager()
        self.hybrid_rag = HybridRAG(self.rag)
        self.test_generator = TestGenerator(self.ollama)
        self.refactor_agent = RefactorAgent(self.ollama)
        self.status_center = StatusCenter()
        self.cleanup = JarvisCleanup()
        self.service_watcher = ServiceWatcher()
        self.model_router = ModelRouter()
        self.reliability_guard = ReliabilityGuard()
        self.auto_repair = AutoRepair()
        self.toolchain_checker = ToolchainChecker()
        self.autopilot = Autopilot(self.ollama, self.coder, self.repo_agent, self.test_generator, self.refactor_agent, self.task_manager, self.project_memory)
        self.sandbox_runner = SandboxRunner()
        self.model_manager = ModelManager()
        self.windows_app_agent_v2 = WindowsAppAgentV2(self.ollama)
        self.project_rollback = ProjectRollback()
        self.autopilot_loop = AutopilotLoop(self.ollama, self.autopilot, self.repo_agent, self.test_generator, self.refactor_agent, self.project_rollback, self.project_memory)


    def has_wake_word(self, text: str) -> bool:
        raw = (text or "").strip().lower()
        raw = re.sub(r"^\s*bestätige\s+", "", raw, flags=re.I).strip()
        return bool(re.match(rf"^(hey\s+)?{re.escape(WAKE_WORD)}(\b|[:,])", raw, flags=re.I))

    def wake_word_required_message(self) -> str:
        return f"Befehl ignoriert. Starte Befehle mit: {WAKE_WORD.capitalize()}, ..."

    def normalize(self, text: str) -> str:
        text = (text or "").strip()
        text = strip_confirmation(text)
        return re.sub(r"^\s*(hey\s+)?jarvis[:,]?\s*", "", text, flags=re.I).strip()

    def intent_text(self, text: str) -> str:
        text = (text or "").lower()
        text = (
            text.replace("ä", "ae")
            .replace("ö", "oe")
            .replace("ü", "ue")
            .replace("ß", "ss")
            .replace("Ã¤", "ae")
            .replace("Ã¶", "oe")
            .replace("Ã¼", "ue")
            .replace("ÃŸ", "ss")
        )
        return re.sub(r"\s+", " ", text).strip()

    def has_any(self, text: str, terms) -> bool:
        return any(term in text for term in terms)

    def is_new_browser_game_request(self, command: str) -> bool:
        low = self.intent_text(command)
        action = self.has_any(low, [
            "erstelle", "erstell", "mach", "mache", "baue", "bau",
            "programmiere", "programmier", "entwickle", "erzeuge",
            "generiere", "schreib", "schreibe",
        ])
        game = self.has_any(low, [
            "spiel", "spiele", "game", "browsergame", "browser game",
            "arcade", "runner", "jump and run", "jump'n'run",
        ])
        browser = self.has_any(low, [
            "browser", "browsergame", "browser game", "web", "html",
            "canvas", "javascript", "offline", "arcade", "runner",
        ])
        large = self.has_any(low, [
            "gross", "grosse", "grosses", "groß", "große", "großes",
            "3d", "unity", "unreal", "godot", "multiplayer", "open world",
            "engine", "steam", "großes projekt", "grosses projekt",
        ])
        return action and game and browser and not large

    def is_new_website_request(self, command: str) -> bool:
        low = self.intent_text(command)
        action = self.has_any(low, [
            "erstelle", "erstell", "mach", "mache", "baue", "bau",
            "entwickle", "erzeuge", "generiere", "schreib", "schreibe",
        ])
        web = self.has_any(low, [
            "webseite", "website", "homepage", "home page", "homge",
            "landing page", "html seite", "browser seite",
        ])
        return action and web

    def is_code_edit_request(self, command: str) -> bool:
        low = (command or "").strip().lower()
        if low.startswith((
            "repo ändere",
            "repo aendere",
            "ändere repo",
            "aendere repo",
            "projekt ändern",
            "projekt aendern",
            "codex ",
            "codey ",
            "codex:",
            "codey:",
        )):
            return True
        code_terms = [
            "code", "coding", "codier", "programmier", "skript", "script",
            "datei", "projekt", "repo", "app", "webseite", "website",
            "homepage", "html", "css", "javascript", "python", "react",
        ]
        edit_terms = [
            "ändere", "aendere", "bearbeite", "verbesser", "fix", "reparier",
            "lösche", "loesche", "entferne", "ersetze", "füge", "fuege",
            "einfügen", "einfuegen", "einbauen", "mach", "baue", "erstelle",
        ]
        build_terms = [
            "baue", "bau ", "mach ", "erstelle", "erstell", "implementier",
            "fuege", "f\u00fcge", "einbauen", "einfuegen", "einf\u00fcgen",
            "testfunktion", "funktion ein", "feature ein",
        ]
        if any(term in low for term in build_terms):
            return True
        return any(term in low for term in code_terms) and any(term in low for term in edit_terms)

    def is_own_game_test_code_request(self, command: str) -> bool:
        low = self.intent_text(command)
        own_context = self.has_any(low, [
            "mein spiel", "mein eigenes spiel", "mein online spiel", "mein online-game",
            "mein game", "mein eigenes game", "unser spiel", "unser game",
            "eigene spiel", "eigenes spiel", "eigenes online spiel",
            "mein projekt", "unser projekt", "mein ordner", "testserver",
            "dev", "debug", "admin", "testmodus", "entwicklermodus",
        ])
        game_context = self.has_any(low, [
            "spiel", "game", "online spiel", "online-game", "server", "client",
        ])
        test_feature = self.has_any(low, [
            "cheat", "cheats", "aimbot", "aim assist", "wallhack", "esp",
            "debug overlay", "debug-overlay", "admin menue", "admin menu",
            "test bot", "testbot", "bot test", "anti-cheat", "anticheat",
            "exploit test", "exploit-test",
        ])
        action = self.has_any(low, [
            "baue", "bau", "erstelle", "erstell", "mach", "mache",
            "implementier", "programmiere", "entwickle", "fuege", "fueg",
            "einbauen", "einfuegen",
        ])
        return own_context and game_context and test_feature and action

    def needs_internet_context(self, task: str, force: bool = False) -> bool:
        if force:
            return True
        low = self.intent_text(task)
        return self.has_any(low, [
            "internet", "online", "recherche", "recherchiere", "google",
            "doku", "docs", "dokumentation", "api", "library", "bibliothek",
            "package", "paket", "npm", "pip", "framework", "version",
            "aktuell", "neueste", "latest", "github", "openai", "ollama", "aider",
        ])

    def with_optional_internet_context(self, task: str, force: bool = False) -> str:
        task = str(task or "").strip()
        if not self.needs_internet_context(task, force=force):
            return task
        pages = int(os.getenv("JARVIS_CODE_RESEARCH_PAGES", "10"))
        pages = max(3, min(pages, 15))
        try:
            research = self.internet.research(task, pages=pages)
        except Exception as e:
            research = f"Internet-Recherche fehlgeschlagen: {e}"
        clean_research = str(research or "").strip()
        if not clean_research:
            clean_research = "Keine verwertbare Internet-Recherche erhalten."
        return (
            f"{task}\n\n"
            "AKTUELLER INTERNET-/DOKU-KONTEXT FUER DIE AUFGABE:\n"
            f"Rechercheumfang: bis zu {pages} Seiten.\n"
            f"{clean_research[:7000]}\n\n"
            "Nutze diesen Kontext nur, wenn er zur Aufgabe passt. Erfinde keine Quellen."
        )

    def with_code_internet_context(self, task: str) -> str:
        return self.with_optional_internet_context(task, force=self.always_research_code)

    def handle(self, raw: str) -> str:
        raw = (raw or "").strip()
        confirmed = is_confirmed(raw)
        command = self.normalize(raw)
        if not command:
            return "Befehl fehlt."
        if risky_user_action(command) and not confirmed and not self.is_code_edit_request(command):
            return confirmation_message(command)

        lower = command.lower()

        if lower in (
            "pruefe dich",
            "prüfe dich",
            "teste dich",
            "status komplett",
            "dashboard",
            "jarvis zentrale",
            "zentrale",
            "autotest",
            "was kannst du",
            "was kannst du alles",
            "kannst du codieren",
            "kannst du code ändern",
            "kannst du code aendern",
            "kannst du dateien ändern",
            "kannst du dateien aendern",
            "kannst du pc steuern",
            "pc steuerung status",
        ) or lower.startswith((
            "pruefe dich",
            "prÃ¼fe dich",
            "teste dich",
            "status komplett",
            "autotest",
            "was kannst du",
            "kannst du codieren",
            "kannst du pc steuern",
            "kannst du code",
            "kannst du dateien",
            "jarvis pruefe dich",
            "jarvis prüfe dich",
            "jarvis teste dich",
            "jarvis was kannst du",
            "jarvis kannst du codieren",
            "jarvis kannst du pc steuern",
        )):
            status = self.status_center.check()
            if any(term in lower for term in ("pruefe dich", "prÃ¼fe dich", "prÃƒÂ¼fe dich", "teste dich", "autotest")):
                return status + "\n\n" + self.reliability_guard.check()
            return status

        if lower.startswith(("aider", "aider modus", "aider-mode")):
            return self.aider_agent.run_command(command)

        if lower.startswith(("coding dashboard", "codier dashboard", "code dashboard", "öffne coding dashboard", "oeffne coding dashboard")):
            url = "http://127.0.0.1:8765/coding_dashboard.html"
            try:
                webbrowser.open(url, new=2)
            except Exception:
                pass
            return f"Coding-Dashboard geoeffnet: {url}"

        if lower.startswith(("service waechter", "service wächter", "dienste pruefen", "dienste prüfen", "dienste status", "services status")):
            return self.service_watcher.check()

        if lower.startswith(("dienste starten", "services starten", "service waechter starten", "service wächter starten", "starte dienste")):
            return self.service_watcher.ensure_all()

        if lower.startswith(("modell router", "modell-router", "welches modell", "model router")):
            return self.model_router.status()

        if lower.startswith((
            "zuverlaessigkeit", "zuverlässigkeit", "stabilitaet", "stabilität",
            "jarvis haerten", "jarvis härten", "haerte jarvis", "härte jarvis",
            "fehler schutz", "fehlerschutz", "reliability", "reliability check",
            "stabil pruefen", "stabil prüfen", "zuverlaessigkeit pruefen", "zuverlässigkeit prüfen",
        )):
            return self.reliability_guard.check()

        if lower.startswith((
            "auto reparatur", "autoreparatur", "automatisch reparieren",
            "repariere dich", "jarvis repariere dich", "selbst reparatur",
            "self repair", "auto repair", "reparatur status",
        )):
            if "status" in lower:
                return self.auto_repair.status()
            return self.auto_repair.run(reason=command, start_services=True)

        if lower.startswith(("fehlerdatenbank", "error datenbank", "error database", "projekt fehler")):
            path = self._after(command, ["fehlerdatenbank", "error datenbank", "error database", "projekt fehler"])
            return self.aider_agent.error_database(path)

        if lower.startswith(("projekt gedächtnis", "projekt gedaechtnis", "projekt memory", "ordner gedächtnis", "ordner gedaechtnis")):
            path = self._after(command, ["projekt gedächtnis", "projekt gedaechtnis", "projekt memory", "ordner gedächtnis", "ordner gedaechtnis"])
            return self.aider_agent.project_memory_status(path, command)

        if lower.startswith(("codex mit internet", "internet codex", "online codex", "recherche codex", "recherchiere und aendere", "recherchiere und ändere")):
            task = self._after(command, [
                "codex mit internet", "internet codex", "online codex", "recherche codex",
                "recherchiere und aendere", "recherchiere und ändere",
            ])
            return self.aider_agent.modify("", self.with_optional_internet_context(task, force=True))

        # Repo-Auftraege kommen aus Drag&Drop-/Chat-Kontext. Sie muessen vor dem
        # lokalen Codex-Direktmodus laufen, sonst loesen Woerter aus altem Kontext
        # wie "ollama", "modell" oder "test" faelschlich Selbsttests aus.
        if lower.startswith(("repo frage", "projekt frage", "frage repo", "frage projekt")):
            rest = self._after(command, ["repo frage", "projekt frage", "frage repo", "frage projekt"])
            if "|" in rest:
                path, question = [x.strip() for x in rest.split("|", 1)]
            else:
                path, question = "", rest
            return self.repo_agent.ask(path, self.with_code_internet_context(question))

        if lower.startswith(("repo analysiere", "analysiere repo", "projekt analysieren")):
            path = self._after(command, ["repo analysiere", "analysiere repo", "projekt analysieren"])
            return self.repo_agent.analyze(path)

        if lower.startswith(("repo ändere", "repo aendere", "repo Ã¤ndere", "ändere repo", "Ã¤ndere repo", "projekt ändern", "projekt aendern", "projekt Ã¤ndern")):
            rest = self._after(command, ["repo ändere", "repo aendere", "repo Ã¤ndere", "ändere repo", "Ã¤ndere repo", "projekt ändern", "projekt aendern", "projekt Ã¤ndern"])
            if "|" in rest:
                path, task = [x.strip() for x in rest.split("|", 1)]
            else:
                path, task = "", rest
            return self.aider_agent.modify(path, self.with_code_internet_context(task))

        if self.is_new_browser_game_request(command):
            return self.coder.create_game(self.with_code_internet_context(command))

        if self.is_new_website_request(command):
            return self.coder.create_website(self.with_code_internet_context(command))

        if self.is_own_game_test_code_request(command):
            task = (
                "Der Nutzer meint sein eigenes/autorisiertes Online-Spiel. "
                "Baue die gewuenschte Cheat-/Debug-/Admin-Testfunktion nur als Dev/Testmodus im eigenen Projekt. "
                "Keine Drittanbieter-Hacks, keine Malware, kein Credentialdiebstahl, keine heimliche Anti-Cheat-Umgehung gegen fremde Systeme.\n\n"
                f"AUFGABE:\n{command}"
            )
            return self.aider_agent.modify("", self.with_code_internet_context(task))

        # Direktmodus: Code-/Datei-Aufgaben automatisch an lokalen Codex-Pro schicken,
        # auch ohne "Jarvis" oder "Codex" davor.
        direct_codex_keywords = (
            "prüfe dich", "pruefe dich", "teste dich", "finde warum", "warum antwortest",
            "repariere", "reparier", "fix", "ändere", "aendere", "verbessere",
            "baue", "füge", "fuege", "implementiere", "suche ", "lese ",
            "öffne datei", "oeffne datei", "app.py", "brain.py", "voice.py",
            "mach nummer", "mache nummer", "nummer ",
            "config.py", "ollama_client.py", "plugin_manager.py", ".env",
            "python", "fehler", "error", "traceback", "modell", "ollama"
        )
        if any(k in lower for k in direct_codex_keywords) and self.is_code_edit_request(command):
            return self.aider_agent.modify("", self.with_code_internet_context(command))

        if self.local_codex and any(k in lower for k in direct_codex_keywords):
            return self.aider_agent.ask("", self.with_code_internet_context(command))



        # Lokaler Codex-Modus mit qwen3-coder-next:latest
        if lower.startswith(("lokaler codex", "local codex", "codex lokal", "codex-modus", "codex modus", "codex ", "code agent", "code-agent")) or lower in ("codex", "code agent"):
            if not self.local_codex:
                return "Lokaler Codex-Modus konnte nicht geladen werden. Prüfe local_codex_agent.py."
            task = re.sub(r"^(lokaler codex|local codex|codex lokal|codex-modus|codex modus|codex|code-agent|code agent)[:,]?\s*", "", command, flags=re.I).strip()
            return self.aider_agent.run_command("aider " + (task or "status"))

        if lower.startswith(("codex ", "codey ", "codex:", "codey:")):
            task = re.sub(r"^(codex|codey)[:,]?\s*", "", command, flags=re.I).strip()
            if not task:
                return "Codex-Modus aktiv. Sag danach direkt, was ich am Projekt ändern soll."
            if any(x in task.lower() for x in ["analysiere", "analysier", "prüfe", "pruefe", "check", "review"]):
                return self.aider_agent.ask("", self.with_code_internet_context(task))
            return self.aider_agent.modify("", self.with_code_internet_context(task))

        if lower in ("codex", "codey", "codex modus", "codey modus"):
            return "Codex-Modus aktiv. Zieh einen Projektordner auf Jarvis und sag danach einfach, was ich am Ordner ändern soll."


        if lower.startswith(("video dashboard", "ki video dashboard", "video fortschritt fenster", "video ladebalken fenster", "oeffne video dashboard", "oeffne ki video dashboard")):
            url = "http://127.0.0.1:8765/video_dashboard.html"
            try:
                webbrowser.open(url, new=2)
            except Exception:
                pass
            return f"Video-Dashboard geoeffnet: {url}"

        if lower.startswith(("ki video status", "video ai status", "video status")):
            return self.video_ai.status()

        if lower.startswith(("ki video fortschritt", "video fortschritt", "ki video ladebalken", "video ladebalken", "render status", "render fortschritt", "render ladebalken", "wie lange rendert", "wie lange dauert das video")):
            target = self._after(command, ["ki video fortschritt", "video fortschritt", "ki video ladebalken", "video ladebalken", "render status", "render fortschritt", "render ladebalken", "wie lange rendert", "wie lange dauert das video"])
            status = self.video_ai.ready_status(target)
            if "ladebalken" in lower or "wie lange" in lower:
                url = "http://127.0.0.1:8765/video_dashboard.html"
                try:
                    webbrowser.open(url, new=2)
                except Exception:
                    pass
                return f"Video-Dashboard geoeffnet: {url}\n\n{status}"
            return status

        if lower.startswith(("ki video fertig?", "video fertig?", "ist video fertig", "ist ki video fertig", "ki video bereit", "video bereit", "render fertig")):
            target = self._after(command, ["ki video fertig?", "video fertig?", "ist video fertig", "ist ki video fertig", "ki video bereit", "video bereit", "render fertig"])
            return self.video_ai.ready_status(target)

        if lower.startswith(("ki video studio", "video studio", "video ai studio")):
            return self.video_ai.studio()

        if lower.startswith(("öffne ki video", "oeffne ki video", "öffne video ki", "video ki öffnen", "video ai öffnen")):
            return self.video_ai.open()

        if lower.startswith(("ki video hilfe", "video ki hilfe", "video ai hilfe")):
            return self.video_ai.install_hint()

        if lower.startswith(("ki video fertigstellen", "video fertigstellen", "ki video 4k", "video 4k", "mache video 4k")):
            target = self._after(command, ["ki video fertigstellen", "video fertigstellen", "ki video 4k", "video 4k", "mache video 4k"])
            return self.video_ai.finalize_video(target)

        video_prefixes = [
            "erstelle ki video",
            "ki video erstellen",
            "ki video generieren",
            "ai video erstellen",
            "video generieren",
            "erstelle video",
            "mach video",
            "mache video",
            "mach ein video",
            "mache ein video",
            "mach tiktok video",
            "mache tiktok video",
            "tiktok video",
            "tanzvideo",
            "sprechender mensch",
            "sprechenden menschen",
            "bild zu video",
            "foto zu video",
            "image to video",
        ]
        if lower.startswith(tuple(video_prefixes)) or re.match(r"^(mach|mache|erstelle).*(tiktok|video|tanzvideo|sprechend|bild zu video|foto zu video)", lower):
            prompt = self._after(command, video_prefixes).strip() or command
            return self.video_ai.create_video_project(prompt)


        if lower.startswith(("fenster liste", "windows liste", "app fenster")):
            return self.windows_app_agent_v2.list_windows()

        if lower.startswith(("fenster aktivieren", "app aktivieren")):
            title = self._after(command, ["fenster aktivieren", "app aktivieren"])
            return self.windows_app_agent_v2.focus_window(title)

        if lower.startswith(("app öffnen", "app oeffnen", "programm öffnen", "programm oeffnen")):
            app_name = self._after(command, ["app öffnen", "app oeffnen", "programm öffnen", "programm oeffnen"])
            return self.windows_app_agent_v2.open_app(app_name)

        if lower.startswith(("ocr bildschirm", "lies bildschirm ocr", "screen ocr")):
            return self.windows_app_agent_v2.read_screen_ocr()

        if lower.startswith(("klick text", "ocr klick")):
            text = self._after(command, ["klick text", "ocr klick"])
            return self.windows_app_agent_v2.click_text(text)

        if lower.startswith(("schreibe in app", "app text schreiben")):
            text = self._after(command, ["schreibe in app", "app text schreiben"])
            return self.windows_app_agent_v2.type_text(text)

        if lower.startswith(("hotkey", "tastenkombi")):
            keys = self._after(command, ["hotkey", "tastenkombi"])
            return self.windows_app_agent_v2.hotkey(keys)

        if lower.startswith(("projekt backup", "backup projekt")):
            rest = self._after(command, ["projekt backup", "backup projekt"])
            if "|" in rest:
                path, label = [x.strip() for x in rest.split("|", 1)]
            else:
                path, label = rest, "manual"
            return self.project_rollback.backup(path, label)

        if lower.startswith(("projekt rollback", "rollback projekt", "projekt wiederherstellen")):
            path = self._after(command, ["projekt rollback", "rollback projekt", "projekt wiederherstellen"])
            return self.project_rollback.restore_latest(path)

        if lower.startswith(("git rollback", "git zurück", "git zurueck")):
            path = self._after(command, ["git rollback", "git zurück", "git zurueck"])
            return self.project_rollback.git_rollback(path)

        if lower.startswith(("autopilot loop", "autopilot bis fertig", "baue bis fertig")):
            goal = self._after(command, ["autopilot loop", "autopilot bis fertig", "baue bis fertig"])
            return self.autopilot_loop.run_until_done(goal)


        if lower.startswith(("sandbox projekt", "sandbox project")):
            rest = self._after(command, ["sandbox projekt", "sandbox project"])
            if "|" in rest:
                path, cmd = [x.strip() for x in rest.split("|", 1)]
            else:
                path, cmd = rest, ""
            return self.sandbox_runner.run_project(path, cmd)

        if lower.startswith(("sandbox befehl", "sandbox command")):
            cmd = self._after(command, ["sandbox befehl", "sandbox command"])
            return self.sandbox_runner.run_command(cmd)

        if lower.startswith(("modell profile", "modell profile", "modell profil", "model profile")):
            name = self._after(command, ["modell profile", "modell profile", "modell profil", "model profile"])
            return self.model_manager.set_profile(name)

        if lower.startswith(("modell liste", "modelle liste", "ollama liste", "model list")):
            return self.model_manager.ollama_list()

        if lower.startswith(("modell manager", "model manager")):
            return self.model_manager.list_profiles()

        if lower.startswith(("modell laden", "modelle laden", "pull modelle")):
            name = self._after(command, ["modell laden", "modelle laden", "pull modelle"])
            return self.model_manager.pull_profile_models(name)


        if lower.startswith(("tests erstellen", "test generator", "erstelle tests")):
            rest = self._after(command, ["tests erstellen", "test generator", "erstelle tests"])
            if "|" in rest:
                path, goal = [x.strip() for x in rest.split("|", 1)]
            else:
                path, goal = rest, ""
            return self.test_generator.generate_tests(path, goal)

        if lower.startswith(("refactor", "refactore", "refaktorisiere")):
            rest = self._after(command, ["refactor", "refactore", "refaktorisiere"])
            if "|" in rest:
                path, instruction = [x.strip() for x in rest.split("|", 1)]
            else:
                path, instruction = rest, "Architektur verbessern und Code sauberer machen"
            return self.refactor_agent.refactor(path, instruction)

        if lower.startswith(("hybrid rag frage", "hybrid frage")):
            q = self._after(command, ["hybrid rag frage", "hybrid frage"])
            return self.hybrid_rag.ask(q, self.ollama, OLLAMA_TEXT_MODEL)

        if lower.startswith(("hybrid rag suche", "hybrid suche")):
            q = self._after(command, ["hybrid rag suche", "hybrid suche"])
            return self.hybrid_rag.search(q)

        if lower.startswith(("quellen", "quellenarchiv")):
            q = self._after(command, ["quellen", "quellenarchiv"])
            return self.source_archive.list(q)

        if lower.startswith(("quelle lesen", "lies quelle")):
            raw_id = self._after(command, ["quelle lesen", "lies quelle"]).strip().lstrip("#")
            return self.source_archive.read(int(raw_id)) if raw_id.isdigit() else "Quellen-ID fehlt."

        if lower.startswith(("ultra status", "system status", "internet status", "status komplett")):
            return self.status_center.check()

        if lower.startswith(("jarvis aufraeumen", "jarvis aufräumen", "aufraeumen", "aufräumen", "system aufraeumen", "system aufräumen")):
            return self.cleanup.clean(command)

        if lower.startswith(("toolchain check", "compiler check", "devtools check")):
            return self.toolchain_checker.check()

        if lower.startswith(("autopilot", "projekt autopilot", "baue komplett")):
            goal = self._after(command, ["autopilot", "projekt autopilot", "baue komplett"])
            return self.autopilot.run(goal)


        if lower.startswith(("multi agent", "multi-agent", "agenten modus", "agentenmodus", "ultra agent")):
            task = self._after(command, ["multi agent", "multi-agent", "agenten modus", "agentenmodus", "ultra agent"])
            return self.multi_agent.execute(task)

        if lower.startswith(("internet recherche", "internetrecherche", "recherchiere im internet", "web recherche", "online recherche")):
            q = self._after(command, ["internet recherche", "internetrecherche", "recherchiere im internet", "web recherche", "online recherche"])
            return self.internet.research(q, pages=7)

        if lower.startswith(("merk dir diese webseite", "webseite merken", "speichere webseite")):
            return self.internet.remember_current_page()

        if lower.startswith(("browser v3", "browser-agent v3", "browser agent v3", "web agent v3")):
            task = self._after(command, ["browser v3", "browser-agent v3", "browser agent v3", "web agent v3"])
            return self.browser_agent_v3.run_task(task)

        if lower.startswith(("projekt speichern", "speichere projekt")):
            rest = self._after(command, ["projekt speichern", "speichere projekt"])
            parts = [x.strip() for x in rest.split("|")]
            while len(parts) < 5:
                parts.append("")
            return self.project_memory.save(parts[0], parts[1], parts[2], parts[3], parts[4])

        if lower.startswith(("projekte", "projekt liste")):
            return self.project_memory.list()

        if lower.startswith(("projekt info", "zeige projekt")):
            name = self._after(command, ["projekt info", "zeige projekt"])
            return self.project_memory.get(name)

        if lower.startswith(("aufgabe erstellen", "task erstellen", "neue aufgabe")):
            title = self._after(command, ["aufgabe erstellen", "task erstellen", "neue aufgabe"])
            return self.task_manager.add(title)

        if lower.startswith(("aufgaben", "task liste")):
            return self.task_manager.list()

        if lower.startswith(("nächste aufgabe", "naechste aufgabe", "next task")):
            return self.task_manager.next()

        if lower.startswith(("aufgabe fertig", "task fertig")):
            raw_id = self._after(command, ["aufgabe fertig", "task fertig"]).strip().lstrip("#")
            return self.task_manager.done(int(raw_id)) if raw_id.isdigit() else "Aufgaben-ID fehlt."

        if lower.startswith(("plugins", "plugin liste", "plugins liste")):
            return self.plugins.list_plugins()

        plugin_result = self.plugins.handle(command, {"ollama": self.ollama, "project_dir": str(__import__("config").PROJECT_DIR)})
        if plugin_result:
            return plugin_result

        if lower.startswith(("rag index", "indexiere ordner", "indexiere dateien", "dateigedächtnis index")):
            path = self._after(command, ["rag index", "indexiere ordner", "indexiere dateien", "dateigedächtnis index"])
            return self.rag.index_path(path)

        if lower.startswith(("rag frage", "frage dateigedächtnis", "suche im dateigedächtnis")):
            q = self._after(command, ["rag frage", "frage dateigedächtnis", "suche im dateigedächtnis"])
            return self.rag.ask(q, self.ollama, OLLAMA_TEXT_MODEL)

        if lower.startswith(("rag suche", "dateigedächtnis suche")):
            q = self._after(command, ["rag suche", "dateigedächtnis suche"])
            return self.rag.search(q)

        if lower.startswith(("repo frage", "projekt frage", "frage repo", "frage projekt")):
            rest = self._after(command, ["repo frage", "projekt frage", "frage repo", "frage projekt"])
            if "|" in rest:
                path, question = [x.strip() for x in rest.split("|", 1)]
            else:
                path, question = "", rest
            return self.repo_agent.ask(path, self.with_code_internet_context(question))

        if lower.startswith(("repo analysiere", "analysiere repo", "projekt analysieren")):
            path = self._after(command, ["repo analysiere", "analysiere repo", "projekt analysieren"])
            return self.repo_agent.analyze(path)

        if lower.startswith(("repo ändere", "repo aendere", "ändere repo", "projekt ändern", "projekt aendern")):
            rest = self._after(command, ["repo ändere", "repo aendere", "ändere repo", "projekt ändern", "projekt aendern"])
            if "|" in rest:
                path, task = [x.strip() for x in rest.split("|", 1)]
            else:
                path, task = "", rest
            return self.aider_agent.modify(path, self.with_code_internet_context(task))

        if lower.startswith(("browser agent", "browser-agent", "web agent v2", "browser v2")):
            task = self._after(command, ["browser agent", "browser-agent", "web agent v2", "browser v2"])
            return self.browser_agent_v3.run_task(task)

        if lower.startswith(("comfyui status", "comfy status")):
            return self.comfyui.status()

        if lower.startswith(("öffne comfyui", "starte comfyui", "comfyui öffnen")):
            return self.comfyui.open()

        if lower.startswith(("comfyui hilfe", "comfy hilfe")):
            return self.comfyui.start_hint()

        if lower in ["status", "systemstatus", "ollama status"]:
            return self.status()

        if lower.startswith(("merk dir", "speichere", "erinnere dich")):
            content = re.sub(r"^(merk dir|speichere|erinnere dich)[:\s]+", "", command, flags=re.I).strip()
            return self.memory.add(content)

        if lower.startswith(("was weißt du", "erinnerung", "gedächtnis")):
            q = re.sub(r"^(was weißt du über|was weißt du|erinnerung|gedächtnis)[:\s]*", "", command, flags=re.I).strip()
            return self.memory.format_results(q)

        if "suche auf google" in lower or lower.startswith("google ") or "google suche" in lower or lower.startswith("suche "):
            query = self._after(command, ["suche auf google", "google suche", "google", "suche"])
            self.browser.google(query)
            page = self.browser.read_page()
            if len(query) > 3:
                summary = self.ollama.complete("Fasse diese Suchergebnisse kurz zusammen:\n\n" + page[:9000], system="Du fasst Webinhalte kurz zusammen.")
                return f"Google geöffnet.\n\n{summary}"
            return "Google geöffnet."

        if lower.startswith(("öffne google", "starte google")):
            return self.browser.google("")

        if lower.startswith(("öffne webseite", "öffne website", "gehe zu", "öffne seite")):
            url = self._after(command, ["öffne webseite", "öffne website", "öffne seite", "gehe zu"])
            return self.browser.goto(url)

        if lower.startswith(("lies die webseite", "webseite lesen", "seite lesen")):
            page = self.browser.read_page()
            return self.ollama.complete("Fasse diese Webseite auf Deutsch zusammen und nenne wichtige Aktionen:\n\n" + page[:10000], system="Du analysierst Webseiten präzise.")

        if lower.startswith(("klick ", "klicke ")):
            return self.browser.click_text(re.sub(r"^(klick|klicke)\s+", "", command, flags=re.I))

        if lower.startswith(("fülle ", "formular ")):
            m = re.search(r"(?:fülle|formular)\s+(.+?)\s+(?:mit|=)\s+(.+)", command, re.I)
            return "Format: Jarvis, fülle Feldname mit Text" if not m else self.browser.fill_field(m.group(1), m.group(2))

        if "neuer tab" in lower or "neuen tab" in lower:
            return self.browser.new_tab()

        if "tab schließen" in lower or "schließe tab" in lower:
            return self.browser.close_tab()

        if (
            ("bildschirm" in lower or "screen" in lower)
            and any(x in lower for x in ["lern", "lerne", "merken", "merk dir", "speichere", "erinnere"])
        ):
            result = self.screen.analyze(command)
            clean_result = re.sub(r"\n\nScreenshot:.*$", "", result, flags=re.S).strip()
            saved = self.memory.add(
                "Vom Bildschirm gelernt:\n"
                f"Auftrag: {command}\n"
                f"Analyse: {clean_result[:3500]}"
            )
            return f"{result}\n\nGedaechtnis: {saved}"

        if "bildschirm" in lower or "screen" in lower:
            return self.screen.analyze(command)

        if lower.startswith(("öffne programm", "starte programm")):
            return self.pc.open_program(self._after(command, ["öffne programm", "starte programm"]))

        if lower.startswith(("öffne ", "starte ")):
            name = self._after(command, ["öffne", "starte"])
            if "." not in name and "http" not in name:
                return self.pc.open_program(name)

        if lower.startswith(("suche datei", "datei suchen", "finde datei")):
            return self.pc.search_files(self._after(command, ["suche datei", "datei suchen", "finde datei"]))

        if lower.startswith(("erstelle ordner", "ordner erstellen", "mach ordner")):
            return self.pc.create_folder(self._after(command, ["erstelle ordner", "ordner erstellen", "mach ordner"]))

        if lower.startswith(("screenshot", "mach screenshot", "speichere screenshot")):
            return self.pc.screenshot()

        if "fenster wechseln" in lower or "wechsle fenster" in lower:
            return self.pc.switch_window()

        if lower.startswith(("tippe ", "schreibe ")):
            return self.pc.type_text(self._after(command, ["tippe", "schreibe"]))

        if lower.startswith(("drücke ", "taste ")):
            return self.pc.press(self._after(command, ["drücke", "taste"]))

        if lower.startswith(("terminal", "führe terminal aus", "befehl ausführen", "cmd ")):
            cmd = self._after(command, ["führe terminal aus:", "führe terminal aus", "befehl ausführen:", "befehl ausführen", "terminal:", "terminal", "cmd"])
            return self.terminal.run(cmd, confirmed=confirmed)

        if lower.startswith(("ki bild stile", "bild stile", "image styles", "bild styles")):
            return self.image_ai.styles()

        if lower.startswith(("ki bild studio", "bild studio", "image studio", "ki-bild studio")):
            return self.image_ai.studio()

        if lower.startswith(("ki bild galerie", "bild galerie", "image galerie", "bild ordner")):
            return self.image_ai.gallery()

        if lower.startswith(("ki bild aussortieren", "bild aussortieren", "schlechte bilder aussortieren")):
            return self.image_ai.sort_gallery()

        if lower.startswith(("ki bild upscale", "bild upscale", "bild hochskalieren", "foto hochskalieren", "ki bild 4k")):
            path = self._after(command, ["ki bild upscale", "bild upscale", "bild hochskalieren", "foto hochskalieren", "ki bild 4k"])
            return self.image_ai.upscale_image(path)

        if lower.startswith(("ki bild referenz", "bild mit referenz", "image to image", "img2img", "bild zu bild")):
            rest = self._after(command, ["ki bild referenz", "bild mit referenz", "image to image", "img2img", "bild zu bild"])
            if "|" in rest:
                ref, prompt = [x.strip() for x in rest.split("|", 1)]
            else:
                ref, prompt = "", rest
            return self.image_ai.create_image(prompt, reference_path=ref)

        if any(x in lower for x in ["ki bild", "bild erstellen", "bild generieren", "ai bild", "image erstellen", "foto generieren"]):
            if "status" in lower:
                return self.image_ai.status()
            prompt = self._after(command, [
                "erstelle ki bild", "ki bild erstellen", "ki bild", "bild erstellen",
                "bild generieren", "ai bild", "image erstellen", "foto generieren",
                "erstelle ein bild", "mach ein bild"
            ])
            return self.image_ai.create_image(prompt)

        if lower.startswith(("analysiere bild", "bild analysieren", "analysiere foto", "foto analysieren", "lies bild", "lies foto")):
            path = self._after(command, ["analysiere bild", "bild analysieren", "analysiere foto", "foto analysieren", "lies bild", "lies foto"])
            return self.analyze_image_file(path)

        if self.is_new_website_request(command) or "erstelle eine webseite" in lower or "webseite erstellen" in lower or "mach eine webseite" in lower or "mach eine seite" in lower or "baue eine seite" in lower or "erstelle eine seite" in lower or "homepage" in lower or "home page" in lower or "homge" in lower:
            return self.coder.create_website(self.with_code_internet_context(command))

        if self.is_new_browser_game_request(command) or "erstelle ein spiel" in lower or "spiel erstellen" in lower or "mach ein spiel" in lower or "game erstellen" in lower:
            return self.coder.create_game(self.with_code_internet_context(command))

        if any(x in lower for x in ["mach", "erstelle", "baue", "entwickle", "erzeuge", "schreib", "schreibe"]) and any(x in lower for x in ["app", "tool", "programm", "projekt", "software", "bot", "ki", "assistant", "assistent", "datei", "seite"]):
            return self.coder.create_code_project(command)

        if lower.startswith(("erstelle projekt", "mach projekt", "baue projekt", "code projekt", "coding projekt")):
            return self.coder.create_code_project(command)

        if lower.startswith(("debug", "fehler analysieren", "analysiere fehler")):
            return self.coder.analyze_error(self._after(command, ["debug", "fehler analysieren", "analysiere fehler"]))

        if any(x in lower for x in [
            "programmiere", "programmier", "codier", "codiere", "codieren", "codiern", "coderinb", "coderien", "coderiern",
            "code", "coding", "skript", "script",
            "c++", "cpp", "c plus plus", "cc plus plus", "c#", "csharp",
            "python", "java", "javascript", "typescript", "html", "css",
            "react", "node", "go", "golang", "rust", "php", "sql",
            "powershell", "batch", ".bat"
        ]):
            if any(x in lower for x in ["erstelle", "mach", "baue", "projekt", "app", "programm", "datei", "webseite", "website", "spiel", "tool", "script", "skript"]):
                return self.coder.create_code_project(command)
            return self.coder.code_answer(command)

        if lower.startswith(("lies pdf", "pdf lesen")):
            text = self.documents.read_pdf(self._after(command, ["lies pdf", "pdf lesen"]))
            return self._summarize_doc(text)

        if lower.startswith(("lies word", "word lesen", "docx lesen")):
            text = self.documents.read_docx(self._after(command, ["lies word", "word lesen", "docx lesen"]))
            return self._summarize_doc(text)

        if lower.startswith(("erstelle pdf", "pdf erstellen")):
            return self.documents.create_pdf("jarvis_dokument.pdf", self._after(command, ["erstelle pdf", "pdf erstellen"]))

        if lower.startswith(("entwirf email", "email entwerfen", "e-mail entwerfen")):
            request = self._after(command, ["entwirf email", "email entwerfen", "e-mail entwerfen"])
            body = self.ollama.complete("Erstelle einen seriösen deutschen E-Mail-Entwurf. Nicht senden.\n\n" + request, system="Du schreibst klare E-Mails.")
            return self.documents.draft_email("Jarvis E-Mail Entwurf", body)

        return self.default_chat(command)

    def status(self) -> str:
        models = self.ollama.list_models()
        if not models:
            return "Ollama nicht erreichbar oder keine Modelle geladen. Starte Ollama und pull_models_rtx5080.bat."
        return (
            "Ollama läuft.\n"
            f"Textmodell: {OLLAMA_TEXT_MODEL}\n"
            f"Codemodell: {OLLAMA_CODE_MODEL}\n"
            f"Visionmodell: {OLLAMA_VISION_MODEL}\n"
            f"Context: {OLLAMA_NUM_CTX}\n"
            f"Internet: Browser/Playwright aktiv, Recherche-Agent vorhanden\n"
            f"RAG: nomic-embed-text-v2-moe\n\n"
            "Geladene Modelle:\n" + "\n".join(f"- {m}" for m in models)
        )

    def default_chat(self, command: str) -> str:
        mem = self.memory.format_results(command)
        return self.ollama.complete(
            f"Relevantes Gedächtnis:\n{mem}\n\nNutzerbefehl:\n{command}",
            system=f"Du bist {ASSISTANT_NAME}, ein lokaler Chatbot und PC-Assistent. Antworte wie ein hilfreicher ChatGPT-ähnlicher Assistent auf normale Fragen. Deutsch, direkt, verständlich. Wenn der Nutzer etwas ausführen oder ändern will, sei praktisch. Keine falschen Versprechen."
        )

    def _summarize_doc(self, text: str) -> str:
        if text.startswith(("PDF nicht", "Word-Datei nicht", "PDF konnte", "Word-Datei konnte")):
            return text
        return self.ollama.complete("Fasse dieses Dokument strukturiert zusammen. Nenne wichtige Punkte und Risiken:\n\n" + text[:14000], system="Du analysierst Dokumente präzise.")

    def analyze_image_file(self, path_text: str) -> str:
        p = Path((path_text or "").strip().strip('"')).expanduser()
        if not p.exists() or not p.is_file():
            return f"Bild nicht gefunden: {p}"
        try:
            b64 = base64.b64encode(p.read_bytes()).decode("ascii")
            return self.ollama.vision(
                "Analysiere dieses Bild/Foto auf Deutsch. Beschreibe Inhalt, wichtige Details und falls es UI/Code/Screenshot ist konkrete Verbesserungsvorschlaege.",
                b64,
                OLLAMA_VISION_MODEL,
            )
        except Exception as e:
            return f"Bildanalyse-Fehler: {e}"

    def _after(self, text: str, patterns):
        out = text.strip()
        for p in patterns:
            out = re.sub(r"^\s*" + re.escape(p) + r"\s*", "", out, flags=re.I).strip()
        return out
