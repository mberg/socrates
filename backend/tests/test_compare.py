import pytest

from app.grading.compare import answers_match, parses_as_number


@pytest.mark.parametrize("s,expected", [
    ("4", True), ("-4", True), ("12.5", True), ("3/6", True), ("1 1/2", True),
    ("1,000", True), (" 7 ", True),
    ("5 R 2", False),       # remainder format — code can't decide
    ("four", False), ("", False), (None, False), ("yes", False),
])
def test_parses_as_number(s, expected):
    assert parses_as_number(s) is expected


@pytest.mark.parametrize("read,correct", [
    ("4", "4"),
    (" 4 ", "4"),            # whitespace
    ("4", "4 "),
    ("Yes", "yes"),          # case
    ("0.50", "0.5"),         # trailing zeros
    ("12", "12.0"),          # int vs float
    ("3/6", "1/2"),          # fraction reduction
    ("1 1/2", "3/2"),        # mixed number
    ("5 cm", "5"),           # trailing unit
    ("1,000", "1000"),       # thousands separator
])
def test_matches(read, correct):
    assert answers_match(read, correct) is True


@pytest.mark.parametrize("read,correct", [
    ("5", "4"),
    ("1/2", "1/3"),
    ("0.6", "0.5"),
    (None, "4"),             # blank read never matches
    ("", "4"),
])
def test_non_matches(read, correct):
    assert answers_match(read, correct) is False
