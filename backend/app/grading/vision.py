from typing import Protocol

from pydantic import BaseModel


class ProblemPrompt(BaseModel):
    number: int
    prompt: str


class ProblemRead(BaseModel):
    number: int
    read_answer: str | None = None
    confidence: float


class VisionRead(BaseModel):
    printed_id: str | None = None
    problems: list[ProblemRead]


class Vision(Protocol):
    def read(self, image: bytes, problems: list[ProblemPrompt]) -> VisionRead: ...
    def judge_equivalence(self, read_answer: str, correct_answer: str) -> bool: ...


class FakeVision:
    def __init__(self, result: VisionRead, *, equivalent: bool = False) -> None:
        self._result = result
        self._equivalent = equivalent

    def read(self, image: bytes, problems: list[ProblemPrompt]) -> VisionRead:
        return self._result

    def judge_equivalence(self, read_answer: str, correct_answer: str) -> bool:
        return self._equivalent
