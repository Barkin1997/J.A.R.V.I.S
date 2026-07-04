from pathlib import Path
from docx import Document
from pypdf import PdfReader
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from config import PROJECT_DIR

class DocumentSkill:
    def read_pdf(self, path: str) -> str:
        p = Path(path.strip().strip('"')).expanduser()
        if not p.exists():
            return f"PDF nicht gefunden: {p}"
        try:
            reader = PdfReader(str(p))
            parts = []
            for i, page in enumerate(reader.pages[:30], start=1):
                parts.append(f"--- Seite {i} ---\n{page.extract_text() or ''}")
            out = "\n\n".join(parts).strip()
            return out[:14000] + ("\n..." if len(out) > 14000 else "")
        except Exception as e:
            return f"PDF konnte nicht gelesen werden: {e}"

    def read_docx(self, path: str) -> str:
        p = Path(path.strip().strip('"')).expanduser()
        if not p.exists():
            return f"Word-Datei nicht gefunden: {p}"
        try:
            doc = Document(str(p))
            text = "\n".join([para.text for para in doc.paragraphs if para.text.strip()])
            return text[:14000] + ("\n..." if len(text) > 14000 else "")
        except Exception as e:
            return f"Word-Datei konnte nicht gelesen werden: {e}"

    def create_pdf(self, filename: str, text: str) -> str:
        filename = filename.strip().replace("/", "_").replace("\\", "_") or "jarvis_dokument.pdf"
        if not filename.lower().endswith(".pdf"):
            filename += ".pdf"
        path = PROJECT_DIR / filename
        c = canvas.Canvas(str(path), pagesize=A4)
        width, height = A4
        x, y = 50, height - 60
        for raw in text.splitlines():
            line = raw.strip()
            while len(line) > 95:
                c.drawString(x, y, line[:95])
                line = line[95:]
                y -= 16
                if y < 60:
                    c.showPage()
                    y = height - 60
            c.drawString(x, y, line)
            y -= 16
            if y < 60:
                c.showPage()
                y = height - 60
        c.save()
        return f"PDF erstellt: {path}"

    def draft_email(self, subject: str, body: str) -> str:
        folder = PROJECT_DIR / "email_entwuerfe"
        folder.mkdir(parents=True, exist_ok=True)
        safe = "".join(ch for ch in subject if ch.isalnum() or ch in " _-").strip()[:60] or "email_entwurf"
        path = folder / f"{safe}.txt"
        path.write_text(f"Betreff: {subject}\n\n{body}", encoding="utf-8")
        return f"E-Mail-Entwurf gespeichert: {path}"
