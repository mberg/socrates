import io

from PIL import Image

from app.grading.image import normalize_for_ocr


def _jpeg_with_orientation(size, orientation):
    im = Image.new("RGB", size, "white")
    exif = im.getexif()
    exif[274] = orientation  # 274 = Orientation
    buf = io.BytesIO()
    im.save(buf, format="JPEG", exif=exif)
    return buf.getvalue()


def test_applies_exif_orientation_to_upright():
    # Orientation 6 means "rotate 90° CW to display"; a 40x20 landscape becomes 20x40.
    out = normalize_for_ocr(_jpeg_with_orientation((40, 20), 6))
    res = Image.open(io.BytesIO(out))
    assert res.size == (20, 40)
    assert res.getexif().get(274) in (None, 1)  # orientation consumed, not re-applied


def test_non_image_bytes_pass_through_unchanged():
    assert normalize_for_ocr(b"not an image") == b"not an image"
