from config import (
    FEEDBACK_MODEL,
    FIXER_MODEL,
    MULTI_AGENT_MODEL,
    PLANNER_MODEL,
    SECURITY_MODEL,
    TESTER_MODEL,
)


class FeedbackAgent:
    def __init__(self, ollama):
        self.ollama = ollama

    def review(self, task: str, plan: str, result: str) -> str:
        prompt = f"""
Pruefe dieses Multi-Agent-Ergebnis kritisch.

Aufgabe:
{task}

Plan:
{plan}

Ergebnis:
{result}

Antworte kurz in diesem Format:
STATUS: OK oder FIX_NEEDED
KATEGORIE: syntax/logik/sicherheit/unvollstaendig/qualitaet
PROBLEM: ein Satz
KORREKTUR_AUFTRAG: konkrete Korrektur, falls noetig
"""
        return self.ollama.complete(
            prompt,
            model=FEEDBACK_MODEL,
            system="Du bist Feedback-Agent. Pruefe streng, aber kurz und praktisch.",
            temperature=0.01,
            ctx=8192,
            num_predict=700,
            timeout=120,
        )

    def needs_fix(self, feedback: str) -> bool:
        low = (feedback or "").lower()
        return "fix_needed" in low or "nicht ok" in low or "fehler" in low


class MultiAgent:
    def __init__(self, ollama, coder, terminal=None):
        self.ollama = ollama
        self.coder = coder
        self.terminal = terminal
        self.feedback = FeedbackAgent(ollama)

    def feedback_loop(self, task: str, plan: str, result: str) -> str:
        feedback = self.feedback.review(task, plan, result)
        if not self.feedback.needs_fix(feedback):
            return feedback

        correction = self.ollama.complete(
            "Verbessere das Ergebnis anhand dieses Feedbacks. Gib eine konkrete korrigierte Fassung.\n\n"
            f"Aufgabe:\n{task}\n\nPlan:\n{plan}\n\nErgebnis:\n{result}\n\nFeedback:\n{feedback}",
            model=FIXER_MODEL,
            system="Du bist Fixer-Agent. Deutsch, konkret, keine Wiederholung ohne Verbesserung.",
            temperature=0.02,
            ctx=8192,
            num_predict=1200,
            timeout=150,
        )
        return f"{feedback}\n\nFixer-Agent:\n{correction}"

    def execute(self, task: str) -> str:
        plan = self.ollama.complete(
            f"Erstelle einen praezisen Ausfuehrungsplan fuer diese Aufgabe:\n\n{task}",
            model=PLANNER_MODEL,
            system="Du bist Planner-Agent. Deutsch, konkrete Schritte, Risiken nennen.",
            temperature=0.02,
            ctx=8192,
            num_predict=1000,
            timeout=150,
        )

        security = self.ollama.complete(
            f"Pruefe diesen Auftrag auf Risiken. Antworte kurz mit SAFE oder BLOCK und Begruendung.\n\nAuftrag:\n{task}\n\nPlan:\n{plan}",
            model=SECURITY_MODEL,
            system="Du bist Security-Agent. Streng. Keine gefaehrlichen finalen Aktionen erlauben.",
            temperature=0.01,
            ctx=8192,
            num_predict=600,
            timeout=120,
        )

        if "BLOCK" in security.upper():
            return f"Security-Agent blockiert.\n\n{security}\n\nPlan:\n{plan}"

        if any(x in task.lower() for x in ["code", "programmiere", "projekt", "c++", "python", "java", "webseite", "spiel", "app"]):
            created = self.coder.create_code_project("BESTE QUALITAET. Multi-Agent-Auftrag:\n" + task + "\n\nPlan:\n" + plan)
            review = self.ollama.complete(
                f"Bewerte das erzeugte Ergebnis. Nenne verbleibende Schwaechen und naechste Verbesserungen.\n\n{created}",
                model=TESTER_MODEL,
                system="Du bist Tester-Agent. Deutsch, direkt, technisch.",
                temperature=0.02,
                ctx=8192,
                num_predict=1000,
                timeout=150,
            )
            feedback = self.feedback_loop(task, plan, f"{created}\n\nTester-Agent:\n{review}")
            return (
                f"Planner-Agent:\n{plan}\n\n"
                f"Security-Agent:\n{security}\n\n"
                f"Ausfuehrung:\n{created}\n\n"
                f"Tester-Agent:\n{review}\n\n"
                f"Feedback-Agent:\n{feedback}"
            )

        answer = self.ollama.complete(
            f"Fuehre diese Aufgabe anhand des Plans aus.\n\nAufgabe:\n{task}\n\nPlan:\n{plan}",
            model=MULTI_AGENT_MODEL,
            system="Du bist Executor-Agent. Deutsch, praezise, maximal gruendlich.",
            temperature=0.03,
            ctx=8192,
            num_predict=1300,
            timeout=150,
        )
        feedback = self.feedback_loop(task, plan, answer)
        return (
            f"Planner-Agent:\n{plan}\n\n"
            f"Security-Agent:\n{security}\n\n"
            f"Executor-Agent:\n{answer}\n\n"
            f"Feedback-Agent:\n{feedback}"
        )
