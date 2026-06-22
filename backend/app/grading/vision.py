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


from google import genai


class _Equivalence(BaseModel):
    equivalent: bool


_READ_PROMPT = (
    "You are given a photo of a child's completed math worksheet plus the list of "
    "its numbered problems. For EVERY problem number, return what the child wrote as "
    "the answer (read_answer), or null if blank/unreadable, with a confidence in "
    "[0,1]. Also return printed_id: the short 5-character code (letters and digits) "
    "printed in large monospace under the QR at the top (or null if you can't read "
    "it). Do not grade — only transcribe."
)

_EQUIV_PROMPT = (
    "Are these two math answers equivalent (same value, ignoring format/units)? "
    "Return {\"equivalent\": true|false}."
)


class GeminiVision:
    def __init__(
        self,
        api_key: str = "",
        model: str = "gemini-3.1-flash-lite",
        *,
        use_vertex: bool = False,
        project: str | None = None,
        location: str | None = None,
        client=None,
    ) -> None:
        if client is not None:
            self._client = client
        elif use_vertex:
            self._client = genai.Client(vertexai=True, project=project, location=location)
        else:
            self._client = genai.Client(api_key=api_key)
        self._model = model

    def read(self, image: bytes, problems: list[ProblemPrompt]) -> VisionRead:
        problem_list = "\n".join(f"{p.number}. {p.prompt}" for p in problems)
        parts = [
            _READ_PROMPT,
            f"PROBLEMS:\n{problem_list}",
            # v1 assumption: camera photos from the iPhone browser are always JPEG.
            # A non-JPEG (e.g. PNG scan) would be sent with a JPEG MIME declaration —
            # acceptable because Gemini sniffs content; revisit if PNG sources become common.
            genai.types.Part.from_bytes(data=image, mime_type="image/jpeg"),
        ]
        resp = self._client.models.generate_content(
            model=self._model,
            contents=parts,
            config={"response_mime_type": "application/json", "response_schema": VisionRead},
        )
        return VisionRead.model_validate_json(resp.text)

    def judge_equivalence(self, read_answer: str, correct_answer: str) -> bool:
        resp = self._client.models.generate_content(
            model=self._model,
            contents=[_EQUIV_PROMPT, f"A: {read_answer}\nB: {correct_answer}"],
            config={"response_mime_type": "application/json", "response_schema": _Equivalence},
        )
        return _Equivalence.model_validate_json(resp.text).equivalent
