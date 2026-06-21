from uuid import uuid4

from sqlalchemy import Column, UniqueConstraint
from sqlalchemy import JSON as SAJSON
from sqlmodel import Field, SQLModel


def _id() -> str:
    return uuid4().hex


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
