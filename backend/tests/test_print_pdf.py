import fitz


def _two_page_pdf() -> bytes:
    doc = fitz.open()
    p1 = doc.new_page()
    p1.insert_text((72, 72), "WORKSHEET PAGE")
    p2 = doc.new_page()
    p2.insert_text((72, 72), "ANSWER KEY SECRET")
    return doc.tobytes()


def test_build_print_pdf_is_single_page_without_answer_key():
    from app.printing.print_pdf import build_print_pdf
    out = build_print_pdf(_two_page_pdf(), "attempt-xyz", caption="Ada · xyz")
    doc = fitz.open(stream=out, filetype="pdf")
    assert doc.page_count == 1
    text = doc[0].get_text()
    assert "WORKSHEET PAGE" in text
    assert "ANSWER KEY SECRET" not in text  # page 2 excluded


def test_build_print_pdf_stamps_an_image():
    from app.printing.print_pdf import build_print_pdf
    out = build_print_pdf(_two_page_pdf(), "attempt-xyz")
    doc = fitz.open(stream=out, filetype="pdf")
    assert len(doc[0].get_images()) >= 1  # the QR image is present
