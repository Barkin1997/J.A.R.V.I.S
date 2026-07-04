import re
from urllib.parse import urlparse

from config import INTERNET_RESEARCH_MODEL, WEB_MEMORY_AUTO_INDEX


class InternetResearch:
    def __init__(self, browser, ollama, rag=None, archive=None):
        self.browser = browser
        self.ollama = ollama
        self.rag = rag
        self.archive = archive

    def research(self, query: str, pages: int = 7) -> str:
        query = query.strip()
        if not query:
            return "Recherchefrage fehlt."

        if hasattr(self.browser, "google_silent"):
            self.browser.google_silent(query)
        else:
            self.browser.google(query)
        links = self._extract_links()
        selected = []
        seen = set()

        for link in links:
            url = link.get("href", "")
            title = link.get("text", "").strip()
            if not url.startswith("http"):
                continue
            host = urlparse(url).netloc.lower()
            if not host or "google." in host or url in seen:
                continue
            seen.add(url)
            selected.append((title, url))
            if len(selected) >= pages:
                break

        if not selected:
            page = self.browser.read_page_silent() if hasattr(self.browser, "read_page_silent") else self.browser.read_page()
            return self.ollama.complete(
                f"Fasse diese Google-Seite zur Recherchefrage zusammen.\nFrage: {query}\n\n{page[:12000]}",
                model=INTERNET_RESEARCH_MODEL,
                system="Du bist Internet-Recherche-Agent. Deutsch, präzise.",
                temperature=0.02
            )

        collected = []
        for title, url in selected:
            try:
                if hasattr(self.browser, "goto_silent"):
                    self.browser.goto_silent(url)
                    text = self.browser.read_page_silent()
                else:
                    self.browser.goto(url)
                    text = self.browser.read_page()
                collected.append(f"QUELLE: {title}\nURL: {url}\n{text[:10000]}")
                if WEB_MEMORY_AUTO_INDEX and self.rag:
                    self.rag.index_text(f"web:{url}", text)
                if self.archive:
                    self.archive.add(title, url, query, text)
            except Exception as e:
                collected.append(f"QUELLE FEHLER: {url}\n{e}")

        context = "\n\n====================\n\n".join(collected)
        return self.ollama.complete(
            f"Erstelle eine Internet-Recherche auf Deutsch.\n\nFrage:\n{query}\n\nQuelleninhalte:\n{context[:70000]}\n\nGib:\n- Kurzantwort\n- wichtigste Punkte\n- Unterschiede/Widersprüche\n- Quellenliste mit URLs\n- was lokal im Quellenarchiv gespeichert wurde",
            model=INTERNET_RESEARCH_MODEL,
            system="Du bist ein strenger Recherche-Agent. Keine erfundenen Fakten. Nutze nur die gelieferten Webseiteninhalte.",
            temperature=0.02
        )

    def remember_current_page(self) -> str:
        text = self.browser.read_page()
        source = "web:current"
        m = re.search(r"URL:\s*(.+)", text)
        if m:
            source = "web:" + m.group(1).strip()
        title = source
        if self.rag:
            rag_msg = self.rag.index_text(source, text)
        else:
            rag_msg = "RAG nicht verfügbar."
        if self.archive:
            url = source.replace("web:", "", 1)
            self.archive.add(title, url, "manual", text)
        return rag_msg + "\nQuelle archiviert."

    def _extract_links(self):
        if hasattr(self.browser, "extract_links_silent"):
            return self.browser.extract_links_silent(120)
        self.browser._ensure()
        try:
            return self.browser.page.evaluate("""
                () => Array.from(document.querySelectorAll('a'))
                  .map(a => ({text: (a.innerText || a.textContent || '').trim(), href: a.href || ''}))
                  .filter(x => x.href && x.text)
                  .slice(0, 120)
            """)
        except Exception:
            return []
