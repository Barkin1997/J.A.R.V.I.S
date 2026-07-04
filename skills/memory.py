import sqlite3
from datetime import datetime
from pathlib import Path
from config import MEMORY_DB

class Memory:
    def __init__(self, db_path: Path = MEMORY_DB):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _connect(self):
        return sqlite3.connect(self.db_path)

    def _init(self):
        with self._connect() as con:
            con.execute("CREATE TABLE IF NOT EXISTS memory (id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL, content TEXT NOT NULL)")
            con.execute("CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(content, content='memory', content_rowid='id')")
            con.execute("CREATE TRIGGER IF NOT EXISTS memory_ai AFTER INSERT ON memory BEGIN INSERT INTO memory_fts(rowid, content) VALUES (new.id, new.content); END;")
            con.execute("CREATE TRIGGER IF NOT EXISTS memory_ad AFTER DELETE ON memory BEGIN INSERT INTO memory_fts(memory_fts, rowid, content) VALUES('delete', old.id, old.content); END;")

    def add(self, content: str) -> str:
        content = content.strip()
        if not content:
            return "Gedächtnis-Eintrag fehlt."
        with self._connect() as con:
            con.execute("INSERT INTO memory(created_at, content) VALUES (?, ?)", (datetime.now().isoformat(timespec="seconds"), content))
        return "Gespeichert."

    def search(self, query: str, limit: int = 8):
        query = query.strip()
        with self._connect() as con:
            if not query:
                return con.execute("SELECT created_at, content FROM memory ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
            safe = " ".join([x for x in query.replace('"', "").split() if len(x) > 1]) or query
            try:
                return con.execute(
                    "SELECT memory.created_at, memory.content FROM memory_fts JOIN memory ON memory_fts.rowid=memory.id WHERE memory_fts MATCH ? ORDER BY rank LIMIT ?",
                    (safe, limit)
                ).fetchall()
            except Exception:
                return con.execute("SELECT created_at, content FROM memory WHERE content LIKE ? ORDER BY id DESC LIMIT ?", (f"%{query}%", limit)).fetchall()

    def format_results(self, query: str) -> str:
        rows = self.search(query)
        if not rows:
            return "Keine passenden Erinnerungen."
        return "\n".join([f"- {d}: {c}" for d, c in rows])
