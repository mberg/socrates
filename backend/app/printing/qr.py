import io

import qrcode


def make_qr_png(payload: str) -> bytes:
    img = qrcode.make(payload)  # PIL image (qrcode[pil])
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
