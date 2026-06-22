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
        # Short code under the QR, stamped LARGE + bold in monospace so a person and
        # the vision model can both read it off a phone photo. It is also the QR
        # payload; the grading cross-check is advisory (the app supplies the id).
        page.insert_text((rect.x0, rect.y1 + 17), "CODE", fontsize=6)
        _CODE_FS = 26
        code_w = fitz.get_text_length(qr_payload, fontname="cobo", fontsize=_CODE_FS)
        page.insert_text((x1 - code_w, rect.y1 + 41), qr_payload, fontsize=_CODE_FS, fontname="cobo")
        result = out.tobytes()
        out.close()
        return result
    finally:
        src.close()
