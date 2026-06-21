import hashlib
from dataclasses import dataclass

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.ingest.extractor import Extractor
from app.ingest.pdf import PdfPages, load_pdf
from app.ingest.taxonomy import parse_filename
from app.ingest.validate import validate
from app.models import Problem, QuarantinedExtraction, Skill, Worksheet
from app.storage import ObjectStore


@dataclass(frozen=True)
class IngestOutcome:
    status: str  # "inserted" | "skipped" | "quarantined"
    worksheet_id: str | None
    reason: str | None


async def _get_or_create_skill(session: AsyncSession, tax) -> Skill:
    existing = (await session.exec(select(Skill).where(Skill.skill_key == tax.skill_key, Skill.grade == tax.grade))).first()
    if existing:
        return existing
    skill = Skill(grade=tax.grade, topic=tax.topic, skill_key=tax.skill_key, label=tax.skill_key)
    session.add(skill)
    await session.flush()
    return skill


async def ingest_pdf(path, *, session: AsyncSession, extractor: Extractor, store: ObjectStore,
                     loader=load_pdf) -> IngestOutcome:
    with open(path, "rb") as fh:
        raw = fh.read()
    sha = hashlib.sha256(raw).hexdigest()
    if (await session.exec(select(Worksheet).where(Worksheet.pdf_sha256 == sha))).first():
        return IngestOutcome("skipped", None, None)

    tax = parse_filename(path)
    pages: PdfPages = loader(path)
    extraction = extractor.extract(pages)
    result = validate(extraction)
    if not result.ok:
        session.add(QuarantinedExtraction(pdf_path=path, pdf_sha256=sha, reason=result.reason or "invalid",
                                          raw_json=extraction.model_dump()))
        await session.commit()
        return IngestOutcome("quarantined", None, result.reason)

    skill = await _get_or_create_skill(session, tax)
    if skill.label == skill.skill_key and extraction.title:
        skill.label = extraction.title
    r2_key = store.put(f"worksheets/{sha}.pdf", raw, "application/pdf")
    ws = Worksheet(skill_id=skill.id, source="k5", variant=tax.variant, title=extraction.title,
                   worked_example=extraction.worked_example, source_pdf_r2_key=r2_key,
                   problem_count=len(extraction.problems), pdf_sha256=sha)
    session.add(ws)
    await session.flush()
    for p in extraction.problems:
        session.add(Problem(worksheet_id=ws.id, number=p.number, prompt=p.prompt,
                            correct_answer=p.correct_answer, extraction_confidence=p.confidence))
    await session.commit()
    return IngestOutcome("inserted", ws.id, None)
