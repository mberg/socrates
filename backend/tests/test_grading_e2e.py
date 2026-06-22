import os

import pytest

from app.grading.vision import GeminiVision, ProblemPrompt

requires_vertex = pytest.mark.skipif(
    not os.environ.get("GEMINI_USE_VERTEX"),
    reason="set GEMINI_USE_VERTEX + GOOGLE_APPLICATION_CREDENTIALS + vertex project/location to run",
)


@requires_vertex
def test_real_vertex_reads_a_sample_photo():
    """Reads a real photo of a completed sheet; asserts it returns per-problem answers.

    Provide a sample image path via GRADING_SAMPLE_IMAGE (a photo of a printed,
    completed worksheet). This exercises GeminiVision.read end-to-end on Vertex.
    """
    img_path = os.environ["GRADING_SAMPLE_IMAGE"]
    with open(img_path, "rb") as f:
        image = f.read()
    v = GeminiVision(
        use_vertex=True,
        model=os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite"),
        project=os.environ["GEMINI_VERTEX_PROJECT"],
        location=os.environ["GEMINI_VERTEX_LOCATION"],
    )
    read = v.read(image, [ProblemPrompt(number=1, prompt="(from the sample sheet)")])
    assert read.problems  # got at least one per-problem read back
