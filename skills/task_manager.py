import sqlite3
from datetime import datetime

from config import TASK_DB


class TaskManager:
    def __init__(self):
        self.db = TASK_DB
        self.db.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _connect(self):
        return sqlite3.connect(self.db)

    def _init(self):
        with self._connect() as con:
            con.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    project TEXT,
                    priority INTEGER DEFAULT 3,
                    status TEXT DEFAULT 'offen',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

    def add(self, title: str, project: str = "", priority: int = 3) -> str:
        title = title.strip()
        if not title:
            return "Aufgabentitel fehlt."
        now = datetime.now().isoformat(timespec="seconds")
        with self._connect() as con:
            con.execute("INSERT INTO tasks(title,project,priority,status,created_at,updated_at) VALUES(?,?,?,?,?,?)", (title, project, priority, "offen", now, now))
        return f"Aufgabe erstellt: {title}"

    def list(self, status: str = "offen") -> str:
        with self._connect() as con:
            rows = con.execute("SELECT id,title,project,priority,status FROM tasks WHERE status=? ORDER BY priority ASC,id ASC LIMIT 30", (status,)).fetchall()
        if not rows:
            return f"Keine Aufgaben mit Status: {status}"
        return "\n".join([f"#{i} [{s}] P{p} {t}" + (f" ({proj})" if proj else "") for i,t,proj,p,s in rows])

    def done(self, task_id: int) -> str:
        with self._connect() as con:
            con.execute("UPDATE tasks SET status='fertig', updated_at=? WHERE id=?", (datetime.now().isoformat(timespec="seconds"), task_id))
        return f"Aufgabe erledigt: {task_id}"

    def next(self) -> str:
        with self._connect() as con:
            row = con.execute("SELECT id,title,project,priority FROM tasks WHERE status='offen' ORDER BY priority ASC,id ASC LIMIT 1").fetchone()
        if not row:
            return "Keine offene Aufgabe."
        i,t,proj,p = row
        return f"Nächste Aufgabe: #{i} P{p} {t}" + (f" ({proj})" if proj else "")
