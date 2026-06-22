import re
from dataclasses import dataclass

from app.ingest.extractor import Extraction

_ARITH_RE = re.compile(r"^\s*([\d,]+)\s*([+\-x×*])\s*([\d,]+)\s*=?\s*$")


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    reason: str | None
    confidence: float


def _as_int(s: str) -> int:
    return int(s.replace(",", ""))


def _check_arithmetic(prompt: str, answer: str) -> bool | None:
    m = _ARITH_RE.match(prompt)
    if not m:
        return None
    a, op, b = _as_int(m.group(1)), m.group(2), _as_int(m.group(3))
    expected = {"+": a + b, "-": a - b, "x": a * b, "×": a * b, "*": a * b}[op]
    try:
        answer_int = _as_int(answer)
    except ValueError:
        # Answer isn't a plain integer (e.g. "18^2" for exponents, or a worked
        # distributive expansion) — we can't arithmetic-check it, so skip rather
        # than treat it as a mismatch.
        return None
    return answer_int == expected


def validate(extraction: Extraction) -> ValidationResult:
    problems = extraction.problems
    if not problems:
        return ValidationResult(False, "no problems extracted", 0.0)
    numbers = [p.number for p in problems]
    if numbers != list(range(1, len(problems) + 1)):
        return ValidationResult(False, f"numbering not contiguous 1..N: {numbers}", 0.0)
    for p in problems:
        checked = _check_arithmetic(p.prompt, p.correct_answer)
        if checked is False:
            return ValidationResult(False, f"arithmetic mismatch on #{p.number}: {p.prompt}={p.correct_answer}", 0.0)
    confidence = min((p.confidence for p in problems if p.confidence is not None), default=1.0)
    return ValidationResult(True, None, confidence)
