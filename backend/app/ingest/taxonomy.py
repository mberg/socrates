import re
from dataclasses import dataclass
from pathlib import PurePath

_GRADE_RE = re.compile(r"^grade-(\d+)-(.+)$")
_VARIANT_RE = re.compile(r"^(.*)-([a-z]\d*)$")


@dataclass(frozen=True)
class Taxonomy:
    grade: int
    topic: str
    skill_key: str
    variant: str | None
    regular: bool


def parse_filename(pdf_path: str) -> Taxonomy:
    p = PurePath(pdf_path)
    topic = p.parent.name
    # Normalize underscores to hyphens so grade_3_foo_b4 → grade-3-foo-b4
    stem = p.stem.replace("_", "-")
    m = _GRADE_RE.match(stem)
    if not m:
        raise ValueError(f"not a grade-N worksheet: {pdf_path}")
    grade = int(m.group(1))
    rest = m.group(2)
    vm = _VARIANT_RE.match(rest)
    if vm:
        return Taxonomy(grade, topic, vm.group(1), vm.group(2), regular=True)
    return Taxonomy(grade, topic, rest, None, regular=False)
