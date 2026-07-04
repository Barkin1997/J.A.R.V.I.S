import json
import re
from pathlib import Path

from config import AUTOPILOT_MAX_STEPS, AUTOPILOT_BUILD_EVERY_STEP, OLLAMA_CODE_MODEL, PROJECT_DIR


class Autopilot:
    def __init__(self, ollama, coder, repo_agent, test_generator, refactor_agent, task_manager, project_memory):
        self.ollama = ollama
        self.coder = coder
        self.repo_agent = repo_agent
        self.test_generator = test_generator
        self.refactor_agent = refactor_agent
        self.task_manager = task_manager
        self.project_memory = project_memory

    def run(self, goal: str) -> str:
        goal = goal.strip()
        if not goal:
            return "Autopilot-Ziel fehlt."

        plan_raw = self.ollama.complete(
            f"""
Zerlege dieses Projektziel in maximal {AUTOPILOT_MAX_STEPS} konkrete Arbeitsschritte.

Ziel:
{goal}

Antworte NUR JSON:
{{"project_name":"kurzer_name","steps":["..."]}}
""",
            model=OLLAMA_CODE_MODEL,
            system="Du bist Projekt-Autopilot-Planner. Nur JSON.",
            temperature=0.02
        )
        data = self._parse_json(plan_raw) or {"project_name": "autopilot_project", "steps": [goal]}
        name = re.sub(r"[^a-zA-Z0-9_-]+", "_", data.get("project_name", "autopilot_project")).strip("_") or "autopilot_project"
        steps = data.get("steps", [])[:AUTOPILOT_MAX_STEPS] or [goal]

        log = [f"Autopilot startet: {name}", "Schritte:", "\n".join(f"{i+1}. {s}" for i,s in enumerate(steps))]
        project_path = ""

        first = self.coder.create_code_project("ULTRA AUTOPILOT. Erstelle Grundprojekt für: " + goal + "\nErster Schritt: " + steps[0])
        log.append("\nGrundprojekt:\n" + first)
        project_path = self._extract_project_path(first)

        if project_path:
            self.project_memory.save(name, project_path, goal, "Grundprojekt erstellt", steps[1] if len(steps) > 1 else "Tests/Finalisierung")
            for s in steps[1:]:
                self.task_manager.add(s, project=name, priority=2)

            for i, step in enumerate(steps[1:], start=2):
                log.append(f"\nAutopilot Schritt {i}: {step}")
                changed = self.repo_agent.modify(project_path, step)
                log.append(changed)

                if AUTOPILOT_BUILD_EVERY_STEP:
                    tests = self.test_generator.generate_tests(project_path, goal)
                    log.append("\nTests:\n" + tests)

            ref = self.refactor_agent.refactor(project_path, "Finaler Refactor: Architektur verbessern, Duplikate reduzieren, README und Startanleitung prüfen.")
            log.append("\nFinaler Refactor:\n" + ref)
            self.project_memory.save(name, project_path, goal, "Autopilot abgeschlossen", "Review durchführen")

        return "\n\n".join(log)

    def _extract_project_path(self, text: str) -> str:
        m = re.search(r"Projekt erstellt:\s*(.+)", text)
        if m:
            p = m.group(1).strip()
            if Path(p).exists():
                return p
        # fallback latest project
        try:
            dirs = [p for p in PROJECT_DIR.iterdir() if p.is_dir()]
            dirs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            return str(dirs[0]) if dirs else ""
        except Exception:
            return ""

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
