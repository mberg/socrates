import asyncio

from pydantic import BaseModel

from app.tutor.base import TutorContext, TutorReply, Turn
from app.tutor.visuals import VisualAction

from google import genai


class _GeminiReply(BaseModel):
    say: str
    visuals: list[VisualAction] = []


_SYSTEM = (
    "You are Socrates, a warm, patient math tutor for a child in grade {grade}. "
    "Help ONLY with this one problem. Use short, encouraging, age-appropriate language. "
    "NEVER state the final answer unless an explicit answer is provided to you in CONTEXT; "
    "if no answer is given, guide with a question or a single next step instead. "
    "You may include visuals by selecting from the allowed components only. "
    "Tier {tier} guidance: 1=a guiding question giving nothing away; "
    "2=point at the specific slip with one concrete step; 3=full worked solution."
)


class GeminiTutor:
    def __init__(self, api_key: str = "", model: str = "gemini-3.1-flash-lite", *,
                 use_vertex: bool = False, project: str | None = None,
                 location: str | None = None, client=None) -> None:
        if client is not None:
            self._client = client
        elif use_vertex:
            self._client = genai.Client(vertexai=True, project=project, location=location)
        else:
            self._client = genai.Client(api_key=api_key)
        self._model = model

    def _generate(self, contents: list[str]) -> str:
        resp = self._client.models.generate_content(
            model=self._model, contents=contents,
            config={"response_mime_type": "application/json", "response_schema": _GeminiReply},
        )
        return resp.text

    async def respond(self, context: TutorContext, history: list[Turn], tier: int) -> TutorReply:
        lines = [
            _SYSTEM.format(grade=context.grade, tier=tier),
            f"CONTEXT — problem: {context.problem_prompt}",
            f"CONTEXT — worked example on the sheet: {context.worked_example or '(none)'}",
            f"CONTEXT — what {context.child_name} wrote: {context.child_answer or '(blank)'}",
        ]
        if context.correct_answer is not None:
            lines.append(f"CONTEXT — correct answer (Tier 3 unlocked, you may reveal it): {context.correct_answer}")
        for t in history:
            lines.append(f"{t.role.upper()}: {t.text}")
        text = await asyncio.to_thread(self._generate, lines)
        parsed = _GeminiReply.model_validate_json(text)
        return TutorReply(say=parsed.say, visuals=[v.model_dump() for v in parsed.visuals])
