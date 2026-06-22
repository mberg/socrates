from app.grading.vision import FakeVision, ProblemPrompt, ProblemRead, VisionRead


def test_fake_vision_returns_configured_read():
    result = VisionRead(printed_id="att1", problems=[ProblemRead(number=1, read_answer="4", confidence=0.9)])
    v = FakeVision(result)
    got = v.read(b"img", [ProblemPrompt(number=1, prompt="2+2")])
    assert got.printed_id == "att1"
    assert got.problems[0].read_answer == "4"


def test_fake_vision_equivalence_is_configurable():
    v = FakeVision(VisionRead(printed_id=None, problems=[]), equivalent=True)
    assert v.judge_equivalence("1/2", "0.5") is True
    assert FakeVision(VisionRead(printed_id=None, problems=[])).judge_equivalence("a", "b") is False
