import sqlite3
from datetime import datetime
from pathlib import Path

from config import PROJECT_MEMORY_DB


class ProjectMemory:
    def __init__(self):
        self.db = PROJECT_MEMORY_DB
        self.db.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _connect(self):
        return sqlite3.connect(self.db)

    def _init(self):
        with self._connect() as con:
            con.execute("""
                CREATE TABLE IF NOT EXISTS projects (
                    name TEXT PRIMARY KEY,
                    path TEXT,
                    goal TEXT,
                    last_status TEXT,
                    next_step TEXT,
                    updated_at TEXT
                )
            """)

    def save(self, name: str, path: str, goal: str, status: str = "", next_step: str = "") -> str:
        name = name.strip()
        if not name:
            return "Projektname fehlt."
        with self._connect() as con:
            con.execute("""
                INSERT INTO projects(name,path,goal,last_status,next_step,updated_at)
                VALUES(?,?,?,?,?,?)
                ON CONFLICT(name) DO UPDATE SET
                    path=excluded.path,
                    goal=excluded.goal,
                    last_status=excluded.last_status,
                    next_step=excluded.next_step,
                    updated_at=excluded.updated_at
            """, (name, path, goal, status, next_step, datetime.now().isoformat(timespec="seconds")))
        return f"Projekt gespeichert: {name}"

    def list(self) -> str:
        with self._connect() as con:
            rows = con.execute("SELECT name,path,goal,last_status,next_step,updated_at FROM projects ORDER BY updated_at DESC LIMIT 20").fetchall()
        if not rows:
            return "Keine Projekte gespeichert."
        return "\n\n".join([f"{n}\nPfad: {p}\nZiel: {g}\nStatus: {s}\nNächster Schritt: {ns}\nUpdate: {u}" for n,p,g,s,ns,u in rows])

    def get(self, name: str) -> str:
        with self._connect() as con:
            row = con.execute("SELECT name,path,goal,last_status,next_step,updated_at FROM projects WHERE name LIKE ? ORDER BY updated_at DESC LIMIT 1", (f"%{name}%",)).fetchone()
        if not row:
            return "Projekt nicht gefunden."
        n,p,g,s,ns,u = row
        return f"{n}\nPfad: {p}\nZiel: {g}\nStatus: {s}\nNächster Schritt: {ns}\nUpdate: {u}"
