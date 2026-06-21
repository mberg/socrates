import pytest

from app.ingest.taxonomy import parse_filename


@pytest.mark.parametrize(
    "path, grade, topic, skill_key, variant, regular",
    [
        ("worksheets/place-value-rounding/grade-5-place-value-5-digit-a.pdf",
         5, "place-value-rounding", "place-value-5-digit", "a", True),
        ("worksheet-g3/telling-time/grade-3-calendar-reading-d.pdf",
         3, "telling-time", "calendar-reading", "d", True),
        ("worksheet-g3/telling-time/grade-3-calendar-months-as-numbers.pdf",
         3, "telling-time", "calendar-months-as-numbers", None, False),
        ("worksheet-g3/telling-time/grade-3-calendar-months-as-numbers-cdf.pdf",
         3, "telling-time", "calendar-months-as-numbers-cdf", None, False),
        # Underscore filename + letter+digit variant (FIX 3)
        ("worksheet-g3/word-problems-mixed/grade_3_addition_word_problems_b4.pdf",
         3, "word-problems-mixed", "addition-word-problems", "b4", True),
    ],
)
def test_parse_filename(path, grade, topic, skill_key, variant, regular):
    t = parse_filename(path)
    assert (t.grade, t.topic, t.skill_key, t.variant, t.regular) == (grade, topic, skill_key, variant, regular)


def test_parse_filename_rejects_non_grade():
    with pytest.raises(ValueError):
        parse_filename("worksheets/x/notes.pdf")
