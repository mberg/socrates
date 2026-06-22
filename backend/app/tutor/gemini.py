import asyncio

from pydantic import BaseModel, Field

from app.gcp import make_genai_client
from app.tutor.base import TutorContext, TutorReply, Turn
from app.tutor.visuals import validate_visuals


# Vertex's `types.Schema` rejects the `discriminator` + oneOf-of-$ref shape that a
# Pydantic discriminated union (VisualAction) emits. So the *response schema* uses a
# single flat model spanning the Core 6's fields; `validate_visuals` then coerces each
# emitted visual back into the proper union and drops anything invalid/unknown.
class _Step(BaseModel):
    text: str
    highlight: bool = False


class _Mark(BaseModel):
    value: float
    label: str | None = None
    color: str | None = None


class _Jump(BaseModel):
    from_: float = Field(alias="from")
    to: float
    label: str | None = None

    model_config = {"populate_by_name": True}


class _Bar(BaseModel):
    denominator: int
    shaded: int
    label: str | None = None


class _VisualOut(BaseModel):
    """Union-free superset of the Core 6 so Vertex accepts it as a response schema."""
    type: str
    # math
    tex: str | None = None
    display: bool | None = None
    # steps
    title: str | None = None
    steps: list[_Step] | None = None
    # number_line
    min: float | None = None
    max: float | None = None
    ticks: int | None = None
    marks: list[_Mark] | None = None
    jumps: list[_Jump] | None = None
    # fraction_bar
    bars: list[_Bar] | None = None
    # place_value
    value: float | None = None
    columns: list[str] | None = None
    # mult_grid
    rows: int | None = None
    cols: int | None = None
    partial: bool | None = None


class _GeminiReply(BaseModel):
    say: str
    visuals: list[_VisualOut] = []


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
        else:
            self._client = make_genai_client(api_key=api_key, use_vertex=use_vertex,
                                             project=project, location=location)
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
        raw = [v.model_dump(by_alias=True, exclude_none=True) for v in parsed.visuals]
        visuals = [v.model_dump(by_alias=True) for v in validate_visuals(raw)]
        return TutorReply(say=parsed.say, visuals=visuals)
