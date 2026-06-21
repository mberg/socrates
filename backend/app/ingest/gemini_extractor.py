from google import genai

from app.ingest.extractor import Extraction
from app.ingest.pdf import PdfPages

_PROMPT = (
    "You are given two images: page 1 is a blank math worksheet, page 2 is its "
    "answer key, plus their extracted text. Return the worksheet's title, any "
    "instructions, the worked example, and every numbered problem with its prompt "
    "(from page 1) and correct answer (from page 2). Numbers must be contiguous "
    "starting at 1. Set confidence in [0,1] per problem."
)


class GeminiExtractor:
    def __init__(
        self,
        api_key: str = "",
        model: str = "gemini-3.1-flash-lite",
        *,
        use_vertex: bool = False,
        project: str | None = None,
        location: str | None = None,
    ) -> None:
        if use_vertex:
            self._client = genai.Client(vertexai=True, project=project, location=location)
        else:
            self._client = genai.Client(api_key=api_key)
        self._model = model

    def extract(self, pages: PdfPages) -> Extraction:
        parts = [
            _PROMPT,
            f"PAGE 1 TEXT:\n{pages.page1_text}",
            f"PAGE 2 TEXT:\n{pages.page2_text or ''}",
            genai.types.Part.from_bytes(data=pages.page1_png, mime_type="image/png"),
        ]
        if pages.page2_png:
            parts.append(genai.types.Part.from_bytes(data=pages.page2_png, mime_type="image/png"))
        resp = self._client.models.generate_content(
            model=self._model,
            contents=parts,
            config={"response_mime_type": "application/json", "response_schema": Extraction},
        )
        return Extraction.model_validate_json(resp.text)
