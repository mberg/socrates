import subprocess
from dataclasses import dataclass

import fitz  # PyMuPDF

_DPI = 150


@dataclass(frozen=True)
class PdfPages:
    page_count: int
    page1_png: bytes
    page2_png: bytes | None
    page1_text: str
    page2_text: str | None


def _page_text(path: str, page_index: int) -> str:
    n = page_index + 1  # pdftotext is 1-based
    out = subprocess.run(
        ["pdftotext", "-layout", "-f", str(n), "-l", str(n), path, "-"],
        capture_output=True, text=True, check=True,
    )
    return out.stdout


def _render_png(doc: "fitz.Document", page_index: int) -> bytes:
    pix = doc.load_page(page_index).get_pixmap(dpi=_DPI)
    return pix.tobytes("png")


def load_pdf(path: str) -> PdfPages:
    doc = fitz.open(path)
    try:
        count = doc.page_count
        return PdfPages(
            page_count=count,
            page1_png=_render_png(doc, 0),
            page2_png=_render_png(doc, 1) if count > 1 else None,
            page1_text=_page_text(path, 0),
            page2_text=_page_text(path, 1) if count > 1 else None,
        )
    finally:
        doc.close()
