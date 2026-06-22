import asyncio

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models import Attempt, Child, Worksheet, _utcnow
from app.printing.print_pdf import build_print_pdf
from app.storage import ObjectStore


async def create_attempt(*, session: AsyncSession, store: ObjectStore, child: Child,
                         worksheet_id: str) -> Attempt:
    ws = (await session.exec(select(Worksheet).where(Worksheet.id == worksheet_id))).first()
    if ws is None or ws.source_pdf_r2_key is None:
        raise LookupError(f"worksheet not found or has no source PDF: {worksheet_id}")

    attempt = Attempt(child_id=child.id, worksheet_id=worksheet_id, status="printed",
                      printed_at=_utcnow())
    source_pdf = await asyncio.to_thread(store.get, ws.source_pdf_r2_key)
    caption = f"{child.name} · {ws.title[:40]}"
    # The short code is the QR payload + the big readable stamp; the uuid id stays
    # internal (PK + API path).
    print_pdf = await asyncio.to_thread(build_print_pdf, source_pdf, attempt.code, caption)
    print_key = f"prints/{attempt.id}.pdf"
    await asyncio.to_thread(store.put, print_key, print_pdf, "application/pdf")
    attempt.print_pdf_r2_key = print_key

    session.add(attempt)
    await session.commit()
    return attempt
