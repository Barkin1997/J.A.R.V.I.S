import json
import math
import sqlite3
from pathlib import Path
from typing import List

import requests

from config import OLLAMA_URL, OLLAMA_EMBED_MODEL, RAG_DB, RAG_CHUNK_SIZE, RAG_TOP_K


TEXT_EXTS = {
    ".txt", ".md", ".py", ".js", ".ts", ".html", ".css", ".json", ".xml",
    ".cpp", ".hpp", ".h", ".c", ".cs", ".java", ".go", ".rs", ".php",
    ".bat", ".ps1", ".sql", ".yml", ".yaml", ".log"
}


class RAGMemory:
    def __init__(self):
        self.db = RAG_DB
        self.db.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _connect(self):
        return sqlite3.connect(self.db)

    def _init(self):
        with self._connect() as con:
            con.execute("""
                CREATE TABLE IF NOT EXISTS chunks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    text TEXT NOT NULL,
                    embedding TEXT NOT NULL
                )
            """)
            con.execute("CREATE INDEX IF NOT EXISTS idx_chunks_source ON chunks(source)")

    def embed(self, text: str) -> List[float]:
        text = text[:12000]
        try:
            r = requests.post(
                f"{OLLAMA_URL}/api/embed",
                json={"model": OLLAMA_EMBED_MODEL, "input": text},
                timeout=180,
            )
            r.raise_for_status()
            data = r.json()
            embeddings = data.get("embeddings") or []
            if embeddings:
                return [float(x) for x in embeddings[0]]
        except Exception:
            pass

        r = requests.post(
            f"{OLLAMA_URL}/api/embeddings",
            json={"model": OLLAMA_EMBED_MODEL, "prompt": text},
            timeout=180,
        )
        r.raise_for_status()
        return [float(x) for x in r.json().get("embedding", [])]

    def index_text(self, source: str, text: str) -> str:
        source = source.strip() or "manual_text"
        chunks = self._chunk(text or "")
        count = 0
        with self._connect() as con:
            con.execute("DELETE FROM chunks WHERE source=?", (source,))
            for i, chunk in enumerate(chunks):
                try:
                    emb = self.embed(chunk)
                    if not emb:
                        continue
                    con.execute(
                        "INSERT INTO chunks(source, chunk_index, text, embedding) VALUES (?, ?, ?, ?)",
                        (source, i, chunk, json.dumps(emb))
                    )
                    count += 1
                except Exception:
                    continue
        return f"RAG gespeichert: {source}. Chunks: {count}."

    def index_path(self, path_text: str) -> str:
        p = Path(path_text.strip().strip('"')).expanduser()
        if not p.exists():
            return f"Pfad nicht gefunden: {p}"

        files = [p] if p.is_file() else [f for f in p.rglob("*") if f.is_file() and f.suffix.lower() in TEXT_EXTS]
        count_files = 0
        count_chunks = 0
        errors = []

        with self._connect() as con:
            for f in files:
                try:
                    text = f.read_text(encoding="utf-8", errors="ignore")
                    chunks = self._chunk(text)
                    con.execute("DELETE FROM chunks WHERE source=?", (str(f),))
                    for i, chunk in enumerate(chunks):
                        emb = self.embed(chunk)
                        if not emb:
                            continue
                        con.execute(
                            "INSERT INTO chunks(source, chunk_index, text, embedding) VALUES (?, ?, ?, ?)",
                            (str(f), i, chunk, json.dumps(emb))
                        )
                        count_chunks += 1
                    count_files += 1
                except Exception as e:
                    errors.append(f"{f}: {e}")

        result = f"RAG indexiert. Dateien: {count_files}. Chunks: {count_chunks}. Modell: {OLLAMA_EMBED_MODEL}"
        if errors:
            result += "\nFehler:\n" + "\n".join(errors[:10])
        return result

    def search(self, query: str, top_k: int = None) -> str:
        query = query.strip()
        if not query:
            return "RAG-Suchfrage fehlt."
        top_k = top_k or RAG_TOP_K
        try:
            q_emb = self.embed(query)
        except Exception as e:
            return f"Embedding-Fehler. Modell laden: ollama pull {OLLAMA_EMBED_MODEL}\n{e}"

        rows = []
        with self._connect() as con:
            for source, idx, text, emb_json in con.execute("SELECT source, chunk_index, text, embedding FROM chunks"):
                try:
                    emb = json.loads(emb_json)
                    score = self._cosine(q_emb, emb)
                    rows.append((score, source, idx, text))
                except Exception:
                    continue

        rows.sort(reverse=True, key=lambda x: x[0])
        if not rows:
            return "Keine RAG-Daten gefunden. Erst Ordner oder Webseite indexieren."

        parts = []
        for score, source, idx, text in rows[:top_k]:
            parts.append(f"[{score:.3f}] {source} #{idx}\n{text[:1800]}")
        return "\n\n---\n\n".join(parts)

    def ask(self, query: str, ollama, model: str) -> str:
        context = self.search(query)
        if context.startswith(("Keine RAG", "Embedding-Fehler", "RAG-Suchfrage")):
            return context
        return ollama.complete(
            f"Beantworte die Frage nur mit dem Kontext. Wenn der Kontext nicht reicht, sage es.\n\nKontext:\n{context}\n\nFrage:\n{query}",
            model=model,
            system="Du bist ein RAG-Assistent. Deutsch, präzise, keine erfundenen Details.",
            temperature=0.03,
        )

    def _chunk(self, text: str) -> List[str]:
        text = "\n".join(line.rstrip() for line in (text or "").splitlines())
        chunks = []
        i = 0
        while i < len(text):
            chunk = text[i:i + RAG_CHUNK_SIZE]
            if chunk.strip():
                chunks.append(chunk.strip())
            i += max(500, RAG_CHUNK_SIZE - 250)
        return chunks

    def _cosine(self, a: List[float], b: List[float]) -> float:
        n = min(len(a), len(b))
        if n == 0:
            return 0.0
        aa = a[:n]
        bb = b[:n]
        dot = sum(x * y for x, y in zip(aa, bb))
        na = math.sqrt(sum(x * x for x in aa))
        nb = math.sqrt(sum(y * y for y in bb))
        return 0.0 if na == 0 or nb == 0 else dot / (na * nb)
