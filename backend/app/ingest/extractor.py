from typing import Protocol

from pydantic import BaseModel, field_validator

from app.ingest.pdf import PdfPages


class ExtractedProblem(BaseModel):
    number: int
    prompt: str
    correct_answer: str
    confidence: float | None = None

    @field_validator("correct_answer")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("correct_answer must be non-empty")
        return v


class Extraction(BaseModel):
    title: str
    instructions: str | None = None
    worked_example: str | None = None
    problems: list[ExtractedProblem]


class Extractor(Protocol):
    def extract(self, pages: PdfPages) -> Extraction: ...


class FakeExtractor:
    def __init__(self, result: Extraction) -> None:
        self._result = result

    def extract(self, pages: PdfPages) -> Extraction:
        return self._result
