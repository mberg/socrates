import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.grading.service import grade_submission
from app.grading.vision import FakeVision, ProblemRead, VisionRead
from app.models import Attempt, Child, Problem, ProblemResult, Skill, Worksheet
from app.storage import InMemoryObjectStore


@pytest.fixture
async def fixture():
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as s:
        skill = Skill(grade=5, topic="t", skill_key="k", label="L"); s.add(skill); await s.flush()
        ws = Worksheet(skill_id=skill.id, source="k5", title="W", problem_count=2, pdf_sha256="sha")
        s.add(ws); await s.flush()
        s.add(Problem(worksheet_id=ws.id, number=1, prompt="2+2", correct_answer="4"))
        s.add(Problem(worksheet_id=ws.id, number=2, prompt="3+3", correct_answer="6"))
        child = Child(name="Ada", grade=5); s.add(child); await s.flush()
        attempt = Attempt(child_id=child.id, worksheet_id=ws.id); s.add(attempt); await s.commit()
        attempt_id = attempt.id
    store = InMemoryObjectStore()
    yield factory, store, attempt_id
    await engine.dispose()


async def _attempt(factory, attempt_id):
    async with factory() as s:
        return (await s.exec(select(Attempt).where(Attempt.id == attempt_id))).one()


async def test_grades_all_problems_some_wrong(fixture):
    factory, store, attempt_id = fixture
    vision = FakeVision(VisionRead(printed_id=None, problems=[
        ProblemRead(number=1, read_answer="4", confidence=0.95),
        ProblemRead(number=2, read_answer="7", confidence=0.95),
    ]))
    async with factory() as s:
        attempt = (await s.exec(select(Attempt).where(Attempt.id == attempt_id))).one()
        result = await grade_submission(session=s, store=store, vision=vision,
                                        attempt=attempt, photo=b"img", ext="jpg")
    assert result.score_total == 2
    assert result.score_correct == 1
    by_num = {r.number: r for r in result.results}
    assert by_num[1].is_correct is True and by_num[1].match_method == "exact"
    assert by_num[2].is_correct is False
    att = await _attempt(factory, attempt_id)
    assert att.status == "graded" and att.graded_at is not None and att.scanned_at is not None


async def test_low_confidence_flags_needs_review(fixture):
    factory, store, attempt_id = fixture
    vision = FakeVision(VisionRead(printed_id=None, problems=[
        ProblemRead(number=1, read_answer="4", confidence=0.3),
        ProblemRead(number=2, read_answer="6", confidence=0.99),
    ]))
    async with factory() as s:
        attempt = (await s.exec(select(Attempt).where(Attempt.id == attempt_id))).one()
        result = await grade_submission(session=s, store=store, vision=vision,
                                        attempt=attempt, photo=b"img", ext="jpg")
    by_num = {r.number: r for r in result.results}
    assert by_num[1].needs_review is True
    assert by_num[2].needs_review is False
    assert result.needs_review_count == 1


async def test_gemini_equivalence_fallback_on_mismatch(fixture):
    factory, store, attempt_id = fixture
    # read "four" for problem with correct "4" won't code-match; equivalent=True forces a pass
    vision = FakeVision(VisionRead(printed_id=None, problems=[
        ProblemRead(number=1, read_answer="four", confidence=0.9),
        ProblemRead(number=2, read_answer="6", confidence=0.9),
    ]), equivalent=True)
    async with factory() as s:
        attempt = (await s.exec(select(Attempt).where(Attempt.id == attempt_id))).one()
        result = await grade_submission(session=s, store=store, vision=vision,
                                        attempt=attempt, photo=b"img", ext="jpg")
    by_num = {r.number: r for r in result.results}
    assert by_num[1].is_correct is True and by_num[1].match_method == "gemini_equiv"


async def test_numeric_mismatch_skips_ai_by_default(fixture):
    factory, store, attempt_id = fixture
    # read "5" vs correct "4": both parse as numbers, so the code decides "wrong"
    # WITHOUT calling Gemini — even though this FakeVision would say equivalent.
    vision = FakeVision(VisionRead(printed_id=None, problems=[
        ProblemRead(number=1, read_answer="5", confidence=0.95),
        ProblemRead(number=2, read_answer="6", confidence=0.95),
    ]), equivalent=True)
    async with factory() as s:
        attempt = (await s.exec(select(Attempt).where(Attempt.id == attempt_id))).one()
        result = await grade_submission(session=s, store=store, vision=vision,
                                        attempt=attempt, photo=b"img", ext="jpg")
    by_num = {r.number: r for r in result.results}
    assert by_num[1].is_correct is False        # code decided, Gemini NOT trusted
    assert by_num[1].match_method == "normalized"


async def test_ai_fallback_forces_gemini_on_numeric_mismatch(fixture):
    factory, store, attempt_id = fixture
    vision = FakeVision(VisionRead(printed_id=None, problems=[
        ProblemRead(number=1, read_answer="5", confidence=0.95),
        ProblemRead(number=2, read_answer="6", confidence=0.95),
    ]), equivalent=True)
    async with factory() as s:
        attempt = (await s.exec(select(Attempt).where(Attempt.id == attempt_id))).one()
        result = await grade_submission(session=s, store=store, vision=vision,
                                        attempt=attempt, photo=b"img", ext="jpg", ai_fallback=True)
    by_num = {r.number: r for r in result.results}
    assert by_num[1].is_correct is True          # forced Gemini call, equivalent=True
    assert by_num[1].match_method == "gemini_equiv"


