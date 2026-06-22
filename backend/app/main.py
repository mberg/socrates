from fastapi import FastAPI

from app.api.catalog import router as catalog_router
from app.api.children import router as children_router
from app.api.grading import router as grading_router


def create_app() -> FastAPI:
    app = FastAPI(title="Socrates")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(catalog_router)
    app.include_router(children_router)
    app.include_router(grading_router)
    return app


app = create_app()
