from pathlib import Path

from app.cli import discover_pdfs


def test_discover_pdfs_finds_only_grade_pdfs(tmp_path):
    (tmp_path / "topic").mkdir()
    (tmp_path / "topic" / "grade-5-foo-a.pdf").write_bytes(b"%PDF")
    (tmp_path / "topic" / "notes.txt").write_text("x")
    found = discover_pdfs(str(tmp_path))
    assert found == [str(tmp_path / "topic" / "grade-5-foo-a.pdf")]