async def test_unparseable_mismatch_uses_gemini_even_by_default(fixture):
    factory, store, attempt_id = fixture
    # "four" doesn't parse as a number, so the code can't decide → Gemini fallback
    # fires even with ai_fallback off (the default).
    vision = FakeVision(VisionRead(printed_id=None, problems=[
        ProblemRead(number=1, read_answer="four", confidence=0.9),
        ProblemRead(number=2, read_answer="6", confidence=0.9),
    ]), equivalent=True)
    async with factory() as s:
        attempt = (await s.exec(select(Attempt).where(Attempt.id == attempt_id))).one()
        result = await grade_submission(session=s, store=store, vision=vision,
                                        attempt=attempt, photo=b"img", ext="jpg")
    by_num = {r.number: r for r in result.results}
    assert by_num[1].is_correct is True and by_num[1].match_method == "gemini_equiv"


async def test_blank_read_is_wrong_not_skipped(fixture):
    factory, store, attempt_id = fixture
    vision = FakeVision(VisionRead(printed_id=None, problems=[
        ProblemRead(number=1, read_answer=None, confidence=0.0),
    ]))  # problem 2 missing from the read entirely
    async with factory() as s:
        attempt = (await s.exec(select(Attempt).where(Attempt.id == attempt_id))).one()
        result = await grade_submission(session=s, store=store, vision=vision,
                                        attempt=attempt, photo=b"img", ext="jpg")
    assert result.score_total == 2  # every problem gets a result
    by_num = {r.number: r for r in result.results}
    assert by_num[1].read_answer is None and by_num[1].is_correct is False
    assert by_num[2].is_correct is False  # missing read → blank result


async def test_identity_mismatch_flags_but_still_grades(fixture):
    factory, store, attempt_id = fixture
    # printed code that won't match the attempt's auto-generated code → identity_ok False,
    # but grading proceeds (the app already resolved the authoritative attempt).
    vision = FakeVision(VisionRead(printed_id="ZZZZZ", problems=[
        ProblemRead(number=1, read_answer="4", confidence=0.95),
        ProblemRead(number=2, read_answer="6", confidence=0.95),
    ]))
    async with factory() as s:
        attempt = (await s.exec(select(Attempt).where(Attempt.id == attempt_id))).one()
        result = await grade_submission(session=s, store=store, vision=vision,
                                        attempt=attempt, photo=b"img", ext="jpg")
    assert result.identity_ok is False
    assert result.score_total == 2  # graded anyway
    att = await _attempt(factory, attempt_id)
    assert att.status == "graded" and att.graded_at is not None


async def test_identity_match_sets_identity_ok(fixture):
    factory, store, attempt_id = fixture
    async with factory() as s:
        attempt = (await s.exec(select(Attempt).where(Attempt.id == attempt_id))).one()
        code = attempt.code
        # model reads the same code (lowercased + spaced) → identity_ok True
        vision = FakeVision(VisionRead(printed_id=f" {code.lower()} ", problems=[
            ProblemRead(number=1, read_answer="4", confidence=0.95),
            ProblemRead(number=2, read_answer="6", confidence=0.95),
        ]))
        result = await grade_submission(session=s, store=store, vision=vision,
                                        attempt=attempt, photo=b"img", ext="jpg")
    assert result.identity_ok is True


async def test_photo_stored_in_object_store(fixture):
    factory, store, attempt_id = fixture
    vision = FakeVision(VisionRead(printed_id=None, problems=[
        ProblemRead(number=1, read_answer="4", confidence=0.9),
        ProblemRead(number=2, read_answer="6", confidence=0.9),
    ]))
    async with factory() as s:
        attempt = (await s.exec(select(Attempt).where(Attempt.id == attempt_id))).one()
        result = await grade_submission(session=s, store=store, vision=vision,
                                        attempt=attempt, photo=b"img", ext="jpg")
    key = f"submissions/{result.submission_id}.jpg"
    assert store.get(key) == b"img"


async def test_photo_is_canonicalized_to_upright_jpeg(fixture):
    # Any uploaded image is normalized to an upright JPEG before storage, regardless
    # of the source format/extension.
    import io

    from PIL import Image

    factory, _store, attempt_id = fixture

    class _RecordingStore:
        def __init__(self):
            self.calls = []
        def put(self, key, data, content_type):
            self.calls.append((key, data, content_type))
            return key
        def get(self, key):
            return next(d for k, d, _ in self.calls if k == key)

    png_buf = io.BytesIO()
    Image.new("RGB", (20, 30), "white").save(png_buf, format="PNG")

    rec = _RecordingStore()
    vision = FakeVision(VisionRead(printed_id=None, problems=[
        ProblemRead(number=1, read_answer="4", confidence=0.9),
        ProblemRead(number=2, read_answer="6", confidence=0.9),
    ]))
    async with factory() as s:
        attempt = (await s.exec(select(Attempt).where(Attempt.id == attempt_id))).one()
        result = await grade_submission(session=s, store=rec, vision=vision,
                                        attempt=attempt, photo=png_buf.getvalue(), ext="png")
    key, data, ctype = rec.calls[0]
    assert key == f"submissions/{result.submission_id}.jpg"
    assert ctype == "image/jpeg"
    assert Image.open(io.BytesIO(data)).format == "JPEG"
