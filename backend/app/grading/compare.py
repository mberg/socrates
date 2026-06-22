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
