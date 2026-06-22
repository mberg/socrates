from app.ingest.extractor import Extraction, ExtractedProblem
from app.ingest.validate import validate


def _ex(problems):
    return Extraction(title="t", instructions=None, worked_example=None, problems=problems)


def test_valid_contiguous_passes():
    res = validate(_ex([
        ExtractedProblem(number=1, prompt="2 + 3", correct_answer="5"),
        ExtractedProblem(number=2, prompt="10 - 4", correct_answer="6"),
    ]))
    assert res.ok and res.reason is None


def test_non_integer_answer_not_quarantined():
    # Exponent / distributive-expansion answers aren't plain integers; the
    # arithmetic check should skip (not fail) them.
    res = validate(_ex([
        ExtractedProblem(number=1, prompt="18 × 18", correct_answer="18^2"),
        ExtractedProblem(number=2, prompt="6 × 562", correct_answer="6 x (500 + 60 + 2)"),
    ]))
    assert res.ok and res.reason is None


def test_non_contiguous_numbering_quarantined():
    res = validate(_ex([
        ExtractedProblem(number=1, prompt="x", correct_answer="a"),
        ExtractedProblem(number=3, prompt="y", correct_answer="b"),
    ]))
    assert not res.ok
    assert "contiguous" in res.reason


def test_wrong_arithmetic_quarantined():
    res = validate(_ex([ExtractedProblem(number=1, prompt="6 x 8", correct_answer="54")]))
    assert not res.ok
    assert "arithmetic" in res.reason


def test_empty_problem_list_quarantined():
    res = validate(_ex([]))
    assert not res.ok
    assert "no problems" in res.reason
