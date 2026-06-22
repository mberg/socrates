from app.grading.vision import GeminiVision, ProblemPrompt


class _StubModels:
    def __init__(self, text): self._text = text
    def generate_content(self, *, model, contents, config):
        class _R: text = self._text
        return _R()


class _StubClient:
    def __init__(self, text): self.models = _StubModels(text)


def test_gemini_vision_parses_read():
    payload = '{"printed_id": "att9", "problems": [{"number": 1, "read_answer": "4", "confidence": 0.8}]}'
    v = GeminiVision(client=_StubClient(payload))
    got = v.read(b"imgbytes", [ProblemPrompt(number=1, prompt="2+2")])
    assert got.printed_id == "att9"
    assert got.problems[0].read_answer == "4"


def test_gemini_vision_judges_equivalence():
    v = GeminiVision(client=_StubClient('{"equivalent": true}'))
    assert v.judge_equivalence("1/2", "0.5") is True
