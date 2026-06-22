import argparse
import asyncio
import re
from collections import Counter
from pathlib import Path

from app.db import create_all, engine
from app.ingest.gemini_extractor import GeminiExtractor
from app.ingest.orchestrator import ingest_pdf
from app.config import settings
from app.storage import InMemoryObjectStore, R2ObjectStore
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession

_GRADE_FILE_RE = re.compile(r"^grade[-_]\d+[-_]")


def discover_pdfs(root: str) -> list[str]:
    return sorted(
        str(p)
        for p in Path(root).rglob("*.pdf")
        if _GRADE_FILE_RE.match(p.name)
    )


async def _run(root: str, dry_run: bool, *, extractor=None, store=None, loader=None,
               session_factory=None, concurrency: int = 8) -> int:
    if extractor is None:
        if settings.gemini_use_vertex:
            extractor = GeminiExtractor(
                use_vertex=True,
                project=settings.gemini_vertex_project,
                location=settings.gemini_vertex_location,
                model=settings.gemini_model,
            )
        else:
            extractor = GeminiExtractor(settings.gemini_api_key, model=settings.gemini_model)
    if store is None:
        store = InMemoryObjectStore() if dry_run else R2ObjectStore()
    if session_factory is None:
        await create_all()
        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    sem = asyncio.Semaphore(concurrency)
    ingest_kwargs = {} if loader is None else {"loader": loader}

    async def _process(path):
        async with sem:
            async with session_factory() as session:
                try:
                    outcome = await ingest_pdf(path, session=session, extractor=extractor,
                                               store=store, **ingest_kwargs)
                    print(f"{outcome.status:11} {path}")
                    return outcome.status
                except Exception as e:
                    print(f"errored     {path}: {type(e).__name__}: {e}")
                    return "errored"

    statuses = await asyncio.gather(*[_process(p) for p in discover_pdfs(root)])
    counts = Counter(statuses)
    print(f"\nSummary: {dict(counts)}")
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="socrates")
    sub = parser.add_subparsers(dest="command", required=True)
    ing = sub.add_parser("ingest")
    ing.add_argument("root")
    ing.add_argument("--dry-run", action="store_true")
    ing.add_argument("--concurrency", type=int, default=8)
    args = parser.parse_args(argv)
    if args.command == "ingest":
        return asyncio.run(_run(args.root, args.dry_run, concurrency=args.concurrency))
    return 1


if __name__ == "__main__":
    import sys

    raise SystemExit(main(sys.argv[1:]))
