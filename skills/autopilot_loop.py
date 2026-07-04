import re
from pathlib import Path

from config import AUTOPILOT_LOOP_MAX_ROUNDS, AUTOPILOT_LOOP_REQUIRE_TEST_PASS


class AutopilotLoop:
    def __init__(self, ollama, autopilot, repo_agent, test_generator, refactor_agent, rollback, project_memory):
        self.ollama = ollama
        self.autopilot = autopilot
        self.repo_agent = repo_agent
        self.test_generator = test_generator
        self.refactor_agent = refactor_agent
        self.rollback = rollback
        self.project_memory = project_memory

    def run_until_done(self, goal: str) -> str:
        goal = (goal or "").strip()
        if not goal:
            return "Autopilot-Loop Ziel fehlt."

        logs = ["Autopilot-Loop startet."]
        first = self.autopilot.run(goal)
        logs.append(first)
        project_path = self._extract_project_path(first)

        if not project_path:
            return "\n\n".join(logs + ["Kein Projektpfad erkannt."])

        for round_no in range(1, AUTOPILOT_LOOP_MAX_ROUNDS + 1):
            logs.append(f"\n=== Autopilot Loop Runde {round_no}/{AUTOPILOT_LOOP_MAX_ROUNDS} ===")
            logs.append(self.rollback.backup(project_path, f"loop_round_{round_no}_before"))

            tests = self.test_generator.generate_tests(project_path, goal)
            logs.append("Tests:\n" + tests)

            test_ok = "Exit-Code: 0" in tests or "Exit 0" in tests or "PASS" in tests.upper()
            if AUTOPILOT_LOOP_REQUIRE_TEST_PASS and not test_ok:
                fix_task = (
                    "Die Tests/Builds sind nicht sauber. "
                    "Analysiere Fehler, repariere Code und mache Projekt lauffähig. "
                    "Keine riskanten Aktionen."
                )
                fix = self.repo_agent.modify(project_path, fix_task)
                logs.append("Fix:\n" + fix)
                continue

            review = self.ollama.complete(
                f"""
Bewerte ob dieses Projekt fertig ist.

Ziel:
{goal}

Letzte Testergebnisse:
{tests[:8000]}

Antworte nur:
FERTIG: ja/nein
NÄCHSTER SCHRITT: ...
""",
                system="Du bist Final-Review-Agent. Deutsch, streng.",
                temperature=0.02
            )
            logs.append("Review:\n" + review)

            if "FERTIG: ja" in review.lower() or "fertig: ja" in review.lower():
                final = self.refactor_agent.refactor(project_path, "Finaler Qualitäts-Refactor, README prüfen, Startanleitung verbessern.")
                logs.append("Finaler Refactor:\n" + final)
                self.project_memory.save(Path(project_path).name, project_path, goal, "Fertig", "Nichts")
                logs.append("Autopilot-Loop abgeschlossen.")
                break

            next_step = self._extract_next(review)
            if not next_step:
                next_step = "Verbessere die noch fehlenden Punkte und bringe Tests zum Bestehen."
            improve = self.repo_agent.modify(project_path, next_step)
            logs.append("Verbesserung:\n" + improve)

        return "\n\n".join(logs)

    def _extract_project_path(self, text: str) -> str:
        m = re.search(r"Projekt erstellt:\s*(.+)", text)
        if m:
            p = m.group(1).strip()
            if Path(p).exists():
                return p
        m = re.search(r"([A-Z]:\\[^\n\r]+)", text)
        if m and Path(m.group(1).strip()).exists():
            return m.group(1).strip()
        return ""

    def _extract_next(self, review: str) -> str:
        m = re.search(r"NÄCHSTER SCHRITT:\s*(.+)", review, flags=re.I)
        return m.group(1).strip() if m else ""
