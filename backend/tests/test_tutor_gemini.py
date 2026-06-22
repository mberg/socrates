import json

from app.tutor.base import TutorContext, Turn
from app.tutor.gemini import GeminiTutor


class _Resp:
    def __init__(self, text): self.text = text


class _Models:
    def __init__(self, payload): self._payload = payload; self.last = None
    def generate_content(self, *, model, contents, config):
        self.last = {"model": model, "contents": contents, "config": config}
        return _Resp(self._payload)


class _Client:
    def __init__(self, payload): self.models = _Models(payload)


async def test_respond_parses_structured_reply():
    payload = json.dumps({"say": "What operation?", "visuals": [{"type": "math", "tex": "3 x 4", "display": False}]})
    client = _Client(payload)
    tutor = GeminiTutor(client=client, model="m")
    # Worked example demonstrates the method with a *different* problem (as real
    # worksheets do), so "12" only appears if the correct_answer leaks into context.
    ctx = TutorContext(problem_prompt="3 x 4", worked_example="2 x 5 = 10", grade=3,
                       child_name="Ada", child_answer="7", correct_answer=None)
    reply = await tutor.respond(ctx, [Turn(role="child", text="help")], tier=1)
    assert reply.say == "What operation?"
    assert reply.visuals[0]["type"] == "math"
    # Tier-1 prompt must NOT contain the answer (it isn't in context anyway).
    assert "12" not in json.dumps(client.models.last["contents"])
