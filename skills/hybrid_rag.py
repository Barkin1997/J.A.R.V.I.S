import json
import math
import re
import sqlite3
from collections import Counter

from config import RAG_DB, RAG_TOP_K, HYBRID_RAG_KEYWORD_WEIGHT, HYBRID_RAG_VECTOR_WEIGHT


class HybridRAG:
    def __init__(self, rag_memory):
        self.rag = rag_memory
        self.db = RAG_DB

    def search(self, query: str, top_k: int = None) -> str:
        query = query.strip()
        if not query:
            return "Hybrid-RAG-Suchfrage fehlt."
        top_k = top_k or RAG_TOP_K
        try:
            q_emb = self.rag.embed(query)
        except Exception as e:
            return f"Embedding-Fehler: {e}"

        q_terms = self._terms(query)
        rows = []
        with sqlite3.connect(self.db) as con:
            for source, idx, text, emb_json in con.execute("SELECT source, chunk_index, text, embedding FROM chunks"):
                try:
                    emb = json.loads(emb_json)
                    v_score = self._cosine(q_emb, emb)
                    k_score = self._keyword_score(q_terms, text)
                    score = HYBRID_RAG_VECTOR_WEIGHT * v_score + HYBRID_RAG_KEYWORD_WEIGHT * k_score
                    rows.append((score, v_score, k_score, source, idx, text))
                except Exception:
                    continue

        rows.sort(reverse=True, key=lambda x: x[0])
        if not rows:
            return "Keine RAG-Daten gefunden."

        parts = []
        for score, vs, ks, source, idx, text in rows[:top_k]:
            parts.append(f"[hybrid={score:.3f} vector={vs:.3f} keyword={ks:.3f}] {source} #{idx}\n{text[:2000]}")
        return "\n\n---\n\n".join(parts)

    def ask(self, query: str, ollama, model: str) -> str:
        context = self.search(query)
        if context.startswith(("Keine", "Embedding", "Hybrid")):
            return context
        return ollama.complete(
            f"Beantworte mit diesem Hybrid-RAG-Kontext. Wenn der Kontext nicht reicht, sag es.\n\nKontext:\n{context}\n\nFrage:\n{query}",
            model=model,
            system="Du bist Hybrid-RAG-Assistent. Deutsch, quellenbezogen, keine Erfindungen.",
            temperature=0.02
        )

    def _terms(self, text: str):
        return [t for t in re.findall(r"[a-zA-ZäöüÄÖÜß0-9_]{3,}", text.lower())]

    def _keyword_score(self, q_terms, text: str) -> float:
        if not q_terms:
            return 0.0
        terms = Counter(self._terms(text))
        hits = sum(min(terms.get(t, 0), 3) for t in q_terms)
        return min(1.0, hits / max(1, len(q_terms) * 3))

    def _cosine(self, a, b) -> float:
        n = min(len(a), len(b))
        if n == 0:
            return 0.0
        aa = a[:n]
        bb = b[:n]
        dot = sum(x*y for x,y in zip(aa,bb))
        na = math.sqrt(sum(x*x for x in aa))
        nb = math.sqrt(sum(y*y for y in bb))
        return 0.0 if na == 0 or nb == 0 else dot / (na * nb)
