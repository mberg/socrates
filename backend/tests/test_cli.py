from pathlib import Path

import pytest

from app.cli import discover_pdfs, _run
from app.ingest.extractor import Extraction, ExtractedProblem
from app.ingest.pdf import PdfPages
from app.storage import InMemoryObjectStore


def test_discover_pdfs_finds_only_grade_pdfs(tmp_path):
    (tmp_path / "topic").mkdir()
    (tmp_path / "topic" / "grade-5-foo-a.pdf").write_bytes(b"%PDF")
    (tmp_path / "topic" / "notes.txt").write_text("x")
    found = discover_pdfs(str(tmp_path))
    assert found == [str(tmp_path / "topic" / "grade-5-foo-a.pdf")]


def test_discover_pdfs_finds_underscore_named_files(tmp_path):
    """Files using underscore naming (e.g. grade_3_foo_b4.pdf) must be discovered."""
    (tmp_path / "topic").mkdir()
    (tmp_path / "topic" / "grade-5-foo-a.pdf").write_bytes(b"%PDF")
    (tmp_path / "topic" / "grade_3_addition_word_problems_b4.pdf").write_bytes(b"%PDF")
    (tmp_path / "topic" / "notes.txt").write_text("x")
    found = discover_pdfs(str(tmp_path))
    names = [Path(f).name for f in found]
    assert "grade-5-foo-a.pdf" in names
    assert "grade_3_addition_word_problems_b4.pdf" in names
    assert "notes.txt" not in names


_GOOD_EXTRACTION = Extraction(
    title="Addition Word Problems",
    instructions=None,
    worked_example=None,
    problems=[ExtractedProblem(number=1, prompt="1 + 1", correct_answer="2")],
)


_DUMMY_PAGES = PdfPages(1, b"\x89PNG", None, "page text", None)


class _FakeExtractor:
    """Always returns the provided Extraction."""

    def __init__(self, result: Extraction) -> None:
        self._result = result

    def extract(self, pages: PdfPages) -> Extraction:  # noqa: ARG002
        return self._result


class _SelectiveLoader:
    """Raises RuntimeError for the specified filename; returns dummy PdfPages for others."""

    def __init__(self, fail_for: str) -> None:
        self._fail_for = fail_for

    def __call__(self, path: str) -> PdfPages:
        if Path(path).name == self._fail_for:
            raise RuntimeError("simulated corrupt PDF")
        return _DUMMY_PAGES


@pytest.mark.asyncio
async def test_run_continues_past_failure(tmp_path):
    """_run must not abort when one file fails; it should error that file and process the rest."""
    topic = tmp_path / "word-problems-mixed"
    topic.mkdir()

    fail_name = "grade-5-foo-a.pdf"
    ok_name = "grade-5-bar-a.pdf"
    (topic / fail_name).write_bytes(b"%PDF-1.4 bad")
    (topic / ok_name).write_bytes(b"%PDF-1.4 ok")

    store = InMemoryObjectStore()

    result = await _run(
        str(tmp_path),
        dry_run=True,
        extractor=_FakeExtractor(result=_GOOD_EXTRACTION),
        store=store,
        loader=_SelectiveLoader(fail_for=fail_name),
    )

    assert result == 0
    # The ok file was processed (inserted or skipped if already present) and the error file
    # was caught without aborting the loop.  The errored file must NOT appear in the store.
    errored_key = f"worksheets/{__import__('hashlib').sha256(b'%PDF-1.4 bad').hexdigest()}.pdf"
    assert errored_key not in store.objects
