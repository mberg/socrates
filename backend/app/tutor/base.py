from typing import Protocol

from pydantic import BaseModel


class TutorContext(BaseModel):
    problem_prompt: str
    worked_example: str | None
    grade: int
    child_name: str
    child_answer: str | None
    correct_answer: str | None  # set ONLY at Tier 3


class Turn(BaseModel):
    role: str   # "child" | "tutor"
    text: str


class TutorReply(BaseModel):
    say: str
    visuals: list[dict] = []  # raw; the service validates + drops via validate_visuals


class Tutor(Protocol):
    async def respond(
        self, context: TutorContext, history: list[Turn], tier: int
    ) -> TutorReply: ...


class FakeTutor:
    """Deterministic, no network. Echoes the tier and (only at Tier 3) the answer,
    and always emits one valid math visual so visual-path tests have data."""

    async def respond(self, context: TutorContext, history: list[Turn], tier: int) -> TutorReply:
        if tier >= 3 and context.correct_answer is not None:
            say = f"The answer is {context.correct_answer}. Here's why, step by step."
        else:
            say = f"Tier {tier}: what operation does '{context.problem_prompt}' ask for?"
        return TutorReply(say=say, visuals=[{"type": "math", "tex": context.problem_prompt, "display": False}])
