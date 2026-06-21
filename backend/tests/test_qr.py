def test_make_qr_png_returns_png_bytes():
    from app.printing.qr import make_qr_png
    data = make_qr_png("attempt-abc123")
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(data) > 100


def test_make_qr_png_is_decodable_shape():
    # Two different payloads produce different images.
    from app.printing.qr import make_qr_png
    assert make_qr_png("a") != make_qr_png("bbbbbbbb")
