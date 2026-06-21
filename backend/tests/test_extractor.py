from app.ingest.extractor import Extraction, ExtractedProblem, FakeExtractor
from app.ingest.pdf import PdfPages


def _pages():
    return PdfPages(2, b"\x89PNG", b"\x89PNG", "prompt text", "answer text")


def test_fake_extractor_returns_canned_result():
    canned = Extraction(
        title="Build a 5-digit number", instructions=None, worked_example="ex",
        problems=[ExtractedProblem(number=1, prompt="30,000 + 100 + 4", correct_answer="30,104", confidence=0.99)],
    )
    out = FakeExtractor(canned).extract(_pages())
    assert out.title == "Build a 5-digit number"
    assert out.problems[0].correct_answer == "30,104"


def test_extraction_rejects_empty_answer():
    import pydantic
    try:
        ExtractedProblem(number=1, prompt="x", correct_answer="", confidence=None)
    except pydantic.ValidationError as e:
        assert "correct_answer" in str(e)
    else:
        raise AssertionError("expected ValidationError for empty answer")
