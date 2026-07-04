import sqlite3
from datetime import datetime
from pathlib import Path

from config import SOURCE_ARCHIVE_DB


class SourceArchive:
    def __init__(self):
        self.db = SOURCE_ARCHIVE_DB
        self.db.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _connect(self):
        return sqlite3.connect(self.db)

    def _init(self):
        with self._connect() as con:
            con.execute("""
                CREATE TABLE IF NOT EXISTS sources (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT,
                    url TEXT UNIQUE,
                    query TEXT,
                    content TEXT,
                    created_at TEXT
                )
            """)

    def add(self, title: str, url: str, query: str, content: str) -> str:
        now = datetime.now().isoformat(timespec="seconds")
        with self._connect() as con:
            con.execute("""
                INSERT INTO sources(title,url,query,content,created_at)
                VALUES(?,?,?,?,?)
                ON CONFLICT(url) DO UPDATE SET
                    title=excluded.title,
                    query=excluded.query,
                    content=excluded.content,
                    created_at=excluded.created_at
            """, (title[:500], url[:1000], query[:500], content[:50000], now))
        return f"Quelle gespeichert: {url}"

    def list(self, query: str = "") -> str:
        with self._connect() as con:
            if query:
                rows = con.execute(
                    "SELECT id,title,url,created_at FROM sources WHERE title LIKE ? OR query LIKE ? OR content LIKE ? ORDER BY created_at DESC LIMIT 20",
                    (f"%{query}%", f"%{query}%", f"%{query}%")
                ).fetchall()
            else:
                rows = con.execute("SELECT id,title,url,created_at FROM sources ORDER BY created_at DESC LIMIT 20").fetchall()
        if not rows:
            return "Keine Quellen gespeichert."
        return "\n".join([f"#{i} {t}\n{u}\n{c}" for i,t,u,c in rows])

    def read(self, source_id: int) -> str:
        with self._connect() as con:
            row = con.execute("SELECT title,url,query,content,created_at FROM sources WHERE id=?", (source_id,)).fetchone()
        if not row:
            return "Quelle nicht gefunden."
        t,u,q,c,created = row
        return f"{t}\nURL: {u}\nQuery: {q}\nGespeichert: {created}\n\n{c[:12000]}"
