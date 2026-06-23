import io

from PIL import Image, ImageOps


def normalize_for_ocr(photo: bytes) -> bytes:
    """Make a camera photo OCR-friendly before storage/vision.

    - Apply EXIF orientation: iPhone photos are stored sideways with an orientation
      flag that vision models ignore, so the worksheet arrives rotated 90°.
    - Gentle auto-contrast to lift shadowed regions.

    Returns the original bytes unchanged if they aren't a decodable image.
    """
    try:
        im = Image.open(io.BytesIO(photo))
        im = ImageOps.exif_transpose(im)
        im = im.convert("RGB")
        im = ImageOps.autocontrast(im, cutoff=2)
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=92)
        return buf.getvalue()
    except Exception:
        return photo
