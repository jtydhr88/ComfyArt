import pypdfium2

from ..bot.documents import DOC_ERRORS as TEXT_ERRORS
from ..bot.documents import capped, read_text
from ..bot.media_sheet import jpeg
from ._common import view_path
from .bot_media import ATTACH_MAX_PX

DOC_EXT = (".pdf", ".docx", ".md", ".markdown", ".txt")
PDF_PAGE_IMAGES = 3
PDF_RENDER_LONG = 1024
DOC_ERRORS = (*TEXT_ERRORS, pypdfium2.PdfiumError)


def _pdf(path: str) -> tuple[str, int, list[dict]]:
    pdf = pypdfium2.PdfDocument(path)
    try:
        pages = [f"--- page {i + 1} ---\n{pdf[i].get_textpage().get_text_range().strip()}" for i in range(len(pdf))]
        images = []
        for i in range(min(len(pdf), PDF_PAGE_IMAGES)):
            w, h = pdf[i].get_size()
            images.append(jpeg(pdf[i].render(scale=PDF_RENDER_LONG / max(w, h)).to_pil(), ATTACH_MAX_PX))
        return "\n".join(pages), len(pdf), images
    finally:
        pdf.close()


def read_document(url: str) -> tuple[str, int, list[dict]]:
    path = view_path(url)
    if path.lower().endswith(".pdf"):
        return _pdf(path)
    return read_text(path), 0, []


def document_line(name: str, url: str, text: str, pages: int, images: int) -> str:
    size = f", {pages} pages" if pages else ""
    shown = f"; the first {images} page images are attached" if images else ""
    return f'[Attached document "{name}"{size} — {url}{shown}. Its text:]\n{capped(text)}\n[End of "{name}"]'
