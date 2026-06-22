from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.api.catalog import router as catalog_router
from app.api.children import router as children_router
from app.api.grading import router as grading_router
from app.api.guidance import router as guidance_router

_BACKEND_DIR = Path(__file__).resolve().parent.parent
_FRONTEND_DIST = _BACKEND_DIR.parent / "frontend" / "dist"
_TESTER_HTML = Path(__file__).parent / "static" / "tester.html"


def create_app() -> FastAPI:
    app = FastAPI(title="Socrates")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/dev", include_in_schema=False)
    async def dev_tester() -> FileResponse:
        return FileResponse(_TESTER_HTML, media_type="text/html")

    app.include_router(catalog_router)
    app.include_router(children_router)
    app.include_router(grading_router)
    app.include_router(guidance_router)

    if _FRONTEND_DIST.is_dir():
        # Mounting at "/" must come AFTER routers so /api and /health win.
        app.mount("/", StaticFiles(directory=_FRONTEND_DIST, html=True), name="app")
    else:
        @app.get("/", include_in_schema=False)
        async def _no_build() -> HTMLResponse:
            return HTMLResponse(
                "<h1>Socrates</h1><p>Frontend not built. Run <code>cd frontend && npm run build</code>, "
                "or use the dev harness at <a href='/dev'>/dev</a>.</p>"
            )

    return app


app = create_app()
