from pathlib import Path

import pytest

from app.ingest.pdf import load_pdf

SAMPLE = "worksheets/place-value-rounding/grade-5-place-value-5-digit-a.pdf"


@pytest.mark.skipif(not Path(SAMPLE).exists(), reason="source PDFs not present")
def test_load_pdf_splits_and_reads():
    pages = load_pdf(SAMPLE)
    assert pages.page_count == 2
    assert pages.page1_png[:8] == b"\x89PNG\r\n\x1a\n"
    assert pages.page2_png is not None
    assert "Build a 5-digit number" in pages.page1_text
    # answer key page contains a filled answer the worksheet page does not
    assert "30,104" in pages.page2_text
    assert "30,104" not in pages.page1_text
