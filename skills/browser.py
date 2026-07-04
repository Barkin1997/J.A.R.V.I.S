import re
from urllib.parse import quote_plus
from playwright.sync_api import sync_playwright
from config import BROWSER_USER_DATA

class BrowserSkill:
    def __init__(self):
        self.playwright = None
        self.context = None
        self.page = None
        self.research_browser = None
        self.research_context = None
        self.research_page = None

    def _ensure(self):
        if self.context and self.page:
            return
        self.playwright = sync_playwright().start()
        self.context = self.playwright.chromium.launch_persistent_context(
            user_data_dir=str(BROWSER_USER_DATA),
            headless=False,
            viewport={"width": 1440, "height": 900},
            accept_downloads=True
        )
        self.page = self.context.pages[0] if self.context.pages else self.context.new_page()

    def _ensure_research(self):
        if self.research_context and self.research_page:
            return
        if not self.playwright:
            self.playwright = sync_playwright().start()
        self.research_browser = self.playwright.chromium.launch(headless=True)
        self.research_context = self.research_browser.new_context(
            viewport={"width": 1440, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0 Safari/537.36"
            ),
        )
        self.research_page = self.research_context.new_page()

    def google(self, query: str) -> str:
        query = query.strip() or "Google"
        self._ensure()
        self.page.goto(f"https://www.google.com/search?q={quote_plus(query)}", wait_until="domcontentloaded", timeout=45000)
        return f"Google geöffnet. Suche: {query}"

    def google_silent(self, query: str) -> str:
        query = query.strip() or "Google"
        self._ensure_research()
        self.research_page.goto(f"https://www.google.com/search?q={quote_plus(query)}", wait_until="domcontentloaded", timeout=45000)
        return f"Google im Hintergrund gelesen. Suche: {query}"

    def goto(self, url: str) -> str:
        url = url.strip()
        if not re.match(r"^https?://", url, re.I):
            url = "https://" + url
        self._ensure()
        self.page.goto(url, wait_until="domcontentloaded", timeout=45000)
        return f"Webseite geöffnet: {url}"

    def goto_silent(self, url: str) -> str:
        url = url.strip()
        if not re.match(r"^https?://", url, re.I):
            url = "https://" + url
        self._ensure_research()
        self.research_page.goto(url, wait_until="domcontentloaded", timeout=45000)
        return f"Webseite im Hintergrund gelesen: {url}"

    def read_page(self) -> str:
        self._ensure()
        return self._read_page_object(self.page)

    def read_page_silent(self) -> str:
        self._ensure_research()
        return self._read_page_object(self.research_page)

    def extract_links_silent(self, limit: int = 120):
        self._ensure_research()
        try:
            return self.research_page.evaluate("""
                (limit) => Array.from(document.querySelectorAll('a'))
                  .map(a => ({text: (a.innerText || a.textContent || '').trim(), href: a.href || ''}))
                  .filter(x => x.href && x.text)
                  .slice(0, limit)
            """, limit)
        except Exception:
            return []

    def _read_page_object(self, page) -> str:
        try:
            title = page.title()
        except Exception:
            title = ""
        try:
            text = page.locator("body").inner_text(timeout=10000)
        except Exception as e:
            return f"Webseite konnte nicht gelesen werden: {e}"
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        text = "\n".join(lines)
        if len(text) > 10000:
            text = text[:10000] + "\n..."
        return f"Titel: {title}\nURL: {page.url}\n\n{text}"

    def click_text(self, text: str) -> str:
        text = text.strip()
        if not text:
            return "Klick-Text fehlt."
        self._ensure()
        locators = [
            self.page.get_by_role("button", name=re.compile(re.escape(text), re.I)),
            self.page.get_by_role("link", name=re.compile(re.escape(text), re.I)),
            self.page.get_by_text(text, exact=False)
        ]
        for loc in locators:
            try:
                loc.first.click(timeout=7000)
                return f"Geklickt: {text}"
            except Exception:
                pass
        return f"Element nicht gefunden: {text}"

    def fill_field(self, field: str, value: str) -> str:
        field = field.strip()
        value = value.strip()
        self._ensure()
        locators = [
            self.page.get_by_label(re.compile(re.escape(field), re.I)),
            self.page.get_by_placeholder(re.compile(re.escape(field), re.I)),
            self.page.locator(f"input[name*='{field}' i]"),
            self.page.locator(f"textarea[name*='{field}' i]")
        ]
        for loc in locators:
            try:
                loc.first.fill(value, timeout=7000)
                return f"Feld ausgefüllt: {field}"
            except Exception:
                pass
        return f"Feld nicht gefunden: {field}"

    def new_tab(self, url: str = "about:blank") -> str:
        self._ensure()
        self.page = self.context.new_page()
        if url and url != "about:blank":
            return self.goto(url)
        return "Neuer Tab geöffnet."

    def close_tab(self) -> str:
        self._ensure()
        try:
            self.page.close()
            self.page = self.context.pages[-1] if self.context.pages else self.context.new_page()
            return "Tab geschlossen."
        except Exception as e:
            return f"Tab konnte nicht geschlossen werden: {e}"
