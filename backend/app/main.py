from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

from app.api.catalog import router as catalog_router
from app.api.children import router as children_router
from app.api.grading import router as grading_router

_TESTER_HTML = Path(__file__).parent / "static" / "tester.html"


def create_app() -> FastAPI:
    app = FastAPI(title="Socrates")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/", include_in_schema=False)
    async def tester() -> FileResponse:
        # Throwaway phone-friendly harness to exercise print → photo → grade.
        return FileResponse(_TESTER_HTML, media_type="text/html")

    app.include_router(catalog_router)
    app.include_router(children_router)
    app.include_router(grading_router)
    return app


app = create_app()
