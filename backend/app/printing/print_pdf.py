import fitz

from app.printing.qr import make_qr_png

_QR_SIZE = 64  # points
_MARGIN = 18


def build_print_pdf(source_pdf: bytes, qr_payload: str, caption: str = "") -> bytes:
    src = fitz.open(stream=source_pdf, filetype="pdf")
    try:
        out = fitz.open()
        out.insert_pdf(src, from_page=0, to_page=0)  # page 1 only — never the answer key
        page = out[0]
        qr_png = make_qr_png(qr_payload)
        x1 = page.rect.width - _MARGIN
        y0 = _MARGIN
        rect = fitz.Rect(x1 - _QR_SIZE, y0, x1, y0 + _QR_SIZE)
        page.insert_image(rect, stream=qr_png)
        if caption:
            page.insert_text((rect.x0, rect.y1 + 9), caption, fontsize=6)
        result = out.tobytes()
        out.close()
        return result
    finally:
        src.close()
