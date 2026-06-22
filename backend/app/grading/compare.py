import re
from fractions import Fraction

_UNIT_RE = re.compile(r"[a-zA-Z]+$")


def _strip_units(s: str) -> str:
    # drop a trailing alphabetic unit when a number precedes it ("5 cm" -> "5")
    body = s.strip()
    m = _UNIT_RE.search(body)
    if m and body[: m.start()].strip():
        return body[: m.start()].strip()
    return body


def _as_fraction(s: str) -> Fraction | None:
    s = s.replace(",", "").strip()
    try:
        if " " in s:  # mixed number "1 1/2"
            whole, frac = s.split(" ", 1)
            return Fraction(int(whole)) + Fraction(frac)
        return Fraction(s)
    except (ValueError, ZeroDivisionError):
        return None


def _normalize(s: str) -> str:
    return _strip_units(s).strip().lower().replace(",", "")


def answers_match(read: str | None, correct: str) -> bool:
    if read is None or not read.strip():
        return False
    rn, cn = _normalize(read), _normalize(correct)
    if rn == cn:
        return True
    rf, cf = _as_fraction(rn), _as_fraction(cn)
    if rf is not None and cf is not None:
        return rf == cf
    return False


def parses_as_number(s: str | None) -> bool:
    """True when s normalizes to a number/fraction the code can compare on its own.

    When both the read and the correct answer parse as numbers, a normalized
    mismatch is a real value difference the code can decide without a model call.
    When one side doesn't parse (e.g. "5 R 2", a worded answer), the code can't be
    sure a mismatch isn't just a format it doesn't understand — that's when the
    Gemini equivalence fallback earns its keep.
    """
    if s is None or not s.strip():
        return False
    return _as_fraction(_normalize(s)) is not None
