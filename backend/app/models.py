import secrets
from uuid import uuid4
from datetime import UTC, datetime

from sqlalchemy import Column, UniqueConstraint
from sqlalchemy import JSON as SAJSON
from sqlmodel import Field, SQLModel


def _id() -> str:
    return uuid4().hex


# Base36 minus look-alikes (0/O, 1/I/L) so the printed code is unambiguous to
# both a person and the vision model reading it off a photo. 31 chars ^ 5 ≈ 28.6M.
_CODE_ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"


def _code() -> str:
    return "".join(secrets.choice(_CODE_ALPHABET) for _ in range(5))


class Skill(SQLModel, table=True):
    __tablename__ = "skill"
    __table_args__ = (UniqueConstraint("grade", "skill_key"),)
    id: str = Field(default_factory=_id, primary_key=True)
    grade: int
    topic: str
    skill_key: str = Field(index=True)
    label: str


class Worksheet(SQLModel, table=True):
    __tablename__ = "worksheet"
    __table_args__ = (UniqueConstraint("pdf_sha256"),)
    id: str = Field(default_factory=_id, primary_key=True)
    skill_id: str = Field(foreign_key="skill.id", index=True)
    source: str  # "k5" | "generated"
    variant: str | None = None
    title: str
    worked_example: str | None = None
    source_pdf_r2_key: str | None = None
    problem_count: int = 0
    pdf_sha256: str = Field(index=True)


class Problem(SQLModel, table=True):
    __tablename__ = "problem"
    id: str = Field(default_factory=_id, primary_key=True)
    worksheet_id: str = Field(foreign_key="worksheet.id", index=True)
    number: int
    prompt: str
    correct_answer: str
    extraction_confidence: float | None = None


class QuarantinedExtraction(SQLModel, table=True):
    __tablename__ = "quarantined_extraction"
    id: str = Field(default_factory=_id, primary_key=True)
    pdf_path: str
    pdf_sha256: str = Field(index=True)
    reason: str
    raw_json: dict = Field(default_factory=dict, sa_column=Column(SAJSON))


def _utcnow() -> datetime:
    """Return current UTC time as a naive datetime (matches TIMESTAMP WITHOUT TIME ZONE columns)."""
    return datetime.now(UTC).replace(tzinfo=None)


class Child(SQLModel, table=True):
    __tablename__ = "child"
    id: str = Field(default_factory=_id, primary_key=True)
    name: str
    grade: int
    pin_hash: str | None = None
    created_at: datetime = Field(default_factory=_utcnow)


class Attempt(SQLModel, table=True):
    __tablename__ = "attempt"
    id: str = Field(default_factory=_id, primary_key=True)
    # Short, unambiguous human/OCR-readable code stamped on the print + used as the
    # QR payload. Nullable so attempts created before this column exists still load.
    code: str | None = Field(default_factory=_code, index=True, unique=True)
    child_id: str = Field(foreign_key="child.id", index=True)
    worksheet_id: str = Field(foreign_key="worksheet.id", index=True)
    status: str = "printed"  # "printed" | "scanned" | "graded"
    print_pdf_r2_key: str | None = None
    printed_at: datetime | None = None
    scanned_at: datetime | None = None
    graded_at: datetime | None = None
    created_at: datetime = Field(default_factory=_utcnow)


class Submission(SQLModel, table=True):
    __tablename__ = "submission"
    id: str = Field(default_factory=_id, primary_key=True)
    attempt_id: str = Field(foreign_key="attempt.id", index=True)
    photo_r2_key: str
    created_at: datetime = Field(default_factory=_utcnow)


class ProblemResult(SQLModel, table=True):
    __tablename__ = "problem_result"
    id: str = Field(default_factory=_id, primary_key=True)
    submission_id: str = Field(foreign_key="submission.id", index=True)
    problem_id: str = Field(foreign_key="problem.id", index=True)
    read_answer: str | None = None
    is_correct: bool
    confidence: float
    match_method: str  # "exact" | "normalized" | "gemini_equiv"
    needs_review: bool = False


class GuidanceSession(SQLModel, table=True):
    __tablename__ = "guidance_session"
    id: str = Field(default_factory=_id, primary_key=True)
    child_id: str = Field(foreign_key="child.id", index=True)
    attempt_id: str = Field(foreign_key="attempt.id", index=True)
    problem_id: str = Field(foreign_key="problem.id", index=True)
    problem_result_id: str = Field(foreign_key="problem_result.id", index=True)
    entry_point: str = "post_grade"  # only value in Plan 4; field exists for Plan 5
    max_tier_reached: int = 1        # server-enforced floor; only this + resolved mutate
    resolved: bool = False
    scan_attached: bool = False
    revealed_at: datetime | None = None  # when "Show me the answer" was first clicked
    created_at: datetime = Field(default_factory=_utcnow)


class TutorTurn(SQLModel, table=True):
    __tablename__ = "tutor_turn"
    id: str = Field(default_factory=_id, primary_key=True)
    session_id: str = Field(foreign_key="guidance_session.id", index=True)
    role: str                       # "child" | "tutor"
    text: str
    input_source: str | None = None  # "typed" | "voice" for child turns; None for tutor
    visuals: list = Field(default_factory=list, sa_column=Column(SAJSON))
    tier: int
    created_at: datetime = Field(default_factory=_utcnow)
